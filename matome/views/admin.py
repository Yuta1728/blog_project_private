# ======================================================================
# views/admin.py — 管理者専用ページ（ログイン必須）
# ======================================================================
#
# 【役割】
#   管理者専用ページのルートとロジックを担うビューファイル。
#
#   担当機能:
#     /create          → 新規記事投稿
#     /<id>/update     → 記事編集
#     /<id>/delete     → 記事削除
#     /mypage          → マイページ（投稿一覧・ニックネーム変更）
#
# 【このファイルの構成（目次）】
#   [1] 定数定義（ファイルアップロード検証・画像最適化のパラメータ）
#   [2] ファイル検証ヘルパー
#        (2-1) allowed_file()            : 拡張子チェック
#        (2-2) _validate_image()         : 拡張子 + MIME の多層検証
#   [3] ハッシュタグ関連ヘルパー
#        (3-1) parse_hashtag_input()     : 入力文字列 → タグ名リスト
#        (3-2) sync_hashtags()           : Post とタグリストの同期
#        (3-3) delete_orphaned_hashtags(): 孤立タグの一括削除
#   [4] 画像キャプション関連ヘルパー
#        (4-1) parse_img_captions()      : フォーム → キャプションリスト
#   [5] ジャンルリスト生成ヘルパー
#        (5-1) _get_genre_list()         : 投稿フォームのジャンル選択肢
#   [6] 画像ファイル操作ヘルパー
#        (6-1) _optimize_body_image_save(): 本文画像を Pillow で縮小・再圧縮して保存
#        (6-2) _save_images()            : 検証 + 最適化保存（アトミック保証）
#        (6-3) _delete_images()          : 実ファイルの物理削除
#        (6-4) _save_thumbnail()         : サムネイル専用画像を WebP 縮小版で保存
#   [7] create()  : 新規投稿ビュー
#   [8] update()  : 記事編集ビュー
#   [9] delete()  : 記事削除ビュー
#   [10] mypage() : マイページビュー
#
# 【本文 HTML の事前生成について（improvement.md 項目 5）】
#   本文（Markdown + 独自タグ）の HTML 変換は閲覧のたびに行うと無駄なため、
#   投稿・編集時に rendering.render_post_body() で
#   (body_html, toc_html) を生成し、Post の同名カラムに保存する。
#   詳細表示（views/blog.py の detail）は保存済み HTML をそのまま出力する。
#   本文・画像（img_name / img_captions）が確定した後に生成することで、
#   [imgN] 置換なども含めた最終形をキャッシュできる。
#
# 【レンダラのバージョン記録（improvement.md 第2版 項目 B-3）】
#   生成した HTML には「どのバージョンの rendering.py で作ったか」を
#   Post.render_version として一緒に保存する。
#   これにより rendering.py を変更して RENDER_VERSION を +1 すれば、
#   既存記事も detail() 側で自動的に作り直される（キャッシュの無効化）。
#
# 【例外時のログ出力について（improvement.md 第2版 項目 A-5）】
#   このファイルは commit 失敗や画像処理エラーを except で捕まえ、
#   ユーザーには flash で「エラーが発生しました」と伝える設計になっている。
#   これはユーザー体験としては正しいが、従来は例外を捨てていたため
#   サーバー側に原因（トレースバック）が一切残らなかった。
#   本番で「投稿できない」「画像が保存できない」といった障害が起きても
#   何が起きたのか調べる手段がない状態だった。
#
#   そこで各 except に current_app.logger を追加した。
#     ・logger.exception() … 想定外の失敗。トレースバックまで自動で記録する
#     ・logger.warning()   … 想定内だが記録しておきたい事象（後始末など）
#   出力先とフォーマットは app.py の _configure_logging() が設定しており、
#   PythonAnywhere では Web タブの「Error log」から確認できる。
#
#   なお flash / redirect などユーザー向けの挙動は一切変えていない。
#   「記録を足しただけ」なので、画面の見た目や操作感は従来どおり。
#
# ======================================================================

from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user, login_required
from datetime import datetime
from urllib.parse import urlparse  # Open Redirect 対策のための URL パース
import os
import uuid
import pytz
import filetype    # ファイルの実際の MIME タイプを判定するライブラリ（拡張子偽装の検出）
from PIL import Image, ImageOps  # アップロード画像の縮小・再圧縮に使用
from extensions import db
from models import Post, Hashtag
from constants import DEFAULT_GENRES
# 本文 → (body_html, toc_html) の事前生成と、そのレンダラのバージョン
from rendering import render_post_body, RENDER_VERSION
import config

admin_bp = Blueprint('admin', __name__)

# Pillow の高品質リサンプリング定数。
# Pillow 9.1 以降は Image.Resampling 名前空間、それ以前はトップレベル定数。
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1 用のフォールバック
    _RESAMPLE = Image.LANCZOS


# ======================================================================
# [1] 定数定義: アップロード検証用ホワイトリスト + 画像最適化パラメータ
# ======================================================================

# 拡張子チェック（第 1 層の防御）: ファイル名の末尾を確認
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# MIME タイプチェック（第 2 層の防御）: ファイルの先頭バイトを読んで実際の形式を確認
# 拡張子を偽装した悪意あるファイル（例: malware.exe を image.jpg にリネーム）を弾く
ALLOWED_MIME_TYPES  = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}

# ---- 画像最適化パラメータ --------------------------------------------
# 本文画像: 長辺がこの値（px）を超える場合のみ、この値まで縮小する（拡大はしない）
#
# 【1600 → 1200 に引き下げた理由（improvement.md 第2版 項目 B-4）】
# 本文画像は 1 サイズしか配信していないため、スマートフォン（表示幅は実質
# 350〜400px 程度）でも同じ画像をダウンロードすることになり、
# モバイル回線では転送量が体感速度に直結していた。
#
# 本来の解決策は「640 / 1280 / 1600px を生成して srcset で出し分ける」ことだが
# 実装コストが高い。一方この記事本文の最大表示幅は detail.css の
# .detail-container（max-width: 860px）と article の左右パディングから
# 実質 740px 程度であり、高精細ディスプレイ（2 倍解像度）を考慮しても
# 1200px あれば足りる。
#
# そのため、まずは上限を 1200px に下げるだけの簡易対応とする。
# これだけでも面積比で約 44%（1200² / 1600²）まで減り、
# JPEG/WebP の転送量はおおむね半分前後になる。
#
# ※ この値を変えても、既にアップロード済みの画像は縮小し直されない
#   （次回アップロードする画像から適用される）。
BODY_IMAGE_MAX_EDGE = 1200
# サムネイル専用画像: 幅がこの値（px）を超える場合のみ、この幅まで縮小して WebP 化する
THUMBNAIL_MAX_WIDTH = 400
# 再エンコード時の品質（0〜100。大きいほど高画質・大サイズ）
JPEG_QUALITY       = 85
WEBP_QUALITY_BODY  = 82
WEBP_QUALITY_THUMB = 80

# ---- 一覧のページネーション設定 --------------------------------------
# マイページ（mypage）の 1 ページあたりの表示件数。
# トップページ（views/blog.py の POSTS_PER_PAGE）と同じ 4 件にそろえている。
POSTS_PER_PAGE = 4


# ======================================================================
# [2] ファイル検証ヘルパー
# ======================================================================

# ----------------------------------------------------------------------
# (2-1) 拡張子チェック
# ----------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    """
    ファイル名の拡張子がホワイトリストに含まれているかチェックする。
    '.' を含み、かつ最後の '.' 以降が許可リストにあれば True を返す。
    （例: 'photo.jpg' → True, 'script.php' → False）
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------------------------------------------------------------
# (2-2) 拡張子 + MIME の多層検証
# ----------------------------------------------------------------------
def _validate_image(file) -> None:
    """
    アップロードされた 1 ファイルを検証する（多層防御）。

    第 1 層: allowed_file() で拡張子チェック
    第 2 層: filetype.guess() で先頭バイトから MIME タイプを判定（拡張子偽装の検出）

    問題があれば ValueError を送出する。検証後はストリーム位置を先頭へ戻すので、
    続けて Pillow の Image.open() / file.save() が読み込める状態になる。

    【A-5】検証で弾いた事実は warning として記録する。
    ユーザーの操作ミス（対応外の形式を選んだ）であることがほとんどだが、
    偽装ファイルのアップロードが繰り返されている場合は
    攻撃の兆候として検知できるようにしておく。
    """
    # 第 1 層: 拡張子
    if not allowed_file(file.filename):
        current_app.logger.warning(
            '許可されていない拡張子のアップロードを拒否しました (filename=%r)', file.filename
        )
        raise ValueError('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)')

    # 第 2 層: 先頭バイトから MIME タイプを判定
    header = file.stream.read(2048)
    file.stream.seek(0)  # ストリーム位置をリセット（後続の読み込みに備える）
    kind = filetype.guess(header)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        current_app.logger.warning(
            '内容が画像でないファイルのアップロードを拒否しました '
            '(filename=%r, detected_mime=%s)',
            file.filename, kind.mime if kind else 'unknown'
        )
        raise ValueError('ファイルの内容が不正です。画像偽装の可能性があります。')


# ======================================================================
# [3] ハッシュタグ関連ヘルパー
# ======================================================================

# ----------------------------------------------------------------------
# (3-1) 入力文字列 → タグ名リスト
# ----------------------------------------------------------------------
def parse_hashtag_input(raw: str) -> list[str]:
    """
    フォームから受け取ったハッシュタグ入力文字列を
    「# なしのタグ名リスト」に変換する。

    対応する入力形式:
      "#Flask #Python ブログ" → ['Flask', 'Python', 'ブログ']
      "Flask,Python,ブログ"   → ['Flask', 'Python', 'ブログ']
      "Flask　Python"         → ['Flask', 'Python']  （全角スペースも対応）

    @param raw: フォームの hashtag_input フィールドの値
    @return: タグ名文字列のリスト（'#' なし）
    """
    import re

    # STEP 1. 前処理
    raw = raw.strip()
    if not raw:
        return []

    # STEP 2. 区切り文字: 半角スペース・全角スペース・カンマ・読点 のいずれか 1 文字以上
    tokens = re.split(r'[\s　,、]+', raw)

    # STEP 3〜4. '#' 除去 + フィルタリング
    names, seen = [], set()
    for token in tokens:
        name = token.lstrip('#').strip()  # 先頭の # を除去
        if name and name not in seen and len(name) <= 50:
            names.append(name)
            seen.add(name)  # 重複チェック用セットに追加

    return names


# ----------------------------------------------------------------------
# (3-2) Post とタグリストの同期
# ----------------------------------------------------------------------
def sync_hashtags(post: Post, tag_names: list[str]) -> None:
    """
    post.hashtags リレーションを tag_names リストと同期する。
    「既存タグがあれば再利用、なければ新規作成」を行う。

    @param post: 同期対象の Post オブジェクト
    @param tag_names: 新しいタグ名リスト（'#' なし）
    """
    new_tags = []
    for name in tag_names:
        # 既存タグの検索・再利用
        tag = Hashtag.query.filter_by(name=name).first()
        if not tag:
            # DB に存在しない新タグ → 新規作成
            tag = Hashtag(name=name)
            db.session.add(tag)
        new_tags.append(tag)

    # リレーションを上書き（中間テーブルの更新は SQLAlchemy が自動処理）
    post.hashtags = new_tags


# ----------------------------------------------------------------------
# (3-3) 孤立タグの一括削除
# ----------------------------------------------------------------------
def delete_orphaned_hashtags() -> None:
    """
    どの記事にも紐付いていない孤立ハッシュタグを一括削除する。
    記事削除後・記事編集後に、commit 前に呼んでセッションに乗せてから commit する。

    ~Hashtag.posts.any() は中間テーブルを「タグ側から」参照する NOT EXISTS で、
    ix_post_hashtags_hashtag_id（項目 A-1）が効く経路のひとつ。
    """
    orphaned = Hashtag.query.filter(~Hashtag.posts.any()).all()
    for tag in orphaned:
        db.session.delete(tag)


# ======================================================================
# [4] 画像キャプション関連ヘルパー
# ======================================================================

# ----------------------------------------------------------------------
# (4-1) フォーム → キャプションリスト
# ----------------------------------------------------------------------
def parse_img_captions(file_count: int, prefix: str = 'img_caption_') -> list[str]:
    """
    フォームから各画像のキャプションを取得してリストにまとめる。

    フォームの入力フィールド名の命名規則:
      {prefix}1, {prefix}2, {prefix}3, ...

    @param file_count: アップロードされた画像の枚数
    @param prefix: フォームフィールド名のプレフィックス
                   新規投稿:           'img_caption_'（デフォルト）
                   編集時の新規画像:   'new_img_caption_'
    @return: キャプション文字列のリスト（インデックスが画像の順番と対応）
    """
    captions = []
    for i in range(1, file_count + 1):
        caption = request.form.get(f'{prefix}{i}', '').strip()
        captions.append(caption)
    return captions


# ======================================================================
# [5] ジャンルリスト生成ヘルパー
# ======================================================================

# ----------------------------------------------------------------------
# (5-1) 投稿フォームのジャンル選択肢
# ----------------------------------------------------------------------
def _get_genre_list(user_id: int, current_genre: str | None = None) -> list[str]:
    """
    投稿フォームのジャンル選択肢リストを生成する。

    プリセット（DEFAULT_GENRES）とユーザーが過去に使ったジャンルの和集合を作り、
    プリセット順 → 独自ジャンル辞書順で安定して並べて返す。

    @param user_id: 現在ログイン中のユーザー ID
    @param current_genre: 編集中の記事のジャンル名（update 時のみ指定）
    @return: ジャンル名のソート済みリスト
    """
    # ユーザーが過去に使ったジャンル名を DB から取得（重複なし）
    existing = (
        db.session.query(Post.genre)
        .filter(Post.user_id == user_id,
                Post.genre != '未分類',
                Post.genre != None,
                Post.genre != '')
        .distinct()
        .all()
    )
    user_genres_list = [g[0] for g in existing]

    # プリセット + ユーザー既存ジャンルの和集合を作成
    all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)

    # 編集中の記事のジャンルが選択肢にない場合も追加（データの整合性を保つ）
    if current_genre:
        all_genres_set.add(current_genre)

    # '未分類' は select の先頭に固定で置くので除外
    all_genres_set.discard('未分類')

    # 並べ替えて返す（プリセット順 → 独自ジャンル辞書順）
    return sorted(
        list(all_genres_set),
        key=lambda x: (0, DEFAULT_GENRES.index(x)) if x in DEFAULT_GENRES else (1, x)
    )


# ======================================================================
# [6] 画像ファイル操作ヘルパー
# ======================================================================

# ----------------------------------------------------------------------
# (6-1) 本文画像を Pillow で最適化して保存
# ----------------------------------------------------------------------
def _optimize_body_image_save(file, save_path: str, ext: str) -> None:
    """
    本文画像 1 枚を Pillow で最適化し、save_path に保存する。

    最適化の内容:
      ・EXIF の向き情報を画素に反映（スマホ写真の回転ズレ対策）
      ・長辺が BODY_IMAGE_MAX_EDGE を超える場合のみ、その値まで縮小
        （項目 B-4 により上限は 1600px → 1200px へ引き下げ済み）
      ・元の形式を尊重して再エンコード（JPEG は品質指定、PNG/WebP は最適化）
      ・アニメーション GIF は劣化・静止化を避けるため原本をそのまま保存

    @param file:      werkzeug の FileStorage（検証済み）
    @param save_path: 保存先の絶対パス
    @param ext:       小文字の拡張子（'.jpg' など）
    @raises ValueError: 画像処理に失敗した場合
    """
    ext = ext.lower()
    try:
        img = Image.open(file.stream)

        # アニメーション GIF は原本を保存してフレーム・ループを保持する
        if getattr(img, 'is_animated', False):
            file.stream.seek(0)
            file.save(save_path)
            return

        # 撮影時の回転情報を画素に焼き込む（未指定の画像では実質何もしない）
        img = ImageOps.exif_transpose(img)

        # 長辺を上限まで縮小（超えていなければそのまま）
        img.thumbnail((BODY_IMAGE_MAX_EDGE, BODY_IMAGE_MAX_EDGE), _RESAMPLE)

        # 形式ごとに再エンコード
        if ext in ('.jpg', '.jpeg'):
            img = img.convert('RGB')  # JPEG は透過を持てないため RGB 化
            img.save(save_path, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif ext == '.png':
            img.save(save_path, 'PNG', optimize=True)   # 透過（RGBA/P）を保持
        elif ext == '.webp':
            img.save(save_path, 'WEBP', quality=WEBP_QUALITY_BODY, method=6)
        elif ext == '.gif':
            img.save(save_path, 'GIF')                  # 静止 GIF
        else:
            img.save(save_path)
    except ValueError:
        # 既に ValueError のものはそのまま上位へ
        raise
    except Exception:
        # Pillow 由来の各種例外（壊れた画像・巨大画像など）は
        # ユーザー向けの ValueError に正規化する。
        #
        # 【A-5】この正規化こそが、原因調査を最も難しくしていた箇所。
        # ユーザーには「別の画像でお試しください」としか出ないため、
        # 「どの形式のどんな画像で、Pillow が何の例外を投げたのか」が
        # サーバー側にも残らなかった。ここでトレースバックを記録する。
        current_app.logger.exception(
            '本文画像の変換に失敗しました (filename=%r, ext=%s, save_path=%s)',
            getattr(file, 'filename', None), ext, save_path
        )
        raise ValueError('画像の処理中にエラーが発生しました。別の画像でお試しください。')


# ----------------------------------------------------------------------
# (6-2) 検証 + 最適化保存（アトミック保証）
# ----------------------------------------------------------------------
def _save_images(files: list) -> list[str]:
    """
    アップロードされた本文画像を検証・最適化・保存し、
    保存したファイル名のリストを返す。

    途中でエラーが出た場合はそれまでに保存したファイルを掃除してから
    例外を再送出する（全成功のときだけファイルを残す）。

    @param files: request.files.getlist('img[]') のファイルオブジェクトのリスト
    @return: 保存したファイル名のリスト
    @raises ValueError: 検証エラー・画像処理エラー時
    """
    filename_list = []

    try:
        for file in files:
            # ファイルが選択されていない場合はスキップ
            if not file or file.filename == '':
                continue

            # 拡張子 + MIME 検証（失敗時は ValueError）
            _validate_image(file)

            # 拡張子は検証済みの元ファイル名から直接取得する
            ext = '.' + file.filename.rsplit('.', 1)[1].lower()

            # UUID でファイル名をランダム化し、掃除対象へ先行登録
            filename  = f"{uuid.uuid4()}{ext}"
            filename_list.append(filename)
            save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)

            # 縮小・再圧縮して保存
            _optimize_body_image_save(file, save_path, ext)

    except Exception:
        # 途中まで保存したファイルをここで掃除する。
        # 【A-5】「何枚保存した時点で中断し、何を消したか」を記録しておくと、
        # ディスク上のファイルと DB の食い違いを追うときの手がかりになる。
        # 例外そのものの詳細は送出元（_validate_image / _optimize_body_image_save）で
        # 既に記録済みのため、ここでは後始末の事実だけを warning で残す。
        if filename_list:
            current_app.logger.warning(
                '本文画像の保存が中断されたため、保存済みの %d 件を削除します: %s',
                len(filename_list), ','.join(filename_list)
            )
            _delete_images(','.join(filename_list))
        raise

    # 全成功: 保存したファイル名のリストを返す
    return filename_list


# ----------------------------------------------------------------------
# (6-3) 実ファイルの物理削除
# ----------------------------------------------------------------------
def _delete_images(img_name_str: str) -> None:
    """
    カンマ区切りファイル名をもとに static/img/posts/ 以下の実ファイルを物理削除する。
    必ず「DB の commit が成功した後」に呼ぶこと。

    【A-5】1 ファイルの削除失敗で全体を止めない
    この関数は「DB の更新が成功した後の後片付け」として呼ばれる。
    そのため削除に失敗しても、DB 側の変更（記事の保存・削除）は
    既に確定しており、巻き戻すべきではない。

    ところが従来は os.remove() を素で呼んでいたため、権限エラーや
    ファイルロック（Windows で別プロセスが掴んでいる等）が起きると
    例外がそのまま上位へ伝わり、「保存は成功しているのに 500 エラー画面が出る」
    という分かりにくい挙動になりうる。
    さらに複数ファイルを消す場合、1 件目で失敗すると 2 件目以降が
    処理されず、消し残しも発生する。

    そこで 1 ファイルずつ try で囲み、失敗はログに残して次へ進む。
    消し残したファイルはディスクを少し消費するだけで表示には影響しない
    （孤児ファイルの一括掃除は improvement.md 第2版 項目 B-6 の課題）。

    @param img_name_str: post.img_name の値（例: "uuid1.jpg,uuid2.png"）
    """
    if not img_name_str:
        return

    for img_file in img_name_str.split(','):
        img_path = os.path.join(current_app.static_folder, 'img', 'posts', img_file.strip())
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except OSError:
            # 削除できなくても処理は続行する（DB の状態は既に確定しているため）
            current_app.logger.exception(
                '画像ファイルの削除に失敗しました。孤児ファイルとして残ります (path=%s)',
                img_path
            )


# ----------------------------------------------------------------------
# (6-4) サムネイル専用画像を WebP 縮小版で保存
# ----------------------------------------------------------------------
def _save_thumbnail(file) -> str | None:
    """
    サムネイル専用にアップロードされた 1 枚の画像を検証し、
    幅 THUMBNAIL_MAX_WIDTH の軽量な WebP に変換して保存する。
    保存したファイル名（.webp）を返す。ファイル未選択なら None。

    @param file: request.files.get('thumbnail_img') のファイルオブジェクト
    @return: 保存したファイル名（.webp。未選択なら None）
    @raises ValueError: 検証エラー・画像処理エラー時
    """
    if not file or file.filename == '':
        return None

    # 拡張子 + MIME 検証（失敗時は ValueError。ここではまだファイル未生成）
    _validate_image(file)

    filename  = f"{uuid.uuid4()}.webp"   # サムネイルは形式を WebP に統一
    save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)

    try:
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)

        # WebP は RGB / RGBA を扱えるため、透過を保持したまま変換する
        if img.mode in ('P', 'LA'):
            img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')

        # 幅が上限を超える場合のみ、アスペクト比を保って縮小（拡大しない）
        w, h = img.size
        if w > THUMBNAIL_MAX_WIDTH:
            new_h = max(1, round(h * THUMBNAIL_MAX_WIDTH / w))
            img = img.resize((THUMBNAIL_MAX_WIDTH, new_h), _RESAMPLE)

        img.save(save_path, 'WEBP', quality=WEBP_QUALITY_THUMB, method=6)

    except ValueError:
        _delete_images(filename)  # 半端なファイルがあれば掃除
        raise
    except Exception:
        # 【A-5】本文画像と同じく、Pillow の例外を ValueError に丸める前に
        # トレースバックを残しておく。
        current_app.logger.exception(
            'サムネイル画像の変換に失敗しました (filename=%r, save_path=%s)',
            getattr(file, 'filename', None), save_path
        )
        _delete_images(filename)
        raise ValueError('サムネイル画像の処理中にエラーが発生しました。別の画像でお試しください。')

    return filename


# ======================================================================
# [7] 新規投稿
# ======================================================================

@admin_bp.route('/create', methods=['GET', 'POST'])
@login_required  # 未ログイン時は app.py の unauthorized_handler により 404 を返す
def create():
    """
    新規記事の投稿フォーム表示（GET）と保存処理（POST）を行う。

    【処理の流れ】
      STEP 1. 管理者チェック（管理者以外はトップへ）
      STEP 2. [POST] フォーム入力値を取得・バリデーション
      STEP 3. [POST] ジャンル・デフォルトサムネイルを決定
      STEP 4. [POST] 本文画像を検証・最適化保存（失敗時はフラッシュしてリダイレクト）
      STEP 4.5. [POST] サムネイル専用画像を検証・最適化保存
      STEP 4.7. [POST] 本文 HTML・目次 HTML を事前生成（詳細表示の再変換を防ぐ）
      STEP 5. [POST] Post オブジェクトを作成してセッションに追加
      STEP 6. [POST] flush() で post.id を確定 → ハッシュタグを同期
      STEP 7. [POST] commit（失敗時は rollback + 保存済み画像を掃除 + ログ記録）
      STEP 8. [GET]  ジャンル選択肢を生成して投稿フォームを表示
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        # --------------------------------------------------------------
        # STEP 2. フォーム入力値の取得とバリデーション
        # --------------------------------------------------------------
        title          = request.form.get('title', '').strip()
        body           = request.form.get('body', '').strip()
        selected_genre = request.form.get('genre_select')           # プリセットから選択したジャンル
        new_genre      = request.form.get('genre_new', '').strip()  # 新規入力したジャンル名
        hashtag_input  = request.form.get('hashtag_input', '')

        if not title or not body:
            flash('タイトルと内容はどちらも入力必須です。', 'danger')
            return redirect('/create')

        # --------------------------------------------------------------
        # STEP 3. ジャンル・デフォルトサムネイルの決定
        # --------------------------------------------------------------
        # ジャンルの優先順位: 新規入力 > プリセット選択 > デフォルト（未分類）
        final_genre = new_genre if new_genre else (selected_genre or '未分類')

        # デフォルトサムネイル: フォームで 'none' が選ばれた場合は NULL
        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        # --------------------------------------------------------------
        # STEP 4. 本文画像の保存（検証 + 最適化）
        # --------------------------------------------------------------
        try:
            filename_list = _save_images(request.files.getlist('img[]'))
        except ValueError as e:
            # 検証エラーの詳細は _validate_image / _optimize_body_image_save が
            # 記録済みのため、ここでは再度ログを出さずユーザーへ通知するだけにする。
            flash(str(e), 'danger')
            return redirect('/create')

        # ファイル名をカンマ区切りで 1 つの文字列に結合して DB に保存
        img_name_str = ','.join(filename_list) if filename_list else None

        # キャプションをタブ区切りで 1 つの文字列に結合
        captions         = parse_img_captions(len(filename_list))
        img_captions_str = '\t'.join(captions) if captions else None

        # --------------------------------------------------------------
        # STEP 4.5. サムネイル専用画像の保存（検証 + WebP 縮小）
        # --------------------------------------------------------------
        try:
            thumbnail_name = _save_thumbnail(request.files.get('thumbnail_img'))
        except ValueError as e:
            if img_name_str:
                _delete_images(img_name_str)
            flash(str(e), 'danger')
            return redirect('/create')

        # 公開設定: hidden フィールド is_published の値が 'true' なら True
        is_published = request.form.get('is_published') == 'true'

        # --------------------------------------------------------------
        # STEP 4.7. 本文 HTML・目次 HTML を事前生成
        # --------------------------------------------------------------
        # 本文・画像（img_name / img_captions）が確定した後に生成する。
        # これにより [imgN] 置換なども含めた最終形をキャッシュでき、
        # 詳細表示（detail）ではこれをそのまま出力するだけになる。
        body_html, toc_html = render_post_body(body, img_name_str, img_captions_str)

        # --------------------------------------------------------------
        # STEP 5. Post オブジェクトを作成してセッションに追加
        # --------------------------------------------------------------
        # updated_at は新規投稿時 NULL のまま（「まだ更新されていない」を明示）
        #
        # 【B-3】render_version には「この HTML を生成したレンダラのバージョン」を
        # 記録する。rendering.py を変更して RENDER_VERSION を +1 すると、
        # この記事は detail() 側で自動的に再生成される。
        post = Post(
            title          = title,
            body           = body,
            body_html      = body_html,
            toc_html       = toc_html,
            render_version = RENDER_VERSION,
            user_id        = current_user.id,
            img_name       = img_name_str,
            default_thumb  = selected_default_thumb,
            thumbnail_img  = thumbnail_name,
            genre          = final_genre,
            is_published   = is_published,
            img_captions   = img_captions_str,
            updated_at     = None,
        )
        db.session.add(post)

        # --------------------------------------------------------------
        # STEP 6. flush で ID を確定してハッシュタグを同期
        # --------------------------------------------------------------
        db.session.flush()

        # ハッシュタグの同期
        sync_hashtags(post, parse_hashtag_input(hashtag_input))

        # --------------------------------------------------------------
        # STEP 7. commit（失敗時は rollback + 保存済み画像を掃除）
        # --------------------------------------------------------------
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            # 【A-5】ここが握り潰されていた最たる箇所。
            # 制約違反・接続断・カラム長超過など原因は多岐にわたるが、
            # 従来はユーザーに「エラーが発生しました」と出るだけで
            # サーバー側に何も残らなかった。
            # 記事を特定できるようタイトルとユーザー ID も添える。
            current_app.logger.exception(
                '記事の保存に失敗しました (user_id=%s, title=%r, images=%s)',
                current_user.id, title, img_name_str
            )
            if img_name_str:
                _delete_images(img_name_str)
            if thumbnail_name:
                _delete_images(thumbnail_name)
            flash('投稿の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
            return redirect('/create')

        current_app.logger.info(
            '記事を新規投稿しました (post_id=%s, user_id=%s, published=%s)',
            post.id, current_user.id, is_published
        )
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 8. GET: 投稿フォームを表示
    # ------------------------------------------------------------------
    genres = _get_genre_list(current_user.id)
    return render_template('create.html', genres=genres)


# ======================================================================
# [8] 記事編集
# ======================================================================

@admin_bp.route('/<int:id>/update', methods=['GET', 'POST'])
@login_required
def update(id):
    """
    記事の編集フォーム表示（GET）と更新処理（POST）を行う。

    【処理の流れ】
      STEP 1. 管理者チェック + 記事の取得・権限チェック
      STEP 2. [GET]  既存データ（ジャンル・タグ・キャプション）を整えてフォーム表示
      STEP 3. [POST] タイトル・本文のバリデーションと基本項目の更新
      STEP 4. [POST] ハッシュタグの同期 + 孤立タグの削除予約
      STEP 5. [POST] 本文画像の更新（3 パターン: A 差し替え / B 個別削除 / C キャプションのみ）
      STEP 5.5. [POST] サムネイル専用画像の更新（差し替え / 削除 / 維持）
      STEP 5.7. [POST] 本文・画像の確定後に本文 HTML・目次 HTML を再生成
      STEP 6. [POST] 更新日時をセットして commit（失敗時はログ記録 + 掃除）
      STEP 7. [POST] commit 成功後に削除対象の旧ファイルを物理削除
      STEP 8. [POST] 記事詳細ページへリダイレクト
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック + 記事の取得・権限チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. GET: 編集フォームの初期値を設定して表示
    # ------------------------------------------------------------------
    if request.method == 'GET':
        genres = _get_genre_list(current_user.id, post.genre)

        # 既存ハッシュタグを "#Flask #Python" 形式の文字列に変換
        existing_hashtag_str = ' '.join(f'#{t.name}' for t in post.hashtags)

        # 既存キャプションをタブ区切りから配列に変換
        existing_captions = post.img_captions.split('\t') if post.img_captions else []

        return render_template('update.html', post=post, genres=genres,
                               existing_hashtag_str=existing_hashtag_str,
                               existing_captions=existing_captions)

    # ------------------------------------------------------------------
    # STEP 3. POST: バリデーションと基本項目の更新
    # ------------------------------------------------------------------
    # (3-1) タイトル・本文
    title = request.form.get('title', '').strip()
    body  = request.form.get('body', '').strip()
    if not title or not body:
        flash('タイトルと内容はどちらも入力必須です。', 'danger')
        return redirect(f'/{id}/update')

    post.title = title
    post.body  = body

    # (3-2) デフォルトサムネイルの更新
    selected_default_thumb = request.form.get('default_thumb_select')
    post.default_thumb = None if selected_default_thumb == 'none' else selected_default_thumb

    # (3-3) 公開設定の更新
    is_published_form = request.form.get('is_published')
    if is_published_form is not None:
        post.is_published = (is_published_form == 'true')

    # (3-4) ジャンルの更新
    new_genre      = request.form.get('genre_new', '').strip()
    selected_genre = request.form.get('genre_select')
    post.genre = new_genre if new_genre else (selected_genre or '未分類')

    # ------------------------------------------------------------------
    # STEP 4. ハッシュタグの同期 + 孤立タグの削除予約
    # ------------------------------------------------------------------
    sync_hashtags(post, parse_hashtag_input(request.form.get('hashtag_input', '')))
    delete_orphaned_hashtags()

    # ------------------------------------------------------------------
    # STEP 5. 本文画像の更新
    # ------------------------------------------------------------------
    # 3 つのパターンを扱う:
    #   A) 新しい画像が選択された          → 全画像を新画像で差し替え
    #   B) 新画像なし + 個別削除フラグあり → 指定された既存画像だけを削除
    #   C) 新画像なし + 削除フラグなし     → キャプションのみ更新
    files = request.files.getlist('img[]')
    old_img_name  = None   # commit 成功後に物理削除する画像
    new_filenames = []     # commit 失敗時に掃除する新規保存ファイル

    if files and files[0].filename != '':
        # --------------------------------------------------------------
        # (5-A) パターン A: 画像の全差し替え（検証 + 最適化保存）
        # --------------------------------------------------------------
        try:
            new_filenames = _save_images(files)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(f'/{id}/update')

        old_img_name  = post.img_name           # 旧画像名を退避（commit 後に削除）
        post.img_name = ','.join(new_filenames)
        captions = parse_img_captions(len(new_filenames), prefix='new_img_caption_')
        post.img_captions = '\t'.join(captions) if captions else None

    elif post.img_name:
        # --------------------------------------------------------------
        # (5-B/C) パターン B / C: 既存画像の個別削除 + キャプション更新
        # --------------------------------------------------------------
        existing_imgs = post.img_name.split(',')
        kept_imgs     = []   # 残す画像ファイル名
        kept_captions = []   # 残す画像のキャプション
        removed_imgs  = []   # 削除予定の画像ファイル名

        for i, img in enumerate(existing_imgs, start=1):
            caption = request.form.get(f'img_caption_{i}', '').strip()

            # keep_img_N が '0' なら削除予定。
            # 送られてこない場合はデフォルト '1'（残す）扱い（安全側・後方互換）。
            if request.form.get(f'keep_img_{i}', '1') == '0':
                removed_imgs.append(img)
            else:
                kept_imgs.append(img)
                kept_captions.append(caption)

        if removed_imgs:
            # 削除対象を commit 成功後の物理削除キューに積む
            old_img_name = ','.join(removed_imgs)

        # 残った画像だけで DB 上の参照を再構築する。
        post.img_name     = ','.join(kept_imgs) if kept_imgs else None
        post.img_captions = '\t'.join(kept_captions) if kept_imgs else None

    # ------------------------------------------------------------------
    # STEP 5.5. サムネイル専用画像の更新
    # ------------------------------------------------------------------
    old_thumbnail_name  = None   # commit 成功後に物理削除する旧サムネイル
    new_thumbnail_saved = None   # commit 失敗時に掃除する新規保存サムネイル

    thumb_file = request.files.get('thumbnail_img')
    if thumb_file and thumb_file.filename != '':
        # --- サムネイルの差し替え（検証 + WebP 縮小） ---
        try:
            new_thumbnail_saved = _save_thumbnail(thumb_file)
        except ValueError as e:
            # 本文画像で今回新規保存したものがあれば掃除してから戻る
            if new_filenames:
                _delete_images(','.join(new_filenames))
            flash(str(e), 'danger')
            return redirect(f'/{id}/update')

        old_thumbnail_name = post.thumbnail_img   # 旧サムネイルを退避（commit 後に削除）
        post.thumbnail_img = new_thumbnail_saved

    elif request.form.get('keep_thumbnail', '1') == '0':
        # --- 現在のサムネイルを削除 ---
        old_thumbnail_name = post.thumbnail_img
        post.thumbnail_img = None

    # ------------------------------------------------------------------
    # STEP 5.7. 本文 HTML・目次 HTML の再生成
    # ------------------------------------------------------------------
    # 本文（post.body）と画像（post.img_name / post.img_captions）が
    # すべて確定した後に再生成し、キャッシュ列を更新する。
    # これにより次回以降の詳細表示は再変換なしで済む。
    #
    # 【B-3】生成に使ったレンダラのバージョンも一緒に更新する。
    # （古いバージョンで作られた記事を編集した場合、ここで最新版に揃う）
    post.body_html, post.toc_html = render_post_body(
        post.body, post.img_name, post.img_captions
    )
    post.render_version = RENDER_VERSION

    # ------------------------------------------------------------------
    # STEP 6. 更新日時をセットして commit
    # ------------------------------------------------------------------
    post.updated_at = datetime.now(pytz.timezone('Asia/Tokyo'))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # 【A-5】更新失敗の記録。どの記事の更新が落ちたかを追えるよう
        # post_id を必ず含める。
        current_app.logger.exception(
            '記事の更新に失敗しました (post_id=%s, user_id=%s, title=%r)',
            id, current_user.id, title
        )
        # commit 失敗 → 今回新規保存したファイルを掃除（DB は旧状態のまま無傷）
        if new_filenames:
            _delete_images(','.join(new_filenames))
        if new_thumbnail_saved:
            _delete_images(new_thumbnail_saved)
        flash('更新の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect(f'/{id}/update')

    # ------------------------------------------------------------------
    # STEP 7. commit 成功 → ここで初めて削除対象のファイルを物理削除する
    # ------------------------------------------------------------------
    if old_img_name:
        _delete_images(old_img_name)
    if old_thumbnail_name:
        _delete_images(old_thumbnail_name)

    current_app.logger.info(
        '記事を更新しました (post_id=%s, user_id=%s)', id, current_user.id
    )

    # ------------------------------------------------------------------
    # STEP 8. 記事詳細ページへリダイレクト
    # ------------------------------------------------------------------
    return redirect(f'/{id}/detail')


# ======================================================================
# [9] 記事削除
# ======================================================================

@admin_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """
    記事を削除する（POST のみ受付）。
    URL を直接叩いただけでは削除できない（CSRF トークンも必要）。
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック + 記事の取得・権限チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. 削除対象の画像名を退避（本文画像 + サムネイル）
    # ------------------------------------------------------------------
    # 物理削除は DB commit 成功後に行う（不整合防止）。
    files_to_delete = []
    if post.img_name:
        files_to_delete.append(post.img_name)
    if post.thumbnail_img:
        files_to_delete.append(post.thumbnail_img)
    img_name_to_delete = ','.join(files_to_delete) if files_to_delete else None

    # 削除後はログに出せなくなるので、タイトルをここで控えておく
    deleted_title = post.title

    # ------------------------------------------------------------------
    # STEP 3. ハッシュタグのリレーションをクリア + 孤立タグの削除予約
    # ------------------------------------------------------------------
    post.hashtags = []
    db.session.flush()  # 中間テーブルの削除を反映させてから孤立判定する

    delete_orphaned_hashtags()

    # ------------------------------------------------------------------
    # STEP 4. 記事を削除予約して commit
    # ------------------------------------------------------------------
    db.session.delete(post)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # 【A-5】削除失敗の記録。外部キー制約などで落ちた場合の調査に必要。
        current_app.logger.exception(
            '記事の削除に失敗しました (post_id=%s, user_id=%s, title=%r)',
            id, current_user.id, deleted_title
        )
        flash('削除中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 5. commit 成功 → ここで初めて関連画像ファイルを物理削除する
    # ------------------------------------------------------------------
    _delete_images(img_name_to_delete)

    current_app.logger.info(
        '記事を削除しました (post_id=%s, user_id=%s, title=%r)',
        id, current_user.id, deleted_title
    )

    # ------------------------------------------------------------------
    # STEP 6. 削除後のリダイレクト先決定（Open Redirect 対策）
    # ------------------------------------------------------------------
    referrer = request.referrer
    if referrer:
        parsed_ref = urlparse(referrer)
        parsed_req = urlparse(request.url)
        same_origin = (
            parsed_ref.scheme == parsed_req.scheme and
            parsed_ref.netloc == parsed_req.netloc
        )
        if same_origin:
            return redirect(referrer)

    return redirect('/')  # referer がない or 別オリジンならトップへ


# ======================================================================
# [10] マイページ
# ======================================================================

@admin_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    """
    マイページの表示（GET）とニックネーム変更（POST）を行う。

    自分の投稿は index と同じくサーバーサイドページネーション（1 ページ
    POSTS_PER_PAGE 件）で取得し、selectinload(Post.hashtags) で N+1 を防ぐ。
    総投稿数は pagination.total（全件数）を total_count として渡す。

    【処理の流れ】
      STEP 1. 管理者チェック
      STEP 2. [POST] ニックネームを更新して commit → マイページへリダイレクト
      STEP 3. [GET]  自分の記事をページネーションで取得（selectinload 付き）
      STEP 4. [GET]  使用ジャンル一覧を生成（'未分類' は末尾へ）
      STEP 5. [GET]  mypage.html をレンダリング
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. POST: ニックネーム変更処理
    # ------------------------------------------------------------------
    if request.method == 'POST':
        new_nickname = request.form.get('nickname', '').strip()
        # 空欄の場合は None にして「ニックネームなし」に戻す
        current_user.nickname = new_nickname or None

        # 【A-5】ここは従来 try/except を持たず、commit が失敗すれば
        # 例外がそのまま送出される（＝ Flask が 500 として記録する）。
        # 「握り潰し」ではないため挙動は変えないが、他のビューと同じく
        # 原因を追えるようにログを残し、ユーザーには他と同じ体裁で通知する。
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                'ニックネームの更新に失敗しました (user_id=%s, nickname=%r)',
                current_user.id, new_nickname
            )
            flash('ニックネームの更新中にエラーが発生しました。もう一度お試しください。', 'danger')
            return redirect('/mypage')

        flash('ニックネームを更新しました！' if new_nickname else 'ニックネームを解除しました。', 'info')
        return redirect('/mypage')

    # ------------------------------------------------------------------
    # STEP 3. GET: 自分の記事をサーバーサイドページネーションで取得
    # ------------------------------------------------------------------
    # 【B-2】記事カードがハッシュタグバッジを表示するため、ここで
    # selectinload により一括先読みして N+1 を防ぐ。
    # models.py 側の lazy='selectin' は撤去したので、
    # この options が「唯一の先読み指定」になる。
    page = request.args.get('page', 1, type=int)
    pagination = (
        Post.query
        .filter(Post.user_id == current_user.id)
        .options(db.selectinload(Post.hashtags))
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=POSTS_PER_PAGE, error_out=False)
    )
    user_posts = pagination.items  # 現在ページ分の記事だけ

    # ------------------------------------------------------------------
    # STEP 4. 使用ジャンル一覧の生成（サイドバー表示用）
    # ------------------------------------------------------------------
    user_genres_raw = (
        db.session.query(Post.genre)
        .filter(Post.user_id == current_user.id,
                Post.genre != None,
                Post.genre != '')
        .distinct()
        .all()
    )
    # 重複除去 + ソート（'未分類' を除いたもの）
    user_genres = sorted({g[0] for g in user_genres_raw if g[0] != '未分類'})
    # '未分類' が存在する場合のみ末尾に追加
    if any(g[0] == '未分類' for g in user_genres_raw):
        user_genres.append('未分類')

    # ------------------------------------------------------------------
    # STEP 5. テンプレートのレンダリング
    # ------------------------------------------------------------------
    return render_template(
        'mypage.html',
        posts       = user_posts,       # 現在ページ分の記事
        pagination  = pagination,       # ページ送りナビ生成用
        total_count = pagination.total, # 「総投稿数」表示用（全件数）
        user_genres = user_genres,
    )