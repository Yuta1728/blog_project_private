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
#   [1] 定数定義（ファイルアップロード検証用ホワイトリスト）
#   [2] ファイル検証ヘルパー
#        (2-1) allowed_file()            : 拡張子チェック
#   [3] ハッシュタグ関連ヘルパー
#        (3-1) parse_hashtag_input()     : 入力文字列 → タグ名リスト
#        (3-2) sync_hashtags()           : Post とタグリストの同期
#        (3-3) delete_orphaned_hashtags(): 孤立タグの一括削除
#   [4] 画像キャプション関連ヘルパー
#        (4-1) parse_img_captions()      : フォーム → キャプションリスト
#   [5] ジャンルリスト生成ヘルパー
#        (5-1) _get_genre_list()         : 投稿フォームのジャンル選択肢
#   [6] 画像ファイル操作ヘルパー
#        (6-1) _save_images()            : 検証 + 保存（アトミック保証）
#        (6-2) _delete_images()          : 実ファイルの物理削除
#   [7] create()  : 新規投稿ビュー
#   [8] update()  : 記事編集ビュー
#   [9] delete()  : 記事削除ビュー
#   [10] mypage() : マイページビュー
#
# 【処理フロー図（投稿・編集・削除に共通する整合性ルール）】
#
#   画像ファイルと DB の不整合を防ぐため、次の順序を厳守している:
#
#   新規保存: _save_images()（全成功 or 全掃除のアトミック動作）
#        │
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
from PIL import Image
import pytz
import filetype    # ファイルの実際の MIME タイプを判定するライブラリ（拡張子偽装の検出）
from extensions import db
from models import Post, Hashtag
from constants import DEFAULT_GENRES
import config

admin_bp = Blueprint('admin', __name__)


# ======================================================================
# [1] 定数定義: ファイルアップロード検証用ホワイトリスト
# ======================================================================

# 拡張子チェック（第 1 層の防御）: ファイル名の末尾を確認
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# MIME タイプチェック（第 2 層の防御）: ファイルの先頭バイトを読んで実際の形式を確認
# 拡張子を偽装した悪意あるファイル（例: malware.exe を image.jpg にリネーム）を弾く
ALLOWED_MIME_TYPES  = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


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
    # la STEP 6. 並べ替えて返す
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
# (6-1) 検証 + 保存（アトミック保証）
# ----------------------------------------------------------------------
def _save_images(files: list) -> list[str]:
    """
    アップロードされた画像ファイルを検証・保存し、
    保存したファイル名のリストを返す。

    【セキュリティの多層防御】
    第 1 層: allowed_file() で拡張子チェック
    第 2 層: filetype.guess() で MIME タイプチェック（ファイルの中身を確認）
    第 3 層: UUID でファイル名を完全にランダム化
    （第 4 層: app.py で 30MB の容量制限）

    【バグ修正】途中の検証エラーで保存済みファイルが孤立する問題を解消
    従来は「1 枚ずつ検証 → 保存」をループしていたため、
    例えば 3 枚中 3 枚目で ValueError が発生すると、
    1〜2 枚目はすでにディスク保存済みのまま例外で処理が中断し、
    どの記事からも参照されない孤立ファイルとして残っていた。
    （呼び出し側の create() / update() は例外を捕捉して
      リダイレクトするだけなので、掃除する機会がなかった）

    対策: 例外発生時に、この関数内でそれまでに保存した
    ファイルを _delete_images() で掃除してから例外を再送出する。
    これにより「この関数は全ファイルの保存に成功したときだけ
    ファイルを残す」というアトミックな挙動が保証され、
    呼び出し側は従来どおり ValueError を捕捉するだけでよい。

    ※ ValueError（検証エラー）だけでなく Exception 全般を対象にするのは、
       file.save() がディスクフル等で OSError を送出した場合にも
       同様に途中保存分が孤立し得るため。掃除後は元の例外を
       そのまま re-raise するので、呼び出し側の挙動は変わらない。

    【処理の流れ】
      STEP 1. ファイルを 1 枚ずつ取り出す（未選択はスキップ）
      STEP 2. 【第 1 層】拡張子チェック → 不正なら ValueError
      STEP 3. 【第 2 層】先頭バイトから MIME タイプを判定 → 不正なら ValueError
      STEP 4. 【第 3 層】UUID + 元の拡張子でファイル名を生成して保存
      STEP 5. 例外発生時 → 保存済みファイルを掃除してから例外を再送出
      STEP 6. 全成功 → 保存したファイル名のリストを返す

    @param files: request.files.getlist('img[]') で取得したファイルオブジェクトのリスト
    @return: 保存したファイル名のリスト
    @raises ValueError: 検証エラー時（拡張子不正・MIME タイプ不正）
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
            # STEP 2. 【第 1 層】拡張子チェック
            # --------------------------------------------------------
            if not allowed_file(file.filename):
                raise ValueError('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)')

            # 拡張子は検証済みの元ファイル名から直接取得する
            ext = '.' + file.filename.rsplit('.', 1)[1].lower()

            # --------------------------------------------------------
            # STEP 3. 【第 2 層】MIME タイプチェック
            # --------------------------------------------------------
            header = file.stream.read(2048)
            file.stream.seek(0)  # ストリーム位置をリセット（後で save() が読めるように）
            kind = filetype.guess(header)
            if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
                raise ValueError('ファイルの内容が不正です。画像偽装の可能性があります。')

            # --------------------------------------------------------
            # STEP 4. 【第 3 層】UUID でファイル名をランダム化して保存 
            # --------------------------------------------------------
            filename  = f"{uuid.uuid4()}{ext}"
            save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)
            file.save(save_path)
            filename_list.append(filename)

    except Exception:
        # ------------------------------------------------------------
        # STEP 5. 【バグ修正】途中まで保存したファイルをここで掃除する
        # ------------------------------------------------------------
        # filename_list には「保存に成功したファイル名」だけが
        # 入っているので、それらを削除すれば孤立ファイルは残らない。
        # 掃除後に元の例外を再送出し、エラー通知は呼び出し側に委ねる。
        if filename_list:
            _delete_images(','.join(filename_list))
        raise

    # ------------------------------------------------------------------
    # STEP 6. 全成功: 保存したファイル名のリストを返す
    # ------------------------------------------------------------------
    return filename_list


# ----------------------------------------------------------------------
# (6-2) 実ファイルの物理削除
# ----------------------------------------------------------------------
def _delete_images(img_name_str: str) -> None:
    """
    post.img_name カラムの値（カンマ区切りファイル名）をもとに
    static/img/posts/ 以下の実ファイルを物理削除する。

    記事削除・画像更新時に呼ばれ、サーバー上の孤立ファイルを防ぐ。
    ファイルが存在しない場合はスキップする（エラーにしない）。

    【バグ修正に伴う運用ルール】
    この関数は必ず「DB の commit が成功した後」に呼ぶこと。
    従来は commit 前に物理削除していたため、commit が失敗すると
    「DB には記事が残っているのに画像だけ消えている」
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
      STEP 4. [POST] 画像を検証・保存（失敗時はフラッシュしてリダイレクト）
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

        # デフォルトサムネイル: フォームで 'none' が選ばれた場合は NULL（サムネイル画像なし）
        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        # --------------------------------------------------------------
        # STEP 4. 画像の保存
        # --------------------------------------------------------------
        # _save_images() は検証エラー時に ValueError を raise するので try/except で受ける
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
        # rollback 後に今回保存したファイルを削除して整合性を保つ。
        try:
            db.session.commit()  # ここで全変更を DB に書き込む
        except Exception:
            db.session.rollback()
            if img_name_str:
                _delete_images(img_name_str)
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
      STEP 5. [POST] 画像の更新（3 パターン: A 差し替え / B 個別削除 / C キャプションのみ）
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
    # STEP 5. 画像の更新
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
        # (5-A) パターン A: 画像の全差し替え
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
        # （一覧・詳細ではデフォルトサムネイル表示に自然にフォールバックする）。
        post.img_name     = ','.join(kept_imgs) if kept_imgs else None
        post.img_captions = '\t'.join(kept_captions) if kept_imgs else None

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
        flash('更新の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect(f'/{id}/update')

    # ------------------------------------------------------------------
    # STEP 7. commit 成功 → ここで初めて削除対象のファイルを物理削除する
    # ------------------------------------------------------------------
    # （差し替え時は旧全画像、個別削除時は削除予定の画像のみ）
    if old_img_name:
        _delete_images(old_img_name)

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
    # STEP 2. 削除対象の画像名を退避
    # ------------------------------------------------------------------
    # 【バグ修正】画像ファイルの物理削除を DB commit 成功後に移動
    #
    # 従来は commit 前に _delete_images() を呼んでいたため、
    # commit が失敗すると「DB には記事が残っているのに画像だけ消えている」
    # という不整合が発生し得た。
    # 削除対象の画像名を退避してから DB 削除を commit し、
    # 成功した場合にのみ実ファイルを削除する。
    img_name_to_delete = post.img_name  # commit 成功後に物理削除するため退避

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

    【処理の流れ】
      STEP 1. 管理者チェック
      STEP 2. [POST] ニックネームを更新して commit → マイページへリダイレクト
      STEP 3. [GET]  URL クエリパラメータ（search / genre）を取得
      STEP 4. [GET]  自分の記事を対象にクエリを構築・絞り込み
      STEP 5. [GET]  使用ジャンル一覧を生成（'未分類' は末尾へ）
      STEP 6. [GET]  mypage.html をレンダリング
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
    # STEP 3. GET: URL クエリパラメータの取得
    # ------------------------------------------------------------------
    # マイページ内でも絞り込み・検索ができる（URL クエリパラメータを使用）
    search_word    = request.args.get('search')
    selected_genre = request.args.get('genre')

    # ------------------------------------------------------------------
    # STEP 4. 自分の記事だけを対象にクエリを構築・絞り込み
    # ------------------------------------------------------------------
    posts_query = Post.query.filter(Post.user_id == current_user.id)

    # (4-1) キーワード検索（タイトルに含まれているか）
    if search_word and search_word.strip():
        posts_query = posts_query.filter(Post.title.contains(search_word.strip()))

    # (4-2) ジャンル絞り込み
    if selected_genre:
        posts_query = posts_query.filter(Post.genre == selected_genre)

    # (4-3) 作成日時の降順（新しい記事が先頭）で取得
    user_posts = posts_query.order_by(Post.created_at.desc()).all()

    # ------------------------------------------------------------------
    # STEP 5. 使用ジャンル一覧の生成（サイドバー表示用）
    # ------------------------------------------------------------------
    # DB クエリで DISTINCT なジャンル名を取得し、
    # Python 側で set → sorted で整理する。
    # '未分類' は特別扱いで末尾に移動する。
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
    # STEP 6. テンプレートのレンダリング
    # ------------------------------------------------------------------
    return render_template(
        'mypage.html',
        posts          = user_posts,
        user_genres    = user_genres,
        selected_genre = selected_genre,
        search_word    = search_word,
    )
