# views/admin.py
from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user, login_required
from datetime import datetime
from urllib.parse import urlparse
import os
import uuid
import pytz
import filetype
from werkzeug.utils import secure_filename
from extensions import db
from models import Post, Hashtag
from constants import DEFAULT_GENRES
import config

admin_bp = Blueprint('admin', __name__)

# --- ファイル検証用ホワイトリスト ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIME_TYPES  = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


def allowed_file(filename: str) -> bool:
    """拡張子がホワイトリストに含まれているかチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ===== ハッシュタグ用ヘルパー =====

def parse_hashtag_input(raw: str) -> list[str]:
    """
    フォームから受け取った文字列をハッシュタグ名リストに変換する。
    入力例: "#Flask #Python ブログ" → ['Flask', 'Python', 'ブログ']
    """
    import re
    raw = raw.strip()
    if not raw:
        return []
    tokens = re.split(r'[\s\u3000,、]+', raw)
    names, seen = [], set()
    for token in tokens:
        name = token.lstrip('#').strip()
        if name and name not in seen and len(name) <= 50:
            names.append(name)
            seen.add(name)
    return names


def sync_hashtags(post: Post, tag_names: list[str]) -> None:
    """
    post.hashtags を tag_names と同期する。
    既存タグは使い回し、Hashtag テーブルに重複を作らない。
    """
    new_tags = []
    for name in tag_names:
        tag = Hashtag.query.filter_by(name=name).first()
        if not tag:
            tag = Hashtag(name=name)
            db.session.add(tag)
        new_tags.append(tag)
    post.hashtags = new_tags


# ===== 画像キャプション用ヘルパー =====

def parse_img_captions(file_count: int) -> list[str]:
    """
    フォームから img_caption_1, img_caption_2 ... を受け取りリストにする。
    [変更] 引数を files リストではなく件数（int）に変更し、
    request への直接依存を最小化した。
    """
    captions = []
    for i in range(1, file_count + 1):
        caption = request.form.get(f'img_caption_{i}', '').strip()
        captions.append(caption)
    return captions


# ===== ジャンルリスト取得ヘルパー =====

def _get_genre_list(user_id: int, current_genre: str | None = None) -> list[str]:
    existing = (
        db.session.query(Post.genre)
        .filter(Post.user_id == user_id, Post.genre != '未分類',
                Post.genre != None, Post.genre != '')
        .distinct()
        .all()
    )
    user_genres_list = [g[0] for g in existing]

    all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)
    if current_genre:
        all_genres_set.add(current_genre)
    all_genres_set.discard('未分類')

    return sorted(
        list(all_genres_set),
        key=lambda x: DEFAULT_GENRES.index(x) if x in DEFAULT_GENRES else len(DEFAULT_GENRES) + hash(x)
    )


# ===== 画像保存共通処理 =====

def _save_images(files: list) -> list[str]:
    """
    アップロードファイルを検証・保存し、保存したファイル名リストを返す。
    検証エラー時は ValueError を raise する。
    """
    filename_list = []
    for file in files:
        if not file or file.filename == '':
            continue

        if not allowed_file(file.filename):
            raise ValueError('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)')

        safe_filename = secure_filename(file.filename)
        ext = os.path.splitext(safe_filename)[1]

        header = file.stream.read(2048)
        file.stream.seek(0)

        kind = filetype.guess(header)
        if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
            raise ValueError('ファイルの内容が不正です。画像偽装の可能性があります。')

        filename  = f"{uuid.uuid4()}{ext}"
        save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)
        file.save(save_path)
        filename_list.append(filename)

    return filename_list


def _delete_images(img_name_str: str) -> None:
    """img_name カラムの値からファイルを物理削除する"""
    if not img_name_str:
        return
    for img_file in img_name_str.split(','):
        img_path = os.path.join(current_app.static_folder, 'img', 'posts', img_file.strip())
        if os.path.exists(img_path):
            os.remove(img_path)


# ===== 新規投稿 =====

@admin_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        title         = request.form.get('title', '').strip()
        body          = request.form.get('body', '').strip()
        selected_genre = request.form.get('genre_select')
        new_genre      = request.form.get('genre_new', '').strip()
        hashtag_input  = request.form.get('hashtag_input', '')

        if not title or not body:
            flash('タイトルと内容はどちらも入力必須です。', 'danger')
            return redirect('/create')

        final_genre = new_genre if new_genre else (selected_genre or '未分類')

        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        # 画像保存（共通ヘルパーに委譲）
        try:
            filename_list = _save_images(request.files.getlist('img[]'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect('/create')

        img_name_str     = ','.join(filename_list) if filename_list else None
        captions         = parse_img_captions(len(filename_list))
        img_captions_str = '\t'.join(captions) if captions else None

        is_published = request.form.get('is_published') == 'true'

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
        db.session.flush()  # post.id を確定させてからハッシュタグを紐付け

        sync_hashtags(post, parse_hashtag_input(hashtag_input))
        db.session.commit()
        return redirect('/')

    genres = _get_genre_list(current_user.id)
    return render_template('create.html', genres=genres)


# ===== 編集 =====

@admin_bp.route('/<int:id>/update', methods=['GET', 'POST'])
@login_required
def update(id):
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    if request.method == 'GET':
        genres               = _get_genre_list(current_user.id, post.genre)
        existing_hashtag_str = ' '.join(f'#{t.name}' for t in post.hashtags)
        existing_captions    = post.img_captions.split('\t') if post.img_captions else []
        return render_template('update.html', post=post, genres=genres,
                               existing_hashtag_str=existing_hashtag_str,
                               existing_captions=existing_captions)

    # POST
    title = request.form.get('title', '').strip()
    body  = request.form.get('body', '').strip()
    if not title or not body:
        flash('タイトルと内容はどちらも入力必須です。', 'danger')
        return redirect(f'/{id}/update')

    post.title = title
    post.body  = body

    selected_default_thumb = request.form.get('default_thumb_select')
    post.default_thumb = None if selected_default_thumb == 'none' else selected_default_thumb

    is_published_form = request.form.get('is_published')
    if is_published_form is not None:
        post.is_published = (is_published_form == 'true')

    new_genre      = request.form.get('genre_new', '').strip()
    selected_genre = request.form.get('genre_select')
    post.genre = new_genre if new_genre else (selected_genre or '未分類')

    sync_hashtags(post, parse_hashtag_input(request.form.get('hashtag_input', '')))

    # 画像更新
    files = request.files.getlist('img[]')
    if files and files[0].filename != '':
        try:
            filename_list = _save_images(files)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(f'/{id}/update')

        _delete_images(post.img_name)   # 旧画像を物理削除
        post.img_name    = ','.join(filename_list)
        captions         = parse_img_captions(len(filename_list))
        post.img_captions = '\t'.join(captions) if captions else None

    else:
        # 画像変更なし → キャプションのみ更新
        if post.img_name:
            existing_imgs = post.img_name.split(',')
            captions = []
            for i in range(1, len(existing_imgs) + 1):
                captions.append(request.form.get(f'img_caption_{i}', '').strip())
            post.img_captions = '\t'.join(captions)

    post.updated_at = datetime.now(pytz.timezone('Asia/Tokyo'))
    db.session.commit()
    return redirect(f'/{id}/detail')


# ===== 削除 =====

@admin_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    _delete_images(post.img_name)
    db.session.delete(post)
    db.session.commit()

    # [変更前] netloc 比較のみ → サブドメインや http/https 差異で Open Redirect の余地
    # [変更後] 同一オリジン（scheme + netloc）が一致する場合のみリダイレクト
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

    return redirect('/')


# ===== マイページ =====

@admin_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        new_nickname = request.form.get('nickname', '').strip()
        current_user.nickname = new_nickname or None
        flash('ニックネームを更新しました！' if new_nickname else 'ニックネームを解除しました。', 'info')
        db.session.commit()
        return redirect('/mypage')

    search_word    = request.args.get('search')
    selected_genre = request.args.get('genre')

    posts_query = Post.query.filter(Post.user_id == current_user.id)
    if search_word and search_word.strip():
        posts_query = posts_query.filter(Post.title.contains(search_word.strip()))
    if selected_genre:
        posts_query = posts_query.filter(Post.genre == selected_genre)

    user_posts = posts_query.order_by(Post.created_at.desc()).all()

    # [変更] Python 側での remove/append を廃止し、DB クエリ + sorted で整理
    user_genres_raw = (
        db.session.query(Post.genre)
        .filter(Post.user_id == current_user.id, Post.genre != None, Post.genre != '')
        .distinct()
        .all()
    )
    user_genres = sorted({g[0] for g in user_genres_raw if g[0] != '未分類'})
    if any(g[0] == '未分類' for g in user_genres_raw):
        user_genres.append('未分類')

    return render_template(
        'mypage.html',
        posts          = user_posts,
        user_genres    = user_genres,
        selected_genre = selected_genre,
        search_word    = search_word,
    )