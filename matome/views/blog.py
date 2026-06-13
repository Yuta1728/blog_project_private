# views/blog.py
from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user  
import markdown
import re
from extensions import db
from models import Post

blog_bp = Blueprint('blog', __name__)

# デフォルトジャンル
DEFAULT_GENRES = [
    '日常', '健康', '旅行', '趣味', 'イラスト', 'ニュース', '経済', '投資',
    'プログラミング学習', '開発記録', '資格勉強', '勉強', 'サッカー', '野球', '競馬',
    'アニメ', '漫画', '本', 'ゲーム', '音楽', '国内映画', '海外映画', '国内ドラマ', '海外ドラマ',
    'バイト', '就活', '仕事'
]  

# トップ画面の表示設定
@blog_bp.route('/', methods=['GET', 'POST'])
def index():
    selected_genre = request.args.get('genre')
    search_word = request.args.get('search')
    
    if current_user.is_authenticated:
        query = Post.query.filter((Post.is_published == True) | (Post.user_id == current_user.id))
    else:
        query = Post.query.filter(Post.is_published == True)

    if search_word:
        query = query.filter(Post.title.ilike(f'%{search_word}%'))
    if selected_genre:
        query = query.filter(Post.genre == selected_genre)

    posts = query.order_by(Post.created_at.desc()).all()
            
    return render_template('index.html', posts=posts, selected_genre=selected_genre, search_word=search_word)

# 投稿詳細
@blog_bp.route('/<int:id>/detail', methods=['GET'])
def detail(id):
    post = db.session.get(Post, id)
    
    if not post:
        flash("指定された記事が見つかりません。")
        return redirect('/')
    
    if not post.is_published:
        if not current_user.is_authenticated or post.user_id != current_user.id:
            flash("この記事は非公開に設定されているため閲覧できません。")
            return redirect('/')
    
    body_content = post.body
    # body_content = body_content.replace(' ', '&emsp;')
    
    md = markdown.Markdown(
        extensions=['toc', 'nl2br'],
        extension_configs={'toc': {'toc_depth': '2-3', 'marker': '[toc]'}}
    )
    
    display_body = md.convert(body_content)
    
    has_toc_marker = '[toc]' in body_content
    toc_html = md.toc if not has_toc_marker else None

    if post.img_name:
        images = post.img_name.split(',')
        for index, img_file in enumerate(images):
            # 💡【修正】src の画像読み込みパスを '/static/img/' から '/static/img/posts/' に変更
            img_tag = f'<span style="display:block; text-align:center; margin: 15px 0;"><img src="/static/img/posts/{img_file}" style="max-width:100%; height:auto;"></span>'
            display_body = display_body.replace(f'[img{index+1}]', img_tag)
            
    display_body = re.sub(r'\[img\d+\]', '', display_body)
            
    return render_template('detail.html', post=post, display_body=display_body, toc_html=toc_html)

# ジャンル一覧画面の表示設定
@blog_bp.route('/genre', methods=['GET'])
def genre_list():
    genres_list = sorted(DEFAULT_GENRES)
    
    if '未分類' in genres_list:
        genres_list.remove('未分類')
        genres_list.append('未分類')
    
    return render_template('genre.html', genres=genres_list)