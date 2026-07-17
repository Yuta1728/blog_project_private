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
# 【画像最適化の方針（このリビジョンでの追加）】
#   従来 _save_images() は原本を UUID 名で保存するだけで、リサイズも圧縮も
#   行っていなかった。一覧サムネイルは CSS 上 260×158px 程度なのに、
#   数 MB の原寸画像がそのまま配信され、読み込み速度を大きく損ねていた。
#
#   対策として Pillow でアップロード時に最適化する:
#     ・本文画像       … 長辺を BODY_IMAGE_MAX_EDGE（既定 1600px）まで縮小し再圧縮。
#                         形式は原則そのまま（JPEG/PNG/WebP/GIF）を尊重する。
#                         アニメーション GIF は劣化・静止化を避けるため原本のまま保存。
#     ・サムネイル画像 … 幅 THUMBNAIL_MAX_WIDTH（既定 400px）の WebP に変換して保存。
#                         thumbnail_img はこの軽量版ファイルを指す。
#   いずれも「上限を超える場合のみ縮小（拡大はしない）」で、EXIF の向き情報を
#   反映してから縮小する（スマホ写真の回転ズレ対策）。
#
# 【処理フロー図（投稿・編集・削除に共通する整合性ルール）】
#
#   画像ファイル（本文画像 + サムネイル）を最適化して保存
#        │        （全成功 or 全掃除のアトミック動作）
#        ▼
#   DB 変更をセッションに積む（add / 属性変更 / delete）
#        │
#        ▼
#   db.session.commit()
#        ├─ 失敗 → rollback + 今回保存した新ファイルを掃除
#        │          （DB は旧状態のまま無傷。孤立ファイルも残らない）
#        └─ 成功 → ここで初めて「削除対象の旧ファイル」を物理削除
#                   （万一削除に失敗しても孤立ファイルが残るだけで
#                     データは壊れない = 安全側に倒す）
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
BODY_IMAGE_MAX_EDGE = 1600
# サムネイル専用画像: 幅がこの値（px）を超える場合のみ、この幅まで縮小して WebP 化する
THUMBNAIL_MAX_WIDTH = 400
# 再エンコード時の品質（0〜100。大きいほど高画質・大サイズ）
JPEG_QUALITY       = 85
WEBP_QUALITY_BODY  = 82
WEBP_QUALITY_THUMB = 80

# ---- 一覧のページネーション設定 --------------------------------------
# マイページ（mypage）の 1 ページあたりの表示件数。
# トップページ（views/blog.py の index）は per_page=4 でページネーションして
# いるため、体験をそろえる意味で同じ 4 件にしている。
# （index 側は blog.py 内に直接 4 を書いているが、マイページは admin.py 内で
#   完結するので定数として明示しておく）
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

    ※ 従来は _save_images() 内にインラインで書かれていた検証を、
       本文画像・サムネイルの両方から使えるよう関数として切り出した（DRY）。
    """
    # 第 1 層: 拡張子
    if not allowed_file(file.filename):
        raise ValueError('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)')

    # 第 2 層: 先頭バイトから MIME タイプを判定
    header = file.stream.read(2048)
    file.stream.seek(0)  # ストリーム位置をリセット（後続の読み込みに備える）
    kind = filetype.guess(header)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
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

    対応する入力形式（ユーザーにとって入力しやすい形式を幅広く受け付ける）:
      "#Flask #Python ブログ" → ['Flask', 'Python', 'ブログ']
      "Flask,Python,ブログ"   → ['Flask', 'Python', 'ブログ']
      "Flask　Python"         → ['Flask', 'Python']  （全角スペースも対応）

    【処理の流れ】
      STEP 1. 前後の空白を除去。空なら空リストを返す
      STEP 2. 全角スペース・半角スペース・カンマ・読点 で分割
      STEP 3. 各トークンの先頭の '#' を除去
      STEP 4. 空文字列・50文字超・重複 を排除してリスト化

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

    【なぜ「同期」が必要か】
    単純に post.hashtags = [new_tag1, new_tag2, ...] と上書きすると
    編集前に付いていたタグが外れ、新しいタグが追加されるが、
    すでに DB に存在する同名タグが重複登録されるリスクがある。
    この関数では「既存タグがあれば再利用、なければ新規作成」を行う。

    【処理の流れ】
      STEP 1. tag_names の各タグ名を Hashtag テーブルで検索
      STEP 2. 存在すれば既存の Hashtag オブジェクトを使う
      STEP 3. 存在しなければ新規 Hashtag を作成して db.session.add()
      STEP 4. post.hashtags を新しいリストで上書き
              （SQLAlchemy が差分を検出して post_hashtags 中間テーブルを更新する）

    @param post: 同期対象の Post オブジェクト
    @param tag_names: 新しいタグ名リスト（'#' なし）
    """
    new_tags = []
    for name in tag_names:
        # STEP 1〜2. 既存タグの検索・再利用
        tag = Hashtag.query.filter_by(name=name).first()
        if not tag:
            # STEP 3. DB に存在しない新タグ → 新規作成
            tag = Hashtag(name=name)
            db.session.add(tag)
        new_tags.append(tag)

    # STEP 4. リレーションを上書き（中間テーブルの更新は SQLAlchemy が自動処理）
    post.hashtags = new_tags


# ----------------------------------------------------------------------
# (3-3) 孤立タグの一括削除
# ----------------------------------------------------------------------
def delete_orphaned_hashtags() -> None:
    """
    どの記事にも紐付いていない孤立ハッシュタグを一括削除する。

    【呼び出しタイミング】
    - 記事削除後（delete ビュー）
    - 記事編集後（update ビュー）
    どちらの操作でも「以前付いていたタグが外れる」可能性があるため、
    commit 前にこの関数を呼んでセッションにまとめて乗せてから commit する。

    【なぜ commit 前に呼ぶのか】
    sync_hashtags() が post.hashtags を新しいリストで上書きした時点で
    SQLAlchemy のセッション上では中間テーブルの削除が予約された状態になる。
    この段階で Hashtag.posts.any() を評価すると、まだ DB には反映されていないが
    セッション内の変更を考慮した結果が返るため、正確に孤立タグを検出できる。

    【処理の流れ】
      STEP 1. 「どの記事にも紐付いていない」タグを検索（~Hashtag.posts.any()）
      STEP 2. 該当タグを db.session.delete() で削除予約
              （実際の削除は呼び出し元の commit 時に実行される）
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
    （create.html / update.html の JavaScript で動的に生成される）

    【バグ修正】prefix 引数を追加
    update.html では「既存画像のキャプション欄（img_caption_N）」と
    「新規画像のキャプション欄」が同名だったため、画像を差し替えた際に
    request.form.get() が先に現れる旧画像側の値を拾ってしまい、
    新規画像のキャプションがずれるバグがあった。
    新規画像側のフィールド名を new_img_caption_N に分離し、
    呼び出し側で prefix を切り替えて取得する。

    【処理の流れ】
      STEP 1. 1 〜 file_count まで順番にフォーム値を取得
      STEP 2. 前後の空白を除去してリストに追加
              （インデックスが画像の順番と対応する）

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

    【処理の流れ】
      STEP 1. DEFAULT_GENRES（constants.py のプリセット）を取得
      STEP 2. このユーザーが既存記事で使っているジャンルを DB から取得
      STEP 3. STEP 1 + STEP 2 の和集合を取る（重複は除去）
      STEP 4. 編集中の記事のジャンルが上記にない場合も必ず含める
      STEP 5. '未分類' を除外（select の先頭に固定で置くため）
      STEP 6. DEFAULT_GENRES の順番を優先して並べ替えて返す

    @param user_id: 現在ログイン中のユーザー ID
    @param current_genre: 編集中の記事のジャンル名（update 時のみ指定）
    @return: ジャンル名のソート済みリスト
    """
    # ------------------------------------------------------------------
    # STEP 2. ユーザーが過去に使ったジャンル名を DB から取得（重複なし）
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # STEP 3. プリセット + ユーザー既存ジャンルの和集合を作成
    # ------------------------------------------------------------------
    all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)

    # ------------------------------------------------------------------
    # STEP 4. 編集中の記事のジャンルが選択肢にない場合も追加（データの整合性を保つ）
    # ------------------------------------------------------------------
    if current_genre:
        all_genres_set.add(current_genre)

    # ------------------------------------------------------------------
    # STEP 5. '未分類' は select の先頭に固定で置くので除外
    # ------------------------------------------------------------------
    all_genres_set.discard('未分類')

    # ------------------------------------------------------------------
    # STEP 6. 並べ替えて返す
    # ------------------------------------------------------------------
    # 【バグ修正】ソートキーを hash(x) からタプルキーに変更
    #
    # 従来は独自ジャンルのキーに len(DEFAULT_GENRES) + hash(x) を使っていたが、
    # hash() は負値を返しうるため、独自ジャンルがプリセットより
    # 前に並んでしまうことがあった（さらに実行のたびに順序が変わり不安定）。
    #
    # タプルキーによる 2 段階ソートに変更:
    #   プリセットジャンル → (0, DEFAULT_GENRES 内のインデックス)
    #   独自ジャンル       → (1, ジャンル名の辞書順)
    # タプル比較では第 1 要素が優先されるため、
    # 「プリセット順 → 独自ジャンル辞書順」の安定した並びが保証される。
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
        （thumbnail() は縮小専用でアスペクト比を保ち、拡大はしない）
      ・元の形式を尊重して再エンコード（JPEG は品質指定、PNG/WebP は最適化）
      ・アニメーション GIF は劣化・静止化を避けるため原本をそのまま保存

    【呼び出し前の前提】
      file は _validate_image() で検証済みで、ストリーム位置は先頭にある。

    【エラー方針】
      Pillow の処理に失敗した場合は ValueError に変換して送出する。
      これにより _save_images() の except（掃除 + 再送出）や、さらに
      呼び出し元の create()/update()（ValueError を捕捉して flash）の
      既存経路にそのまま乗せられる（未捕捉例外による 500 を避ける）。

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
        # ユーザー向けの ValueError に正規化する
        raise ValueError('画像の処理中にエラーが発生しました。別の画像でお試しください。')


# ----------------------------------------------------------------------
# (6-2) 検証 + 最適化保存（アトミック保証）
# ----------------------------------------------------------------------
def _save_images(files: list) -> list[str]:
    """
    アップロードされた本文画像を検証・最適化・保存し、
    保存したファイル名のリストを返す。

    【セキュリティの多層防御】
    第 1 層: allowed_file() で拡張子チェック（_validate_image 内）
    第 2 層: filetype.guess() で MIME タイプチェック（_validate_image 内）
    第 3 層: UUID でファイル名を完全にランダム化
    （第 4 層: app.py で 30MB の容量制限）

    【最適化（このリビジョンの追加）】
    検証を通過した各ファイルは、原本をそのまま保存するのではなく
    _optimize_body_image_save() で縮小・再圧縮してから保存する。
    これにより一覧・詳細の読み込みが軽くなる。

    【アトミックな挙動（従来から維持）】
    途中の検証・処理エラーで例外が発生した場合、この関数内でそれまでに
    保存したファイルを _delete_images() で掃除してから例外を再送出する。
    「全ファイルの保存に成功したときだけファイルを残す」ことを保証するため、
    呼び出し側は従来どおり ValueError を捕捉するだけでよい。

    保存対象のファイル名は「保存を試みる直前」に filename_list へ登録する。
    こうすることで、_optimize_body_image_save() が途中まで書き込んで失敗した
    場合でも、その半端なファイルが確実に掃除対象に含まれる
    （_delete_images は存在チェック付きなので、未生成でも無害）。

    【処理の流れ】
      STEP 1. ファイルを 1 枚ずつ取り出す（未選択はスキップ）
      STEP 2. _validate_image() で拡張子・MIME を検証
      STEP 3. UUID + 元の拡張子でファイル名を生成し、掃除対象として登録
      STEP 4. _optimize_body_image_save() で縮小・再圧縮して保存
      STEP 5. 例外発生時 → 保存済みファイルを掃除してから例外を再送出
      STEP 6. 全成功 → 保存したファイル名のリストを返す

    @param files: request.files.getlist('img[]') で取得したファイルオブジェクトのリスト
    @return: 保存したファイル名のリスト
    @raises ValueError: 検証エラー・画像処理エラー時
    """
    filename_list = []

    try:
        for file in files:
            # --------------------------------------------------------
            # STEP 1. ファイルが選択されていない場合はスキップ
            # --------------------------------------------------------
            if not file or file.filename == '':
                continue

            # --------------------------------------------------------
            # STEP 2. 拡張子 + MIME 検証（失敗時は ValueError）
            # --------------------------------------------------------
            _validate_image(file)

            # 拡張子は検証済みの元ファイル名から直接取得する
            ext = '.' + file.filename.rsplit('.', 1)[1].lower()

            # --------------------------------------------------------
            # STEP 3. UUID でファイル名をランダム化し、掃除対象へ先行登録
            # --------------------------------------------------------
            filename  = f"{uuid.uuid4()}{ext}"
            filename_list.append(filename)
            save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)

            # --------------------------------------------------------
            # STEP 4. 縮小・再圧縮して保存
            # --------------------------------------------------------
            _optimize_body_image_save(file, save_path, ext)

    except Exception:
        # ------------------------------------------------------------
        # STEP 5. 途中まで保存したファイルをここで掃除する
        # ------------------------------------------------------------
        if filename_list:
            _delete_images(','.join(filename_list))
        raise

    # ------------------------------------------------------------------
    # STEP 6. 全成功: 保存したファイル名のリストを返す
    # ------------------------------------------------------------------
    return filename_list


# ----------------------------------------------------------------------
# (6-3) 実ファイルの物理削除
# ----------------------------------------------------------------------
def _delete_images(img_name_str: str) -> None:
    """
    post.img_name カラムの値（カンマ区切りファイル名）をもとに
    static/img/posts/ 以下の実ファイルを物理削除する。

    記事削除・画像更新時に呼ばれ、サーバー上の孤立ファイルを防ぐ。
    ファイルが存在しない場合はスキップする（エラーにしない）。
    サムネイル専用画像（thumbnail_img）も同じ static/img/posts/ 配下に
    保存されるため、この関数でそのまま削除できる。

    【バグ修正に伴う運用ルール】
    この関数は必ず「DB の commit が成功した後」に呼ぶこと。
    従来は commit 前に _delete_images() を呼んでいたため、
    commit が失敗すると「DB には記事が残っているのに画像だけ消えている」
    という復旧不能な不整合が発生し得た。
    commit 後の物理削除であれば、万一削除に失敗しても
    「孤立ファイルが残る」だけで済み、データは壊れない（安全側に倒す）。

    【処理の流れ】
      STEP 1. 引数が空なら何もしない
      STEP 2. カンマ区切りをファイル名ごとに分割
      STEP 3. 存在するファイルだけを os.remove() で削除

    @param img_name_str: post.img_name の値（例: "uuid1.jpg,uuid2.png"）
    """
    # STEP 1. 空チェック
    if not img_name_str:
        return

    # STEP 2〜3. 分割して 1 件ずつ削除
    for img_file in img_name_str.split(','):
        img_path = os.path.join(current_app.static_folder, 'img', 'posts', img_file.strip())
        if os.path.exists(img_path):
            os.remove(img_path)


# ----------------------------------------------------------------------
# (6-4) サムネイル専用画像を WebP 縮小版で保存
# ----------------------------------------------------------------------
def _save_thumbnail(file) -> str | None:
    """
    サムネイル専用にアップロードされた 1 枚の画像を検証し、
    幅 THUMBNAIL_MAX_WIDTH（既定 400px）の軽量な WebP に変換して保存する。
    保存したファイル名（.webp）を返す。ファイル未選択なら None を返す。

    【最適化の内容】
      ・拡張子 + MIME を検証（_validate_image）
      ・EXIF の向き情報を反映
      ・幅が上限を超える場合のみ、アスペクト比を保って縮小（拡大はしない）
      ・WebP へ変換して保存（透過は保持: RGB/RGBA のまま WebP 化）
    元がどの形式でも保存名は常に UUID + '.webp' になる。
    thumbnail_img カラムはこの軽量版ファイルを指す。

    【エラー方針】
      検証エラー・画像処理エラーはいずれも ValueError として送出する
      （呼び出し元 create()/update() は ValueError を捕捉して flash する）。
      途中まで書き込んだ WebP が残らないよう、失敗時は自分で掃除してから送出する。

    @param file: request.files.get('thumbnail_img') で取得したファイルオブジェクト
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
                （失敗時は本文画像を掃除してからリダイレクト）
      STEP 5. [POST] Post オブジェクトを作成してセッションに追加
      STEP 6. [POST] flush() で post.id を確定 → ハッシュタグを同期
      STEP 7. [POST] commit（失敗時は rollback + 保存済み画像を掃除）
      STEP 8. [GET]  ジャンル選択肢を生成して投稿フォームを表示
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック
    # ------------------------------------------------------------------
    # 管理者以外のユーザー（将来的なマルチユーザー対応時の保険）はトップへ
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

        # デフォルトサムネイル: フォームで 'none' が選ばれた場合は NULL（デフォルトサムネイルなし）
        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        # --------------------------------------------------------------
        # STEP 4. 本文画像の保存（検証 + 最適化）
        # --------------------------------------------------------------
        # _save_images() は検証・処理エラー時に ValueError を raise するので try/except で受ける
        try:
            filename_list = _save_images(request.files.getlist('img[]'))
        except ValueError as e:
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
        # 本文画像とは独立した 1 枚のサムネイルをアップロードできる。
        # 検証エラー時は、直前で保存した本文画像が孤立しないよう掃除してから戻る。
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
        # STEP 5. Post オブジェクトを作成してセッションに追加
        # --------------------------------------------------------------
        # updated_at は新規投稿時 NULL のまま（「まだ更新されていない」を明示）
        post = Post(
            title         = title,
            body          = body,
            user_id       = current_user.id,
            img_name      = img_name_str,
            default_thumb = selected_default_thumb,
            thumbnail_img = thumbnail_name,
            genre         = final_genre,
            is_published  = is_published,
            img_captions  = img_captions_str,
            updated_at    = None,
        )
        db.session.add(post)

        # --------------------------------------------------------------
        # STEP 6. flush で ID を確定してハッシュタグを同期
        # --------------------------------------------------------------
        # flush(): まだ commit せずに post.id だけを確定させる
        # ハッシュタグの中間テーブルに post_id を設定するために必要
        db.session.flush()

        # ハッシュタグの同期（入力文字列 → Hashtag オブジェクト → 中間テーブル登録）
        sync_hashtags(post, parse_hashtag_input(hashtag_input))

        # --------------------------------------------------------------
        # STEP 7. commit（失敗時は rollback + 保存済み画像を掃除）
        # --------------------------------------------------------------
        # 【バグ修正】commit 失敗時に保存済みファイルを掃除する
        # 画像ファイルは commit より先にディスク保存されるため、
        # commit が失敗した場合はそのままだと孤立ファイルが残る。
        # rollback 後に今回保存したファイル（本文画像・サムネイル）を
        # 削除して整合性を保つ。
        try:
            db.session.commit()  # ここで全変更を DB に書き込む
        except Exception:
            db.session.rollback()
            if img_name_str:
                _delete_images(img_name_str)
            if thumbnail_name:
                _delete_images(thumbnail_name)
            flash('投稿の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
            return redirect('/create')

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
      STEP 6. [POST] 更新日時をセットして commit
              （失敗時は rollback + 新規保存ファイルを掃除）
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
    #   C) 新画像なし + 削除フラグなし     → キャプションのみ更新（従来どおり）
    #
    # 【機能追加】パターン B: 既存画像の個別削除
    # update.html の各既存画像カードに hidden フィールド
    # keep_img_N（'1'=残す / '0'=削除予定）を持たせ、
    # ここで '0' の画像を除外して img_name / img_captions を再構築する。
    # 削除対象の実ファイルは old_img_name に積んでおき、
    # 差し替え時（パターン A）と同じ「commit 成功後に物理削除」の
    # 経路で処理する（DB とファイルの整合性ルールを一本化するため）。
    #
    # ※ パターン A（差し替え）が選ばれた場合、旧画像はどのみち
    #    全削除されるため、個別削除フラグは無視される（差し替えが優先）。
    files = request.files.getlist('img[]')
    old_img_name  = None   # commit 成功後に物理削除する画像（差し替え時: 旧全画像 / 個別削除時: 削除対象のみ）
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
        kept_captions = []   # 残す画像のキャプション（順番を kept_imgs と対応させる）
        removed_imgs  = []   # 削除予定の画像ファイル名

        for i, img in enumerate(existing_imgs, start=1):
            caption = request.form.get(f'img_caption_{i}', '').strip()

            # keep_img_N が '0' なら削除予定。
            # フィールド自体が送られてこない場合（JS 無効・旧テンプレート）は
            # デフォルト '1' として「残す」扱いにする（安全側・後方互換）。
            if request.form.get(f'keep_img_{i}', '1') == '0':
                removed_imgs.append(img)
            else:
                kept_imgs.append(img)
                kept_captions.append(caption)

        if removed_imgs:
            # 削除対象を commit 成功後の物理削除キューに積む
            old_img_name = ','.join(removed_imgs)

        # 残った画像だけで DB 上の参照を再構築する。
        # 全画像を削除した場合は None にして「画像なし記事」に戻す
        # （一覧・詳細ではサムネイルは thumbnail_img / default_thumb に
        #   自然にフォールバックする）。
        post.img_name     = ','.join(kept_imgs) if kept_imgs else None
        post.img_captions = '\t'.join(kept_captions) if kept_imgs else None

    # ------------------------------------------------------------------
    # STEP 5.5. サムネイル専用画像の更新
    # ------------------------------------------------------------------
    # 3 パターン:
    #   ・新しいサムネイルがアップロードされた → 差し替え（旧サムネイルは commit 後に削除）
    #   ・keep_thumbnail == '0'（削除ボタン ON）→ 現在のサムネイルを削除
    #   ・それ以外                               → 現状維持
    #
    # 新規サムネイルのアップロードが最優先。アップロードがあれば
    # keep_thumbnail フラグ（削除指定）は無視される（差し替え優先）。
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
    # STEP 6. 更新日時をセットして commit
    # ------------------------------------------------------------------
    # 更新日時を現在時刻（日本時間）に更新
    post.updated_at = datetime.now(pytz.timezone('Asia/Tokyo'))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # commit 失敗 → 今回新規保存したファイルを掃除（DB は旧状態のまま無傷）
        # 個別削除（パターン B）の場合、物理削除はまだ行っていないため
        # rollback だけで完全に元の状態に戻る（掃除対象なし）。
        if new_filenames:
            _delete_images(','.join(new_filenames))
        if new_thumbnail_saved:
            _delete_images(new_thumbnail_saved)
        flash('更新の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect(f'/{id}/update')

    # ------------------------------------------------------------------
    # STEP 7. commit 成功 → ここで初めて削除対象のファイルを物理削除する
    # ------------------------------------------------------------------
    # （本文画像: 差し替え時は旧全画像、個別削除時は削除予定の画像のみ）
    if old_img_name:
        _delete_images(old_img_name)
    # （サムネイル: 差し替え時 or 削除指定時の旧サムネイル）
    if old_thumbnail_name:
        _delete_images(old_thumbnail_name)

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

    POST メソッドのみ受け付ける（GET でアクセスできないようにする）
    → URL を直接叩いただけでは削除できない（CSRF トークンも必要）
    （CSRF トークンも必要）
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
    # 【バグ修正】画像ファイルの物理削除を DB commit 成功後に移動
    #
    # 従来は commit 前に _delete_images() を呼んでいたため、
    # commit が失敗すると「DB には記事が残っているのに画像だけ消えている」
    # という不整合が発生し得た。
    # 削除対象の画像名を退避してから DB 削除を commit し、
    # 成功した場合にのみ実ファイルを削除する。
    #
    # 本文画像（img_name）とサムネイル専用画像（thumbnail_img）は
    # どちらも static/img/posts/ 配下にあるため、まとめて退避する。
    files_to_delete = []
    if post.img_name:
        files_to_delete.append(post.img_name)
    if post.thumbnail_img:
        files_to_delete.append(post.thumbnail_img)
    img_name_to_delete = ','.join(files_to_delete) if files_to_delete else None

    # ------------------------------------------------------------------
    # STEP 3. ハッシュタグのリレーションをクリア + 孤立タグの削除予約
    # ------------------------------------------------------------------
    # ハッシュタグのリレーションを先にクリアしてから記事を削除する。
    # post.hashtags = [] にすることで中間テーブルの行が削除予約され、
    # その後 delete_orphaned_hashtags() で孤立タグ本体も削除できる。
    post.hashtags = []
    db.session.flush()  # 中間テーブルの削除をセッションに反映させてから孤立判定する

    # 孤立ハッシュタグを削除（commit 前にまとめてセッションに乗せる）
    delete_orphaned_hashtags()

    # ------------------------------------------------------------------
    # STEP 4. 記事を削除予約して commit
    # ------------------------------------------------------------------
    db.session.delete(post)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('削除中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 5. commit 成功 → ここで初めて関連画像ファイルを物理削除する
    # ------------------------------------------------------------------
    _delete_images(img_name_to_delete)

    # ------------------------------------------------------------------
    # STEP 6. 削除後のリダイレクト先決定（Open Redirect 対策）
    # ------------------------------------------------------------------
    # 単純に return redirect(request.referrer) とすると
    # 攻撃者が referer ヘッダを偽造して外部サイトへリダイレクトさせる
    # Open Redirect 攻撃が可能になる。
    #
    # 対策: scheme（http/https）と netloc（ドメイン名）が
    #       リクエスト元と同じオリジンかどうかを検証してからリダイレクト。
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

    【今回の改善: 全件一括ロード → サーバーサイドページネーションに統一】
    従来この関数は自分の投稿を Post.query...all() で「全件」取得し、
    テンプレート側で全カードを描画してから JavaScript で先頭 4 件以外を
    display:none で隠す「もっと見る」方式だった。
    しかしトップページ（views/blog.py の index）は既に paginate() による
    サーバーサイドページネーションへ移行しており、マイページだけ旧方式が
    残っていた。投稿数が増えるほど

      ・DB から全 Post を取得する（メモリ肥大）
      ・全カード分の HTML を描画して送信する（DOM 肥大・転送量増）

    という無駄が大きくなる。そこで index と同じく paginate() に統一し、
    1 ページ POSTS_PER_PAGE 件（= 4 件）だけを取得・描画するように変更した。

    さらに、記事カード（_macros.html の post_card）はハッシュタグバッジ
    （post.hashtags）を参照するため、index と同様に
    selectinload(Post.hashtags) を付与して N+1 クエリを防ぐ。
    （Post.hashtags はモデル定義で lazy='selectin' 済みだが、
      呼び出し側でも明示して index とロード戦略をそろえる）

    【総投稿数の表示について】
    ページネーション後の posts は「現在ページ分」だけなので、
    プロフィール欄の「これまでの総投稿数」は pagination.total（全件数）を
    total_count としてテンプレートへ渡して表示する。
    （旧テンプレートは posts|length で数えていたが、ページネーション後は
      それだと 1 ページ分の件数になってしまうため total を使う）

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
        flash('ニックネームを更新しました！' if new_nickname else 'ニックネームを解除しました。', 'info')
        db.session.commit()
        return redirect('/mypage')

    # ------------------------------------------------------------------
    # STEP 3. GET: 自分の記事をサーバーサイドページネーションで取得
    # ------------------------------------------------------------------
    # index（views/blog.py）と同じ方式にそろえる:
    #   ・?page= でページ番号を受け取る（未指定は 1）
    #   ・options(db.selectinload(Post.hashtags)) でタグを一括ロードし N+1 を防止
    #   ・created_at の降順（新しい記事が先頭）
    #   ・per_page=POSTS_PER_PAGE、error_out=False
    #     （範囲外のページ番号でも 404 にせず空リストを返す）
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
    # DB クエリで DISTINCT なジャンル名を取得し、
    # Python 側で set → sorted で整理する。
    # '未分類' は特別扱いで末尾に移動する。
    #
    # ※ ここはページネーションとは独立に「自分の全記事」からジャンルを集計する。
    #   現在ページの user_posts に依存させると、ページを移動するたびに
    #   ジャンル一覧が変わってしまうため、専用クエリで全体から求めている。
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