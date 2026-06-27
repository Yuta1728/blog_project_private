# views/blog.py
#
# 【役割】
# 一般公開ページ（誰でも閲覧できるページ）のルートとロジックを担うビューファイル。
#
# 担当ページ:
#   /            → トップ（記事一覧）
#   /about       → 管理者自己紹介ページ
#   /howto       → このブログの使い方ページ
#   /<id>/detail → 記事詳細ページ
#   /genre       → ジャンル一覧ページ

from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user
import markdown    # マークダウン → HTML 変換ライブラリ
import re          # 正規表現（[img1], [map:xxx], [youtube:xxx] の置換に使用）
from sqlalchemy import func
from extensions import db
from models import Post, Hashtag, User
from constants import DEFAULT_GENRES
import config

blog_bp = Blueprint('blog', __name__)


# ===================================================================
# トップページ（記事一覧）
# ===================================================================
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

    if search_word:
        keyword = f'%{search_word.strip()}%'
        query = query.filter(
            Post.title.ilike(keyword) |
            Post.hashtags.any(Hashtag.name.ilike(keyword))
        )

    if selected_genre:
        query = query.filter(Post.genre == selected_genre)

    if selected_hashtag:
        query = query.join(Post.hashtags).filter(Hashtag.name == selected_hashtag)

    posts = query.order_by(Post.created_at.desc()).all()

    hashtags_in_genre = []
    if selected_genre:
        pub_filter = [] if current_user.is_authenticated else [Post.is_published == True]
        hashtags_in_genre = (
            db.session.query(Hashtag)
            .join(Hashtag.posts)
            .filter(Post.genre == selected_genre, *pub_filter)
            .distinct()
            .order_by(Hashtag.name)
            .all()
        )

    # -------------------------------------------------------------------
    # インページ検索エリア用ジャンルリスト
    #
    # search_area.html の <select> に渡す選択肢。
    # DEFAULT_GENRES をベースに、実際に記事が存在するジャンルだけを残す。
    # これにより「記事がないジャンル」を選択肢から除外できる。
    #
    # 表示順: DEFAULT_GENRES の並び順を優先し、
    #         それ以外（管理者が独自追加したジャンル）は末尾に辞書順で追加。
    # -------------------------------------------------------------------
    pub_condition = (Post.is_published == True) if not current_user.is_authenticated else True
    used_genres_raw = (
        db.session.query(Post.genre)
        .filter(pub_condition, Post.genre != None, Post.genre != '', Post.genre != '未分類')
        .distinct()
        .all()
    )
    used_genres_set = {g[0] for g in used_genres_raw}

    genre_list_all = [g for g in DEFAULT_GENRES if g in used_genres_set]
    # DEFAULT_GENRES にないジャンル（独自追加分）を末尾に辞書順で追加
    extra_genres = sorted(used_genres_set - set(DEFAULT_GENRES))
    genre_list_all.extend(extra_genres)
    # 未分類が使われている場合は末尾に追加
    has_miscellaneous = any(g[0] == '未分類' for g in used_genres_raw)
    if has_miscellaneous:
        genre_list_all.append('未分類')

    stats      = None
    admin_user = None
    if not selected_genre and not search_word and not selected_hashtag:
        post_count = Post.query.filter(Post.is_published == True).count()
        hashtag_count = (
            db.session.query(func.count(func.distinct(Hashtag.id)))
            .join(Hashtag.posts)
            .filter(Post.is_published == True)
            .scalar()
        )
        latest = (
            Post.query
            .filter(Post.is_published == True)
            .order_by(Post.updated_at.desc())
            .with_entities(Post.updated_at)
            .first()
        )
        last_updated = latest.updated_at.strftime('%Y/%m/%d') if latest and latest.updated_at else '---'
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
        genre_list_all    = genre_list_all,   # ← 追加: インページ検索エリア用
        stats             = stats,
        admin_user        = admin_user,
    )


# ===================================================================
# 自己紹介ページ
# ===================================================================
@blog_bp.route('/about')
def about():
    admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()
    return render_template('about.html', admin_user=admin_user)


# ===================================================================
# 使い方ページ
# ===================================================================
@blog_bp.route('/howto')
def howto():
    return render_template('howto.html')


# ===================================================================
# 関連記事取得ヘルパー
# ===================================================================

def _get_related_posts(post: Post, pub_filter, max_count: int = 4) -> list:
    """
    指定した記事に対する関連記事を最大 max_count 件取得して返す。

    取得は以下の優先順位で段階的に行い、合計が max_count に達した時点で終了する。

    STEP1: 同じジャンル × 同じタグあり（最も関連度が高い）
    STEP2: 同じタグのみ（ジャンル不問）
    STEP3: 同じジャンルのみ（タグ不問）
    STEP4: 最新記事（関連条件なし）

    各 STEP 内では created_at DESC（新しい順）で取得する。
    前の STEP で取得済みの記事は次の STEP 以降の候補から除外する（重複排除）。

    @param post:       現在閲覧中の Post オブジェクト
    @param pub_filter: 公開状態の絞り込み条件（SQLAlchemy フィルター式）
    @param max_count:  最大取得件数（デフォルト 4）
    @return:           STEP 順に並べた Post オブジェクトのリスト
    """
    results    = []          # 最終的に返すリスト（STEP 順を維持）
    seen_ids   = {post.id}   # 現在の記事を最初から除外対象に追加
    remaining  = max_count   # まだ取得が必要な件数
    tag_names  = [t.name for t in post.hashtags]

    # ------------------------------------------------------------------
    # STEP 1: 同じジャンル × 同じタグあり
    # ------------------------------------------------------------------
    if remaining > 0:
        step1 = (
            Post.query
            .filter(
                pub_filter,
                Post.id.notin_(seen_ids),
                Post.genre == post.genre,
                Post.hashtags.any(Hashtag.name.in_(tag_names)) if tag_names else False,
            )
            .order_by(Post.created_at.desc())
            .limit(remaining)
            .all()
        )
        results   += step1
        seen_ids  |= {p.id for p in step1}
        remaining  = max_count - len(results)

    # ------------------------------------------------------------------
    # STEP 2: 同じタグのみ（ジャンル不問）
    # ------------------------------------------------------------------
    if remaining > 0 and tag_names:
        step2 = (
            Post.query
            .filter(
                pub_filter,
                Post.id.notin_(seen_ids),
                Post.hashtags.any(Hashtag.name.in_(tag_names)),
            )
            .order_by(Post.created_at.desc())
            .limit(remaining)
            .all()
        )
        results   += step2
        seen_ids  |= {p.id for p in step2}
        remaining  = max_count - len(results)

    # ------------------------------------------------------------------
    # STEP 3: 同じジャンルのみ（タグ不問）
    # ------------------------------------------------------------------
    if remaining > 0:
        step3 = (
            Post.query
            .filter(
                pub_filter,
                Post.id.notin_(seen_ids),
                Post.genre == post.genre,
            )
            .order_by(Post.created_at.desc())
            .limit(remaining)
            .all()
        )
        results   += step3
        seen_ids  |= {p.id for p in step3}
        remaining  = max_count - len(results)

    # ------------------------------------------------------------------
    # STEP 4: 最新記事（関連条件なし）
    # ------------------------------------------------------------------
    if remaining > 0:
        step4 = (
            Post.query
            .filter(
                pub_filter,
                Post.id.notin_(seen_ids),
            )
            .order_by(Post.created_at.desc())
            .limit(remaining)
            .all()
        )
        results += step4

    return results


# ===================================================================
# 記事詳細ページ
# ===================================================================
@blog_bp.route('/<int:id>/detail', methods=['GET'])
def detail(id):
    """
    記事を取得し、マークダウン変換・画像埋め込み・地図埋め込み・
    YouTube 埋め込みを行って表示する。
    非公開記事は管理者のみ閲覧可能。
    """
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

    toc_html = None if has_toc_marker else md.toc

    # -------------------------------------------------------------------
    # 画像タグの埋め込み（[img1], [img2] → <img> タグ or <figure> タグ）
    # -------------------------------------------------------------------
    if post.img_name:
        images   = post.img_name.split(',')
        captions = post.img_captions.split('\t') if post.img_captions else []

        for index, img_file in enumerate(images):
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

    # マークダウン変換後は [img1] が <p>[img1]</p> になっている場合があるため
    # <p> タグごと除去してから、念のため素の [imgN] タグも除去する。
    display_body = re.sub(r'<p>\[img\d+\]</p>\n?', '', display_body)
    display_body = re.sub(r'\[img\d+\]', '', display_body)

    # -------------------------------------------------------------------
    # 地図タグの変換（[map:場所名] → Google Maps iframe）
    # -------------------------------------------------------------------
    display_body = re.sub(r'\[map:([^\]]+)\]', _replace_map, display_body)

    # -------------------------------------------------------------------
    # YouTube タグの変換
    # -------------------------------------------------------------------
    display_body = re.sub(
        r'(?:<p>)?\[youtube:([^\]]+)\](?:</p>)?',
        _replace_youtube,
        display_body
    )

    # -------------------------------------------------------------------
    # 関連記事の取得
    # -------------------------------------------------------------------
    if current_user.is_authenticated:
        pub_filter = (Post.is_published == True) | (Post.user_id == current_user.id)
    else:
        pub_filter = Post.is_published == True

    related_posts = _get_related_posts(post, pub_filter, max_count=4)

    # -------------------------------------------------------------------
    # 関連記事セクションのサブラベル生成
    # -------------------------------------------------------------------
    tag_names = [t.name for t in post.hashtags]
    if post.genre and post.genre != '未分類' and tag_names:
        related_sub_label = f'{post.genre}・{"、".join(f"#{n}" for n in tag_names[:2])} を表示中'
    elif post.genre and post.genre != '未分類':
        related_sub_label = f'{post.genre} を表示中'
    elif tag_names:
        related_sub_label = f'{"、".join(f"#{n}" for n in tag_names[:2])} を表示中'
    else:
        related_sub_label = '最新記事を表示中'

    return render_template(
        'detail.html',
        post              = post,
        display_body      = display_body,
        toc_html          = toc_html,
        related_posts     = related_posts,
        related_sub_label = related_sub_label,
    )


# ===================================================================
# ジャンル一覧ページ
# ===================================================================
@blog_bp.route('/genre', methods=['GET'])
def genre_list():
    genres_list = sorted(DEFAULT_GENRES)
    if '未分類' in genres_list:
        genres_list.remove('未分類')
        genres_list.append('未分類')
    return render_template('genre.html', genres=genres_list)


# ===================================================================
# 内部ヘルパー関数群
# ===================================================================

def _is_structural_line(s: str) -> bool:
    stripped = s.strip()
    return (
        stripped.startswith('#') or
        stripped.startswith('```') or
        stripped == '[toc]'
    )


def _expand_blank_lines(text: str) -> str:
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

            if (_is_structural_line(prev_line) or
                    _is_structural_line(next_line) or
                    blank_count == 1):
                result.extend([''] * blank_count)
            else:
                result.append('')
                result.extend(['<br>'] * (blank_count - 1))
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def _replace_map(m: re.Match) -> str:
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


# ===================================================================
# YouTube 埋め込みヘルパー
# ===================================================================

def _extract_youtube_id(raw: str) -> str | None:
    raw = raw.strip()

    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.search(r'/shorts/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.search(r'/embed/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.fullmatch(r'[A-Za-z0-9_-]{11}', raw)
    if m:
        return raw

    return None


def _replace_youtube(m: re.Match) -> str:
    raw      = m.group(1)
    video_id = _extract_youtube_id(raw)

    if not video_id:
        return f'<p style="color:#c0392b;">[youtube: 動画IDを認識できませんでした → {raw}]</p>'

    thumb_url = f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'
    embed_url = f'https://www.youtube.com/embed/{video_id}?autoplay=1'

    return (
        f'<div class="post-youtube-wrapper" data-embed-url="{embed_url}">'
        f'  <div class="post-youtube-facade" onclick="ytPlay(this)">'
        f'    <img class="post-youtube-thumb"'
        f'         src="{thumb_url}"'
        f'         alt="YouTube動画のサムネイル"'
        f'         loading="lazy">'
        f'    <button class="post-youtube-play-btn" aria-label="動画を再生">'
        f'      <svg viewBox="0 0 68 48" width="68" height="48">'
        f'        <path class="yt-btn-bg" d="M66.5 7.7a8.5 8.5 0 0 0-6-6C55.8.3 34 .3 34 .3S12.2.3 7.5 1.7a8.5 8.5 0 0 0-6 6C.1 11.4 0 24 0 24s.1 12.6 1.5 16.3a8.5 8.5 0 0 0 6 6C12.2 47.7 34 47.7 34 47.7s21.8 0 26.5-1.4a8.5 8.5 0 0 0 6-6C67.9 36.6 68 24 68 24s-.1-12.6-1.5-16.3z"/>'
        f'        <path class="yt-btn-icon" d="M45 24 27 14v20"/>'
        f'      </svg>'
        f'    </button>'
        f'  </div>'
        f'</div>'
    )