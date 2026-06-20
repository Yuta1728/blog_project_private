# views/admin.py
#
# 【役割】
# 管理者専用ページ（ログイン必須）のルートとロジックを担うビューファイル。
#
# 担当機能:
#   /create          → 新規記事投稿
#   /<id>/update     → 記事編集
#   /<id>/delete     → 記事削除
#   /mypage          → マイページ（投稿一覧・ニックネーム変更）

from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user, login_required
from datetime import datetime
from urllib.parse import urlparse  # Open Redirect 対策のための URL パース
import os
import uuid        # 画像ファイル名を UUID でユニーク化するため
import pytz
import filetype    # ファイルの実際の MIME タイプを判定するライブラリ（拡張子偽装の検出）
from werkzeug.utils import secure_filename  # アップロードファイル名のサニタイズ
from extensions import db
from models import Post, Hashtag
from constants import DEFAULT_GENRES
import config

admin_bp = Blueprint('admin', __name__)

# ===================================================================
# ファイルアップロード検証用ホワイトリスト
# ===================================================================
# 拡張子チェック（第 1 層の防御）: ファイル名の末尾を確認
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
# MIME タイプチェック（第 2 層の防御）: ファイルの先頭バイトを読んで実際の形式を確認
# 拡張子を偽装した悪意あるファイル（例: malware.exe を image.jpg にリネーム）を弾く
ALLOWED_MIME_TYPES  = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


# ===================================================================
# ファイル検証ヘルパー
# ===================================================================
def allowed_file(filename: str) -> bool:
    """
    ファイル名の拡張子がホワイトリストに含まれているかチェックする。
    '.' を含み、かつ最後の '.' 以降が許可リストにあれば True を返す。
    （例: 'photo.jpg' → True, 'script.php' → False）
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ===================================================================
# ハッシュタグ関連ヘルパー
# ===================================================================

def parse_hashtag_input(raw: str) -> list[str]:
    """
    フォームから受け取ったハッシュタグ入力文字列を
    「# なしのタグ名リスト」に変換する。

    対応する入力形式（ユーザーにとって入力しやすい形式を幅広く受け付ける）:
      "#Flask #Python ブログ" → ['Flask', 'Python', 'ブログ']
      "Flask,Python,ブログ"   → ['Flask', 'Python', 'ブログ']
      "Flask　Python"         → ['Flask', 'Python']  （全角スペースも対応）

    処理の流れ:
      1. 全角スペース・半角スペース・カンマ・読点 で分割
      2. 先頭の '#' を除去
      3. 空文字列・50文字超・重複 を排除

    @param raw: フォームの hashtag_input フィールドの値
    @return: タグ名文字列のリスト（'#' なし）
    """
    import re
    raw = raw.strip()
    if not raw:
        return []

    # 区切り文字: 半角スペース・全角スペース・カンマ・読点 のいずれか 1 文字以上
    tokens = re.split(r'[\s\u3000,、]+', raw)

    names, seen = [], set()
    for token in tokens:
        name = token.lstrip('#').strip()  # 先頭の # を除去
        if name and name not in seen and len(name) <= 50:
            names.append(name)
            seen.add(name)  # 重複チェック用セットに追加

    return names


def sync_hashtags(post: Post, tag_names: list[str]) -> None:
    """
    post.hashtags リレーションを tag_names リストと同期する。

    【なぜ「同期」が必要か】
    単純に post.hashtags = [new_tag1, new_tag2, ...] と上書きすると
    編集前に付いていたタグが外れ、新しいタグが追加されるが、
    すでに DB に存在する同名タグが重複登録されるリスクがある。
    この関数では「既存タグがあれば再利用、なければ新規作成」を行う。

    【処理の流れ】
    1. tag_names の各タグ名を Hashtag テーブルで検索
    2. 存在すれば既存の Hashtag オブジェクトを使う
    3. 存在しなければ新規 Hashtag を作成して db.session.add()
    4. post.hashtags を新しいリストで上書き
       （SQLAlchemy が差分を検出して post_hashtags 中間テーブルを更新する）

    @param post: 同期対象の Post オブジェクト
    @param tag_names: 新しいタグ名リスト（'#' なし）
    """
    new_tags = []
    for name in tag_names:
        tag = Hashtag.query.filter_by(name=name).first()
        if not tag:
            # DB に存在しない新タグ → 新規作成
            tag = Hashtag(name=name)
            db.session.add(tag)
        new_tags.append(tag)

    post.hashtags = new_tags  # リレーションを上書き（中間テーブルの更新は SQLAlchemy が自動処理）


# ===================================================================
# 画像キャプション関連ヘルパー
# ===================================================================

def parse_img_captions(file_count: int) -> list[str]:
    """
    フォームから各画像のキャプションを取得してリストにまとめる。

    フォームの入力フィールド名の命名規則:
      img_caption_1, img_caption_2, img_caption_3, ...
    （create.html / update.html の JavaScript で動的に生成される）

    @param file_count: アップロードされた画像の枚数
    @return: キャプション文字列のリスト（インデックスが画像の順番と対応）
    """
    captions = []
    for i in range(1, file_count + 1):
        caption = request.form.get(f'img_caption_{i}', '').strip()
        captions.append(caption)
    return captions


# ===================================================================
# ジャンルリスト生成ヘルパー
# ===================================================================

def _get_genre_list(user_id: int, current_genre: str | None = None) -> list[str]:
    """
    投稿フォームのジャンル選択肢リストを生成する。

    生成ロジック:
      1. DEFAULT_GENRES（constants.py のプリセット）を取得
      2. このユーザーが既存記事で使っているジャンルを DB から取得
      3. 1 + 2 の和集合を取る（重複は除去）
      4. 編集中の記事のジャンルが上記にない場合も必ず含める
      5. DEFAULT_GENRES の順番を優先して並べ替え

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

    all_genres_set.discard('未分類')  # '未分類' は select の先頭に固定で置くので除外

    # DEFAULT_GENRES の順番を優先してソート（プリセット外のジャンルは末尾）
    return sorted(
        list(all_genres_set),
        key=lambda x: DEFAULT_GENRES.index(x) if x in DEFAULT_GENRES else len(DEFAULT_GENRES) + hash(x)
    )


# ===================================================================
# 画像ファイル操作ヘルパー
# ===================================================================

def _save_images(files: list) -> list[str]:
    """
    アップロードされた画像ファイルを検証・保存し、
    保存したファイル名のリストを返す。

    【セキュリティの多層防御】
    第 1 層: allowed_file() で拡張子チェック
    第 2 層: filetype.guess() で MIME タイプチェック（ファイルの中身を確認）
    第 3 層: secure_filename() でファイル名のサニタイズ（パストラバーサル対策）
    第 4 層: UUID でファイル名をランダム化（既存ファイルの上書き防止、URL 推測防止）
    （第 5 層: app.py で 30MB の容量制限）

    @param files: request.files.getlist('img[]') で取得したファイルオブジェクトのリスト
    @return: 保存したファイル名のリスト
    @raises ValueError: 検証エラー時（拡張子不正・MIME タイプ不正）
    """
    filename_list = []
    for file in files:
        # ファイルが選択されていない場合はスキップ
        if not file or file.filename == '':
            continue

        # --- 第 1 層: 拡張子チェック ---
        if not allowed_file(file.filename):
            raise ValueError('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)')

        # ファイル名のサニタイズ（第 3 層）
        # secure_filename() は '../../../etc/passwd' のような危険なパスを除去する
        safe_filename = secure_filename(file.filename)
        ext = os.path.splitext(safe_filename)[1]  # 拡張子部分（例: ".jpg"）を取得

        # --- 第 2 層: MIME タイプチェック ---
        # ファイルの先頭 2048 バイトを読み込んでマジックナンバーで実際の形式を判定
        header = file.stream.read(2048)
        file.stream.seek(0)  # ストリーム位置をリセット（後で save() が読めるように）
        kind = filetype.guess(header)
        if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
            raise ValueError('ファイルの内容が不正です。画像偽装の可能性があります。')

        # --- 第 4 層: UUID でファイル名をランダム化 ---
        # uuid4() は 128 bit のランダムな識別子を生成する
        # これにより元のファイル名・アップロード順が URL から推測できなくなる
        filename  = f"{uuid.uuid4()}{ext}"
        save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)
        file.save(save_path)
        filename_list.append(filename)

    return filename_list


def _delete_images(img_name_str: str) -> None:
    """
    post.img_name カラムの値（カンマ区切りファイル名）をもとに
    static/img/posts/ 以下の実ファイルを物理削除する。

    記事削除・画像更新時に呼ばれ、サーバー上の孤立ファイルを防ぐ。
    ファイルが存在しない場合はスキップする（エラーにしない）。

    @param img_name_str: post.img_name の値（例: "uuid1.jpg,uuid2.png"）
    """
    if not img_name_str:
        return
    for img_file in img_name_str.split(','):
        img_path = os.path.join(current_app.static_folder, 'img', 'posts', img_file.strip())
        if os.path.exists(img_path):
            os.remove(img_path)


# ===================================================================
# 新規投稿
# ===================================================================

@admin_bp.route('/create', methods=['GET', 'POST'])
@login_required  # 未ログイン時は login_manager.login_view へリダイレクト
def create():
    # 管理者以外のユーザー（将来的なマルチユーザー対応時の保険）はトップへ
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        # --- フォーム入力値の取得 ---
        title          = request.form.get('title', '').strip()
        body           = request.form.get('body', '').strip()
        selected_genre = request.form.get('genre_select')       # プリセットから選択したジャンル
        new_genre      = request.form.get('genre_new', '').strip()  # 新規入力したジャンル名
        hashtag_input  = request.form.get('hashtag_input', '')

        # --- バリデーション ---
        if not title or not body:
            flash('タイトルと内容はどちらも入力必須です。', 'danger')
            return redirect('/create')

        # ジャンルの優先順位: 新規入力 > プリセット選択 > デフォルト（未分類）
        final_genre = new_genre if new_genre else (selected_genre or '未分類')

        # --- デフォルトサムネイルの設定 ---
        # フォームで 'none' が選ばれた場合は NULL（サムネイル画像なし）
        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        # --- 画像の保存 ---
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

        # --- DB への保存 ---
        post = Post(
            title         = title,
            body          = body,
            user_id       = current_user.id,
            img_name      = img_name_str,
            default_thumb = selected_default_thumb,
            genre         = final_genre,
            is_published  = is_published,
            img_captions  = img_captions_str,
        )
        db.session.add(post)

        # flush(): まだ commit せずに post.id だけを確定させる
        # ハッシュタグの中間テーブルに post_id を設定するために必要
        db.session.flush()

        # ハッシュタグの同期（入力文字列 → Hashtag オブジェクト → 中間テーブル登録）
        sync_hashtags(post, parse_hashtag_input(hashtag_input))

        db.session.commit()  # ここで全変更を DB に書き込む
        return redirect('/')

    # GET: 投稿フォームを表示
    genres = _get_genre_list(current_user.id)
    return render_template('create.html', genres=genres)


# ===================================================================
# 記事編集
# ===================================================================

@admin_bp.route('/<int:id>/update', methods=['GET', 'POST'])
@login_required
def update(id):
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    # 記事の取得と権限チェック
    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    if request.method == 'GET':
        # --- 編集フォームの初期値を設定 ---
        genres = _get_genre_list(current_user.id, post.genre)

        # 既存ハッシュタグを "#Flask #Python" 形式の文字列に変換
        # （フォームの value に設定してユーザーが編集しやすいように）
        existing_hashtag_str = ' '.join(f'#{t.name}' for t in post.hashtags)

        # 既存キャプションをタブ区切りから配列に変換（テンプレートでインデックスアクセスするため）
        existing_captions = post.img_captions.split('\t') if post.img_captions else []

        return render_template('update.html', post=post, genres=genres,
                               existing_hashtag_str=existing_hashtag_str,
                               existing_captions=existing_captions)

    # --- POST: 記事の更新処理 ---
    title = request.form.get('title', '').strip()
    body  = request.form.get('body', '').strip()
    if not title or not body:
        flash('タイトルと内容はどちらも入力必須です。', 'danger')
        return redirect(f'/{id}/update')

    post.title = title
    post.body  = body

    # デフォルトサムネイルの更新
    selected_default_thumb = request.form.get('default_thumb_select')
    post.default_thumb = None if selected_default_thumb == 'none' else selected_default_thumb

    # 公開設定の更新（フォームで値が送られた場合のみ更新する）
    is_published_form = request.form.get('is_published')
    if is_published_form is not None:
        post.is_published = (is_published_form == 'true')

    # ジャンルの更新
    new_genre      = request.form.get('genre_new', '').strip()
    selected_genre = request.form.get('genre_select')
    post.genre = new_genre if new_genre else (selected_genre or '未分類')

    # ハッシュタグの同期（フォームの最新入力で上書き）
    sync_hashtags(post, parse_hashtag_input(request.form.get('hashtag_input', '')))

    # --- 画像の更新 ---
    files = request.files.getlist('img[]')
    if files and files[0].filename != '':
        # 新しい画像が選択された場合 → 旧画像を削除して新画像で置き換え
        try:
            filename_list = _save_images(files)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(f'/{id}/update')

        _delete_images(post.img_name)       # 旧画像ファイルを物理削除
        post.img_name = ','.join(filename_list)
        captions = parse_img_captions(len(filename_list))
        post.img_captions = '\t'.join(captions) if captions else None

    else:
        # 画像変更なし → キャプションのみ更新する
        # 既存画像の枚数分だけフォームを読んでキャプションを更新
        if post.img_name:
            existing_imgs = post.img_name.split(',')
            captions = []
            for i in range(1, len(existing_imgs) + 1):
                captions.append(request.form.get(f'img_caption_{i}', '').strip())
            post.img_captions = '\t'.join(captions)

    # 更新日時を現在時刻（日本時間）に更新
    post.updated_at = datetime.now(pytz.timezone('Asia/Tokyo'))
    db.session.commit()

    return redirect(f'/{id}/detail')


# ===================================================================
# 記事削除
# ===================================================================

@admin_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    # POST メソッドのみ受け付ける（GET でアクセスできないようにする）
    # → URL を直接叩いただけでは削除できない（CSRF トークンも必要）

    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    # 関連する画像ファイルをサーバーから物理削除（DB 削除前に行う）
    _delete_images(post.img_name)

    # DB から記事を削除（post_hashtags 中間テーブルのレコードも CASCADE で削除される）
    db.session.delete(post)
    db.session.commit()

    # -------------------------------------------------------------------
    # 削除後のリダイレクト先決定（Open Redirect 対策）
    #
    # 単純に return redirect(request.referrer) とすると
    # 攻撃者が referer ヘッダを偽造して外部サイトへリダイレクトさせる
    # Open Redirect 攻撃が可能になる。
    #
    # 対策: scheme（http/https）と netloc（ドメイン名）が
    #       リクエスト元と同じオリジンかどうかを検証してからリダイレクト。
    # -------------------------------------------------------------------
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


# ===================================================================
# マイページ
# ===================================================================

@admin_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        # --- ニックネーム変更処理 ---
        new_nickname = request.form.get('nickname', '').strip()
        # 空欄の場合は None にして「ニックネームなし」に戻す
        current_user.nickname = new_nickname or None
        flash('ニックネームを更新しました！' if new_nickname else 'ニックネームを解除しました。', 'info')
        db.session.commit()
        return redirect('/mypage')

    # --- GET: マイページの表示 ---

    # マイページ内でも絞り込み・検索ができる（URL クエリパラメータを使用）
    search_word    = request.args.get('search')
    selected_genre = request.args.get('genre')

    # 自分の記事だけを対象にクエリを構築
    posts_query = Post.query.filter(Post.user_id == current_user.id)

    # キーワード検索（タイトルに含まれているか）
    if search_word and search_word.strip():
        posts_query = posts_query.filter(Post.title.contains(search_word.strip()))

    # ジャンル絞り込み
    if selected_genre:
        posts_query = posts_query.filter(Post.genre == selected_genre)

    # 作成日時の降順（新しい記事が先頭）
    user_posts = posts_query.order_by(Post.created_at.desc()).all()

    # -------------------------------------------------------------------
    # 使用ジャンル一覧の生成（サイドバー表示用）
    #
    # DB クエリで DISTINCT なジャンル名を取得し、
    # Python 側で set → sorted で整理する。
    # '未分類' は特別扱いで末尾に移動する。
    # -------------------------------------------------------------------
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

    return render_template(
        'mypage.html',
        posts          = user_posts,
        user_genres    = user_genres,
        selected_genre = selected_genre,
        search_word    = search_word,
    )