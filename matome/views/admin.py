from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user
from flask_login import login_required
from datetime import datetime
from urllib.parse import urlparse
import os
import uuid
import pytz
import filetype          # マジックナンバー検証用ライブラリ
from werkzeug.utils import secure_filename  # ファイル名サニタイズ用
from extensions import db
from models import Post, Hashtag
import config

admin_bp = Blueprint('admin', __name__)

# views/blog.py と同じ DEFAULT_GENRES を参照
DEFAULT_GENRES = [
    '日常', '健康', '旅行', '趣味', 'イラスト', 'ニュース', '経済', '投資',
    'プログラミング学習', '開発記録', '資格勉強', '勉強', 'サッカー', '野球', '競馬',
    'アニメ', '漫画', '本', 'ゲーム', '音楽', '国内映画', '海外映画', '国内ドラマ', '海外ドラマ',
    'バイト', '就活', '仕事'
]

# --- ファイル検証用ホワイトリスト ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIME_TYPES  = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


def allowed_file(filename):
    """拡張子がホワイトリストに含まれているかチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ===== ハッシュタグ用ヘルパー =====

def parse_hashtag_input(raw: str) -> list[str]:
    """
    フォームから受け取った文字列をハッシュタグ名リストに変換する。
    入力例: "#Flask #Python ブログ" → ['Flask', 'Python', 'ブログ']
    - '#' はあっても無くても OK
    - 空白・全角空白・カンマ・読点 で区切り
    - 重複は除去、50文字以内のみ受け付ける
    """
    import re
    raw = raw.strip()
    if not raw:
        return []
    tokens = re.split(r'[\s\u3000,、]+', raw)
    names = []
    seen  = set()
    for token in tokens:
        name = token.lstrip('#').strip()
        if name and name not in seen and len(name) <= 50:
            names.append(name)
            seen.add(name)
    return names


def sync_hashtags(post: Post, tag_names: list[str]):
    """
    post.hashtags を tag_names と同期する。
    - 既存タグは使い回す（Hashtag テーブルに重複を作らない）
    - 不要になったタグは post との紐付けを外す（Hashtag 行自体は残す）
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

def parse_img_captions(files: list) -> list[str]:
    """
    フォームから img_caption_1, img_caption_2 ... を受け取りリストにする。
    files と同じ件数分取得し、未入力は空文字で埋める。
    """
    captions = []
    for i in range(1, len(files) + 1):
        caption = request.form.get(f'img_caption_{i}', '').strip()
        captions.append(caption)
    return captions


# ===== ジャンルリスト取得ヘルパー =====

def _get_genre_list(user_id: int, current_genre: str | None = None) -> list[str]:
    existing = db.session.query(Post.genre).filter(
        Post.user_id == user_id,
        Post.genre   != '未分類',
        Post.genre   != None,
        Post.genre   != ''
    ).distinct().all()
    user_genres_list = [g[0] for g in existing]

    all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)
    if current_genre:
        all_genres_set.add(current_genre)
    all_genres_set.discard('未分類')

    return sorted(
        list(all_genres_set),
        key=lambda x: DEFAULT_GENRES.index(x) if x in DEFAULT_GENRES else len(DEFAULT_GENRES) + hash(x)
    )


# ===== 新規投稿 =====

@admin_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        title        = request.form.get('title')
        body         = request.form.get('body')
        selected_genre = request.form.get('genre_select')
        new_genre      = request.form.get('genre_new')
        hashtag_input  = request.form.get('hashtag_input', '')

        final_genre = '未分類'
        if new_genre and new_genre.strip():
            final_genre = new_genre.strip()
        elif selected_genre and selected_genre:
            final_genre = selected_genre

        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        files = request.files.getlist('img[]')

        filename_list = []
        for file in files:
            if file and file.filename != '':
                if not allowed_file(file.filename):
                    flash('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)', 'danger')
                    return redirect('/create')

                safe_filename = secure_filename(file.filename)
                ext = os.path.splitext(safe_filename)[1]

                header = file.stream.read(2048)
                file.stream.seek(0)

                kind = filetype.guess(header)
                if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
                    flash('ファイルの内容が不正です。画像偽装の可能性があります。', 'danger')
                    return redirect('/create')

                filename  = f"{uuid.uuid4()}{ext}"
                save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)
                file.save(save_path)
                filename_list.append(filename)

        img_name_str = ",".join(filename_list) if filename_list else None

        # ===== キャプション保存 =====
        captions = parse_img_captions(filename_list)
        img_captions_str = "\t".join(captions) if captions else None

        if not title or not body or title.strip() == '' or body.strip() == '':
            flash('タイトルと内容はどちらも入力必須です。', 'danger')
            return redirect('/create')

        is_published_form = request.form.get('is_published')
        is_published = (is_published_form == 'true') if is_published_form is not None else False

        post = Post(
            title        = title,
            body         = body,
            user_id      = current_user.id,
            img_name     = img_name_str,
            default_thumb = selected_default_thumb,
            genre        = final_genre,
            is_published = is_published,
            img_captions = img_captions_str,
        )
        db.session.add(post)

        # ハッシュタグの同期（flush で post.id を確定させてから）
        db.session.flush()
        tag_names = parse_hashtag_input(hashtag_input)
        sync_hashtags(post, tag_names)

        db.session.commit()
        return redirect('/')

    else:
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
        genres = _get_genre_list(current_user.id, post.genre)
        # 編集画面用：既存ハッシュタグを「#name #name …」形式で渡す
        existing_hashtag_str = ' '.join(f'#{t.name}' for t in post.hashtags)
        # 既存キャプションをリストで渡す
        existing_captions = post.img_captions.split('\t') if post.img_captions else []
        return render_template('update.html', post=post, genres=genres,
                               existing_hashtag_str=existing_hashtag_str,
                               existing_captions=existing_captions)

    else:
        post.title = request.form.get('title')
        post.body  = request.form.get('body')

        selected_default_thumb = request.form.get('default_thumb_select')
        post.default_thumb = None if selected_default_thumb == 'none' else selected_default_thumb

        is_published_form = request.form.get('is_published')
        if is_published_form is not None:
            post.is_published = (is_published_form == 'true')

        selected_genre = request.form.get('genre_select')
        new_genre      = request.form.get('genre_new')
        if new_genre and new_genre.strip():
            post.genre = new_genre.strip()
        elif selected_genre and selected_genre:
            post.genre = selected_genre
        else:
            post.genre = '未分類'

        if not post.title or not post.body or post.title.strip() == '' or post.body.strip() == '':
            flash('タイトルと内容はどちらも入力必須です。', 'danger')
            return redirect(f'/{id}/update')

        # ハッシュタグ更新
        hashtag_input = request.form.get('hashtag_input', '')
        tag_names = parse_hashtag_input(hashtag_input)
        sync_hashtags(post, tag_names)

        # 画像更新
        files = request.files.getlist('img[]')
        if files and files[0].filename != '':
            for file in files:
                if file and file.filename != '':
                    if not allowed_file(file.filename):
                        flash('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)', 'danger')
                        return redirect(f'/{id}/update')
                    header = file.stream.read(2048)
                    file.stream.seek(0)
                    kind = filetype.guess(header)
                    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
                        flash('ファイルの内容が不正です。画像偽装の可能性があります。', 'danger')
                        return redirect(f'/{id}/update')

            if post.img_name:
                for old_img in post.img_name.split(','):
                    old_path = os.path.join(current_app.static_folder, 'img', 'posts', old_img)
                    if os.path.exists(old_path):
                        os.remove(old_path)

            filename_list = []
            for file in files:
                if file and file.filename != '':
                    safe_filename = secure_filename(file.filename)
                    ext  = os.path.splitext(safe_filename)[1]
                    filename  = f"{uuid.uuid4()}{ext}"
                    save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)
                    file.save(save_path)
                    filename_list.append(filename)
            post.img_name = ",".join(filename_list)

            # 新しい画像に合わせてキャプション更新
            captions = parse_img_captions(filename_list)
            post.img_captions = "\t".join(captions) if captions else None

        else:
            # 画像変更なし → キャプションのみ更新（既存画像枚数分）
            if post.img_name:
                existing_imgs = post.img_name.split(',')
                captions = []
                for i in range(1, len(existing_imgs) + 1):
                    caption = request.form.get(f'img_caption_{i}', '').strip()
                    captions.append(caption)
                post.img_captions = "\t".join(captions)

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

    if post.img_name:
        for img_file in post.img_name.split(','):
            img_path = os.path.join(current_app.static_folder, 'img', 'posts', img_file)
            if os.path.exists(img_path):
                os.remove(img_path)

    db.session.delete(post)
    db.session.commit()

    referrer = request.referrer
    if referrer:
        parsed_ref = urlparse(referrer)
        parsed_req = urlparse(request.url)
        if parsed_ref.netloc == parsed_req.netloc:
            return redirect(referrer)

    return redirect('/')


# ===== マイページ =====

@admin_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        new_nickname = request.form.get('nickname')
        if new_nickname and new_nickname.strip():
            current_user.nickname = new_nickname.strip()
            flash('ニックネームを更新しました！', 'success')
        else:
            current_user.nickname = None
            flash('ニックネームを解除しました。', 'info')
        db.session.commit()
        return redirect('/mypage')

    posts_query  = Post.query.filter(Post.user_id == current_user.id)
    search_word  = request.args.get('search')
    selected_genre = request.args.get('genre')

    if search_word and search_word.strip():
        posts_query = posts_query.filter(Post.title.contains(search_word.strip()))
    if selected_genre:
        posts_query = posts_query.filter(Post.genre == selected_genre)

    user_posts = posts_query.order_by(Post.created_at.desc()).all()

    existing_genres = db.session.query(Post.genre).filter(
        Post.user_id == current_user.id,
        Post.genre   != '未分類',
        Post.genre   != None,
        Post.genre   != ''
    ).distinct().all()

    user_genres = [g[0] for g in existing_genres]
    if '未分類' in user_genres:
        user_genres.remove('未分類')
    user_genres = sorted(user_genres)
    user_genres.append('未分類')

    return render_template(
        'mypage.html',
        posts        = user_posts,
        user_genres  = user_genres,
        selected_genre = selected_genre,
        search_word  = search_word
    )