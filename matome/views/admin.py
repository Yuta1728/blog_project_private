# views/admin.py
from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user  
from flask_login import login_required
from datetime import datetime
from urllib.parse import urlparse
import os
import uuid
import pytz
from extensions import db
from models import Post
import config

admin_bp = Blueprint('admin', __name__)

# views/blog.pyと同じDEFAULT_GENRESを参照
DEFAULT_GENRES = [
    '日常', '健康', '旅行', '趣味', 'イラスト', 'ニュース', '経済', '投資',
    'プログラミング学習', '開発記録', '資格勉強', '勉強', 'サッカー', '野球', '競馬',
    'アニメ', '漫画', '本', 'ゲーム', '音楽', '国内映画', '海外映画', '国内ドラマ', '海外ドラマ',
    'バイト', '就活', '仕事'
]

# 新規投稿画面の表示設定
@admin_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')
    
    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        selected_genre = request.form.get('genre_select')
        new_genre = request.form.get('genre_new')
        
        final_genre = '未分類'
        if new_genre and new_genre.strip() != '':
            final_genre = new_genre.strip()
        elif selected_genre and selected_genre != '':
            final_genre = selected_genre
        
        # 👇【追加】選択されたデフォルトサムネイル画像名を取得
        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':  # 「選択なし」の場合はNone(Null)にする
            selected_default_thumb = None
        
        files = request.files.getlist('img[]')
        
        filename_list = []
        for file in files:
            if file and file.filename != '':
                ext = os.path.splitext(file.filename)[1]
                filename = f"{uuid.uuid4()}{ext}"
                
                save_path = os.path.join(current_app.static_folder, 'img', filename)
                file.save(save_path)
                filename_list.append(filename)
                
        img_name_str = ",".join(filename_list) if filename_list else None
        
        if not title or not body or title.strip() == '' or body.strip() == '':
            flash('タイトルと内容はどちらも入力必須です。')
            return redirect('/create')
        
        is_published_form = request.form.get('is_published')
        is_published = (is_published_form == 'true') if is_published_form is not None else False
            
        post = Post(
            title=title, 
            body=body, 
            user_id=current_user.id, 
            img_name=img_name_str, 
            default_thumb=selected_default_thumb,
            genre=final_genre,
            is_published=is_published  
        )
        
        db.session.add(post)
        db.session.commit()
        return redirect('/')
        
    else:
        existing_genres = db.session.query(Post.genre).filter(
            Post.user_id == current_user.id,
            Post.genre != '未分類', Post.genre != None, Post.genre != ''
        ).distinct().all()
        user_genres_list = [g[0] for g in existing_genres]

        all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)

        existing_genres = sorted(
            list(all_genres_set),
            key=lambda x: DEFAULT_GENRES.index(x) if x in DEFAULT_GENRES else len(DEFAULT_GENRES) + hash(x)
        )
        return render_template('create.html', genres=existing_genres)

# 編集画面の表示設定   
@admin_bp.route('/<int:id>/update', methods=['GET', 'POST'])
@login_required
def update(id):
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')
    
    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。")
        return redirect('/')
    
    if request.method == 'GET':
        existing_genres = db.session.query(Post.genre).filter(
            Post.user_id == current_user.id, 
            Post.genre != '未分類', Post.genre != None, Post.genre != ''
        ).distinct().all()
        user_genres_list = [g[0] for g in existing_genres]
        
        all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)
        if post.genre:
            all_genres_set.add(post.genre)
        if '未分類' in all_genres_set:
            all_genres_set.remove('未分類')
            
        genres_list = sorted(
            list(all_genres_set),
            key=lambda x: DEFAULT_GENRES.index(x) if x in DEFAULT_GENRES else len(DEFAULT_GENRES) + hash(x)
        )
        return render_template('update.html', post=post, genres=genres_list)
    else:
        post.title = request.form.get('title')
        post.body = request.form.get('body')
        
        # 👇【追加】編集画面から送信されたデフォルトサムネイル画像名で更新
        selected_default_thumb = request.form.get('default_thumb_select')
        post.default_thumb = None if selected_default_thumb == 'none' else selected_default_thumb
        
        is_published_form = request.form.get('is_published')
        if is_published_form is not None:
            post.is_published = (is_published_form == 'true')
        
        selected_genre = request.form.get('genre_select')
        new_genre = request.form.get('genre_new')
        
        if new_genre and new_genre.strip() != '':
            post.genre = new_genre.strip()
        elif selected_genre and selected_genre != '':
            post.genre = selected_genre
        else:
            post.genre = '未分類'
        
        if not post.title or not post.body or post.title.strip() == '' or post.body.strip() == '':
            flash('タイトルと内容はどちらも入力必須です。')
            return redirect(f'/{id}/update')

        files = request.files.getlist('img[]')
        if files and files[0].filename != '':
            if post.img_name:
                for old_img in post.img_name.split(','):
                    old_path = os.path.join(current_app.static_folder, 'img', old_img)
                    if os.path.exists(old_path):
                        os.remove(old_path)
            
            filename_list = []
            for file in files:
                if file and file.filename != '':
                    ext = os.path.splitext(file.filename)[1]
                    filename = f"{uuid.uuid4()}{ext}"
                    
                    save_path = os.path.join(current_app.static_folder, 'img', filename)
                    file.save(save_path)
                    filename_list.append(filename)
            post.img_name = ",".join(filename_list)
            
        post.updated_at = datetime.now(pytz.timezone('Asia/Tokyo'))
        db.session.commit()
    return redirect(f'/{id}/detail')

# 削除機能
@admin_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')
    
    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。")
        return redirect('/')
    
    if post.img_name:
        for img_file in post.img_name.split(','):
            img_path = os.path.join(current_app.static_folder, 'img', img_file)
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

# マイページの表示設定
@admin_bp.route('/mypage', methods=['GET', 'POST'])
@login_required  
def mypage():
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')
    
    if request.method == 'POST':
        new_nickname = request.form.get('nickname')
        if new_nickname and new_nickname.strip() != '':
            current_user.nickname = new_nickname.strip()
            flash('ニックネームを更新しました！')
        else:
            current_user.nickname = None
            flash('ニックネームを解除しました。')
            
        db.session.commit()
        return redirect('/mypage')
    
    posts_query = Post.query.filter(Post.user_id == current_user.id)
    search_word = request.args.get('search')
    selected_genre = request.args.get('genre')
    
    if search_word and search_word.strip() != '':
        posts_query = posts_query.filter(Post.title.contains(search_word.strip()))
        
    if selected_genre:
        posts_query = posts_query.filter(Post.genre == selected_genre)
        
    user_posts = posts_query.order_by(Post.created_at.desc()).all()
    
    existing_genres = db.session.query(Post.genre).filter(
        Post.user_id == current_user.id,
        Post.genre != '未分類', Post.genre != None, Post.genre != ''
    ).distinct().all()
    
    user_genres = [g[0] for g in existing_genres]
    if '未分類' in user_genres:
        user_genres.remove('未分類')
    user_genres = sorted(user_genres) 
    user_genres.append('未分類')
        
    return render_template(
        'mypage.html', 
        posts=user_posts, 
        user_genres=user_genres, 
        selected_genre=selected_genre,
        search_word=search_word
    )