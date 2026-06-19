# views/blog.py
from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user
import markdown
import re
from sqlalchemy import func
from extensions import db
from models import Post, Hashtag, User
from constants import DEFAULT_GENRES
import config

blog_bp = Blueprint('blog', __name__)


# ===== トップ画面 =====

@blog_bp.route('/', methods=['GET'])
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

    # --- 検索フィルター ---
    if search_word:
        keyword = f'%{search_word.strip()}%'
        # [変更前] any() と join() を同一クエリに混在 → 重複行・カーテシアン積のリスク
        # [変更後] any() を OR の両辺で統一。EXISTS サブクエリになるため安全かつ効率的
        query = query.filter(
            Post.title.ilike(keyword) |
            Post.hashtags.any(Hashtag.name.ilike(keyword))
        )

    if selected_genre:
        query = query.filter(Post.genre == selected_genre)

    if selected_hashtag:
        # [変更] search との混在を分離し、hashtag 絞り込み専用 join を後から適用
        query = query.join(Post.hashtags).filter(Hashtag.name == selected_hashtag)

    posts = query.order_by(Post.created_at.desc()).all()

    # ===== ジャンル内ハッシュタグ一覧（絞り込みバー用） =====
    hashtags_in_genre = []
    if selected_genre:
        # [変更前] genre_posts を Python 側で全件ループ → N+1 に近い問題
        # [変更後] DB 側で JOIN + DISTINCT + ORDER BY を一括処理
        pub_filter = [] if current_user.is_authenticated else [Post.is_published == True]
        hashtags_in_genre = (
            db.session.query(Hashtag)
            .join(Hashtag.posts)
            .filter(Post.genre == selected_genre, *pub_filter)
            .distinct()
            .order_by(Hashtag.name)
            .all()
        )

    # ===== 統計情報（トップページのみ、毎回 DB から取得） =====
    stats      = None
    admin_user = None
    if not selected_genre and not search_word and not selected_hashtag:
        post_count = Post.query.filter(Post.is_published == True).count()

        # [変更前] .distinct().count() を別クエリで実行
        # [変更後] func.count(func.distinct()) で 1 クエリに集約
        hashtag_count = (
            db.session.query(func.count(func.distinct(Hashtag.id)))
            .join(Hashtag.posts)
            .filter(Post.is_published == True)
            .scalar()
        )

        # [変更] with_entities で updated_at のみ取得し転送データ削減
        latest = (
            Post.query
            .filter(Post.is_published == True)
            .order_by(Post.updated_at.desc())
            .with_entities(Post.updated_at)
            .first()
        )
        last_updated = latest.updated_at.strftime('%Y/%m/%d') if latest else '---'

        stats = {
            'post_count':    post_count,
            'hashtag_count': hashtag_count,
            'last_updated':  last_updated,
        }
        admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()

    return render_template(
        'index.html',
        posts             = posts,
        selected_genre    = selected_genre,
        search_word       = search_word,
        selected_hashtag  = selected_hashtag,
        hashtags_in_genre = hashtags_in_genre,
        stats             = stats,
        admin_user        = admin_user,
    )


# ===== 自己紹介ページ =====

@blog_bp.route('/about')
def about():
    admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()
    return render_template('about.html', admin_user=admin_user)


# ===== 使い方ページ =====

@blog_bp.route('/howto')
def howto():
    return render_template('howto.html')


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

    body_content   = post.body
    has_toc_marker = '[toc]' in body_content

    body_content = _expand_blank_lines(body_content)

    md = markdown.Markdown(
        extensions=['toc', 'nl2br'],
        extension_configs={'toc': {'toc_depth': '2-3', 'marker': '[toc]'}}
    )

    display_body = md.convert(body_content)
    toc_html     = None if has_toc_marker else md.toc

    if post.img_name:
        images   = post.img_name.split(',')
        captions = post.img_captions.split('\t') if post.img_captions else []

        for index, img_file in enumerate(images):
            # [追加] ファイル名のディレクトリトラバーサルをブロック
            # DB に保存済みの値だが、念のためパス区切り文字を除去する
            img_file = re.sub(r'[/\\]', '', img_file.strip())
            caption  = captions[index].strip() if index < len(captions) else ''

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
    display_body = re.sub(r'\[map:([^\]]+)\]', _replace_map, display_body)

    return render_template('detail.html', post=post, display_body=display_body, toc_html=toc_html)


# ===== ジャンル一覧 =====

@blog_bp.route('/genre', methods=['GET'])
def genre_list():
    genres_list = sorted(DEFAULT_GENRES)
    if '未分類' in genres_list:
        genres_list.remove('未分類')
        genres_list.append('未分類')
    return render_template('genre.html', genres=genres_list)


# ===== 内部ヘルパー =====

def _is_structural_line(s: str) -> bool:
    stripped = s.strip()
    return (
        stripped.startswith('#') or
        stripped.startswith('```') or
        stripped == '[toc]'
    )


def _expand_blank_lines(text: str) -> str:
    """
    連続する空行をマークダウン用に正規化する。
    見出し・コードブロック・TOC マーカーに隣接する空行はそのまま維持し、
    それ以外の連続空行は <br> タグに変換して段落間隔を保つ。
    """
    lines  = text.split('\n')
    result = []
    i      = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == '':
            blank_count = 0
            while i < len(lines) and lines[i].strip() == '':
                blank_count += 1
                i += 1
            prev_line = result[-1] if result else ''
            next_line = lines[i] if i < len(lines) else ''
            if _is_structural_line(prev_line) or _is_structural_line(next_line) or blank_count == 1:
                result.extend([''] * blank_count)
            else:
                result.append('')
                result.extend(['<br>'] * (blank_count - 1))
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)


def _replace_map(m: re.Match) -> str:
    """[map:場所名] を Google Maps iFrame HTML に変換する"""
    place   = m.group(1).strip()
    encoded = place.replace(' ', '+')
    return (
        f'<div class="post-map-wrapper">'
        f'<div class="post-map-label">📍 {place}</div>'
        f'<iframe class="post-map-iframe"'
        f' src="https://maps.google.com/maps?q={encoded}&output=embed&hl=ja"'
        f' loading="lazy" allowfullscreen></iframe>'
        f'</div>'
    )