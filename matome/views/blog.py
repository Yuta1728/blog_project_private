# views/blog.py
from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user
import markdown
import re
from extensions import db
from models import Post, Hashtag

blog_bp = Blueprint('blog', __name__)

# デフォルトジャンル
DEFAULT_GENRES = [
    '日常', '健康', '旅行', '趣味', 'イラスト', 'ニュース', '経済', '投資',
    'プログラミング学習', '開発記録', '資格勉強', '勉強', 'サッカー', '野球', '競馬',
    'アニメ', '漫画', '本', 'ゲーム', '音楽', '国内映画', '海外映画', '国内ドラマ', '海外ドラマ',
    'バイト', '就活', '仕事'
]


# ===== トップ画面 =====

@blog_bp.route('/', methods=['GET', 'POST'])
def index():
    selected_genre   = request.args.get('genre')
    search_word      = request.args.get('search')
    selected_hashtag = request.args.get('hashtag')

    if current_user.is_authenticated:
        query = Post.query.filter(
            (Post.is_published == True) | (Post.user_id == current_user.id)
        )
    else:
        query = Post.query.filter(Post.is_published == True)

    if search_word:
        keyword = f'%{search_word}%'
        # タイトル OR ハッシュタグ名 のどちらかにマッチする記事を返す
        query = query.filter(
            Post.title.ilike(keyword) |
            Post.hashtags.any(Hashtag.name.ilike(keyword))
        )
    if selected_genre:
        query = query.filter(Post.genre == selected_genre)
    if selected_hashtag:
        query = query.join(Post.hashtags).filter(Hashtag.name == selected_hashtag)

    posts = query.order_by(Post.created_at.desc()).all()

    # ===== ジャンル一覧ページ用：選択ジャンル配下のハッシュタグを取得 =====
    hashtags_in_genre = []
    if selected_genre:
        if current_user.is_authenticated:
            genre_posts = Post.query.filter(
                Post.genre == selected_genre,
            ).all()
        else:
            genre_posts = Post.query.filter(
                Post.genre == selected_genre,
                Post.is_published == True
            ).all()

        seen = set()
        for p in genre_posts:
            for tag in p.hashtags:
                if tag.name not in seen:
                    hashtags_in_genre.append(tag)
                    seen.add(tag.name)
        hashtags_in_genre.sort(key=lambda t: t.name)

    return render_template(
        'index.html',
        posts            = posts,
        selected_genre   = selected_genre,
        search_word      = search_word,
        selected_hashtag = selected_hashtag,
        hashtags_in_genre = hashtags_in_genre,
    )


# ===== 投稿詳細 =====

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

    # ===== 連続する空行を <br> に変換（Markdown変換前に処理） =====
    # Markdownは \n\n 以上の連続空行を段落区切り1つとして扱い折りたたむため、
    # 変換前に「空行2行以上」を <br> タグへ置き換えておく。
    # ただし見出し（## / ###）やコードブロック(```)の前後は除外する。
    def expand_blank_lines(text):
        lines = text.split('\n')
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # 空行の連続をカウント
            if line.strip() == '':
                blank_count = 0
                while i < len(lines) and lines[i].strip() == '':
                    blank_count += 1
                    i += 1
                # 前後の行が見出し・コードブロック区切りなら通常の段落区切りとして残す
                prev_line = result[-1].strip() if result else ''
                next_line = lines[i].strip() if i < len(lines) else ''
                is_structural = (
                    prev_line.startswith('#') or next_line.startswith('#') or
                    prev_line.startswith('```') or next_line.startswith('```')
                )
                if is_structural or blank_count == 1:
                    # 通常の段落区切り：空行をそのまま出力
                    result.extend([''] * blank_count)
                else:
                    # 2行以上の空行：1つの段落区切り + 余剰分を <br> で表現
                    result.append('')
                    result.extend(['<br>'] * (blank_count - 1))
            else:
                result.append(line)
                i += 1
        return '\n'.join(result)

    body_content = expand_blank_lines(body_content)
    # ============================================================

    md = markdown.Markdown(
        extensions=['toc', 'nl2br'],
        extension_configs={'toc': {'toc_depth': '2-3', 'marker': '[toc]'}}
    )

    display_body = md.convert(body_content)

    has_toc_marker = '[toc]' in body_content
    toc_html = md.toc if not has_toc_marker else None

    if post.img_name:
        images   = post.img_name.split(',')
        captions = post.img_captions.split('\t') if post.img_captions else []

        for index, img_file in enumerate(images):
            caption = captions[index].strip() if index < len(captions) else ''

            if caption:
                img_tag = (
                    f'<figure class="post-figure">'
                    f'<img src="/static/img/posts/{img_file}" alt="{caption}" style="max-width:100%; height:auto;">'
                    f'<figcaption class="post-figcaption">{caption}</figcaption>'
                    f'</figure>'
                )
            else:
                img_tag = (
                    f'<span style="display:block; text-align:center; margin: 15px 0;">'
                    f'<img src="/static/img/posts/{img_file}" style="max-width:100%; height:auto;">'
                    f'</span>'
                )

            display_body = display_body.replace(f'[img{index+1}]', img_tag)

    display_body = re.sub(r'\[img\d+\]', '', display_body)

    # ===== [map:場所名] → Google Maps 埋め込み iframe に変換 =====
    def replace_map(m):
        place = m.group(1).strip()
        encoded = place.replace(' ', '+')
        return (
            f'<div class="post-map-wrapper">'
            f'<div class="post-map-label">📍 {place}</div>'
            f'<iframe class="post-map-iframe"'
            f' src="https://maps.google.com/maps?q={encoded}&output=embed&hl=ja"'
            f' loading="lazy" allowfullscreen></iframe>'
            f'</div>'
        )
    display_body = re.sub(r'\[map:([^\]]+)\]', replace_map, display_body)
    # ============================================================

    return render_template('detail.html', post=post, display_body=display_body, toc_html=toc_html)


# ===== ジャンル一覧 =====

@blog_bp.route('/genre', methods=['GET'])
def genre_list():
    genres_list = sorted(DEFAULT_GENRES)

    if '未分類' in genres_list:
        genres_list.remove('未分類')
        genres_list.append('未分類')

    return render_template('genre.html', genres=genres_list)