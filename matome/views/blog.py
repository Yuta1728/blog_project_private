# ======================================================================
# views/blog.py — 一般公開ページ（誰でも閲覧できるページ）
# ======================================================================
#
# 【役割】
#   一般公開ページのルートとロジックを担うビューファイル。
#
#   担当ページ:
#     /            → トップ（記事一覧）
#     /about       → 管理者自己紹介ページ
#     /howto       → このブログの使い方ページ
#     /<id>/detail → 記事詳細ページ
#     /genre       → ジャンル一覧ページ
#
# 【このファイルの構成（目次）】
#   [1] index()              : トップページ（記事一覧・検索・絞り込み・統計）
#   [2] about()              : 自己紹介ページ
#   [3] howto()              : 使い方ページ
#   [4] _get_related_posts() : 関連記事取得ヘルパー
#   [5] detail()             : 記事詳細ページ（Markdown 変換・各種タグ埋め込み）
#   [6] genre_list()         : ジャンル一覧ページ
#   [7] 内部ヘルパー関数群
#        (7-1) _is_structural_line()  : 構造行（見出し等）の判定
#        (7-2) _expand_blank_lines()  : 連続空行の <br> 展開
#        (7-3) _replace_map()         : [map:] タグ → Google マップ iframe
#        (7-4) _extract_youtube_id()  : YouTube URL から動画 ID を抽出
#        (7-5) _replace_youtube()     : [youtube:] タグ → ファサード埋め込み
#
# 【処理フロー図（記事詳細ページの本文レンダリング）】
#
#   post.body（Markdown + 独自タグ）
#        │
#        ▼
#   (7-2) _expand_blank_lines() ── 連続空行を <br> に展開
#        │
#        ▼
#   markdown.convert() ── Markdown → HTML（toc / nl2br 拡張）
#        │
#        ▼
#   [imgN] 置換 ── 画像 <img> / <figure>（キャプションは escape 済み）
#        │
#        ▼
#   (7-3) [map:] 置換 ── Google マップ iframe（quote + escape 済み）
#        │
#        ▼
#   (7-5) [youtube:] 置換 ── サムネイル + 再生ボタン（ファサード方式）
#        │
#        ▼
#   display_body として detail.html に渡す（| safe で出力）
#
# ======================================================================

from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user
import markdown    # マークダウン → HTML 変換ライブラリ
import re          # 正規表現（[img1], [map:xxx], [youtube:xxx] の置換に使用）
from urllib.parse import quote  # 【セキュリティ修正】地図 URL の正しいエンコードに使用
from markupsafe import escape   # 【セキュリティ修正】HTML 直組み立て時のエスケープに使用
from sqlalchemy import func
from extensions import db
from models import Post, Hashtag, User
from constants import DEFAULT_GENRES
import config

blog_bp = Blueprint('blog', __name__)


# ======================================================================
# [1] トップページ（記事一覧）
# ======================================================================

@blog_bp.route('/', methods=['GET'])
def index():
    """
    記事一覧を表示する。URL クエリパラメータによる
    キーワード検索・ジャンル絞り込み・ハッシュタグ絞り込みに対応。

    【処理の流れ】
      STEP 1. URL クエリパラメータを取得（genre / search / hashtag）
      STEP 2. 公開状態でベースクエリを構築
              （ログイン中は自分の非公開記事も含める）
      STEP 3. キーワード・ジャンル・ハッシュタグで絞り込み
      STEP 4. 作成日時の降順で記事リストを取得
      STEP 5. ジャンル選択中なら、そのジャンル内のハッシュタグ一覧を取得
      STEP 6. 検索エリア用のジャンル選択肢リストを生成
      STEP 7. 絞り込みなし（トップ表示）のときだけ統計情報と管理者情報を取得
      STEP 8. index.html をレンダリング
    """
    # ------------------------------------------------------------------
    # STEP 1. URL クエリパラメータの取得
    # ------------------------------------------------------------------
    selected_genre   = request.args.get('genre')
    search_word      = request.args.get('search')
    selected_hashtag = request.args.get('hashtag')

    # ------------------------------------------------------------------
    # STEP 2. 公開状態でベースクエリを構築
    # ------------------------------------------------------------------
    # ログイン中: 公開記事 + 自分の記事（非公開含む）
    # 未ログイン: 公開記事のみ
    if current_user.is_authenticated:
        query = Post.query.filter(
            (Post.is_published == True) | (Post.user_id == current_user.id)
        )
    else:
        query = Post.query.filter(Post.is_published == True)

    # ------------------------------------------------------------------
    # STEP 3. 検索・絞り込み条件の追加
    # ------------------------------------------------------------------
    # (3-1) キーワード検索: タイトル または ハッシュタグ名の部分一致（大文字小文字無視）
    if search_word:
        keyword = f'%{search_word.strip()}%'
        query = query.filter(
            Post.title.ilike(keyword) |
            Post.hashtags.any(Hashtag.name.ilike(keyword))
        )

    # (3-2) ジャンル絞り込み: 完全一致
    if selected_genre:
        query = query.filter(Post.genre == selected_genre)

    # (3-3) ハッシュタグ絞り込み: 中間テーブルを JOIN してタグ名で完全一致
    if selected_hashtag:
        query = query.join(Post.hashtags).filter(Hashtag.name == selected_hashtag)

    # ------------------------------------------------------------------
    # STEP 4. 作成日時の降順（新しい記事が先頭）で取得
    # ------------------------------------------------------------------
    # N+1問題を避けるため、ハッシュタグを selectinload で一括取得し、
    # サーバーサイドページネーションを適用する。
    page = request.args.get('page', 1, type=int)
    pagination = (
        query.options(db.selectinload(Post.hashtags))
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=4, error_out=False)
    )
    posts = pagination.items

    # ------------------------------------------------------------------
    # STEP 5. ジャンル選択中: そのジャンル内で使われているハッシュタグ一覧
    #         （タグ絞り込みバーの表示用）
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # STEP 6. インページ検索エリア用ジャンルリストの生成
    # ------------------------------------------------------------------
    # search_area.html の <select> に渡す選択肢。
    # DEFAULT_GENRES をベースに、実際に記事が存在するジャンルだけを残す。
    # これにより「記事がないジャンル」を選択肢から除外できる。
    #
    # 表示順: DEFAULT_GENRES の並び順を優先し、
    #         それ以外（管理者が独自追加したジャンル）は末尾に辞書順で追加。
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

    # ------------------------------------------------------------------
    # STEP 7. 絞り込みなし（トップ表示）のときだけ統計情報・管理者情報を取得
    # ------------------------------------------------------------------
    stats      = None
    admin_user = None
    if not selected_genre and not search_word and not selected_hashtag:
        # (7-1) 公開記事の総数
        post_count = Post.query.filter(Post.is_published == True).count()

        # (7-2) 公開記事に付いているハッシュタグの種類数
        hashtag_count = (
            db.session.query(func.count(func.distinct(Hashtag.id)))
            .join(Hashtag.posts)
            .filter(Post.is_published == True)
            .scalar()
        )

        # (7-3) 最終更新日
        # 【バグ修正】「最終更新日」の取得ロジックを修正
        #
        # 従来は ORDER BY updated_at DESC で先頭 1 件を取得していたが、
        # PostgreSQL は DESC ソートで NULL を先頭に並べる（NULLS FIRST が既定）ため、
        # updated_at が NULL の未更新記事が 1 件でもあると常に '---' 表示になっていた。
        # また、新規投稿（created_at のみ更新される）がサイトの
        # 「最終更新日」に反映されないという問題もあった。
        #
        # 対策: max(coalesce(updated_at, created_at)) で
        #       「更新日時があればそれ、なければ投稿日時」の最大値を 1 クエリで取得する。
        #       これにより NULL の影響を受けず、新規投稿も更新として扱われる。
        last_activity = (
            db.session.query(
                func.max(func.coalesce(Post.updated_at, Post.created_at))
            )
            .filter(Post.is_published == True)
            .scalar()
        )
        last_updated = last_activity.strftime('%Y/%m/%d') if last_activity else '---'

        stats = {
            'post_count':    post_count,
            'hashtag_count': hashtag_count,
            'last_updated':  last_updated,
        }
        # (7-4) hero セクション表示用の管理者情報
        admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()

    # ------------------------------------------------------------------
    # STEP 8. テンプレートのレンダリング
    # ------------------------------------------------------------------
    return render_template(
        'index.html',
        posts             = posts,
        pagination        = pagination,
        selected_genre    = selected_genre,
        search_word       = search_word,
        selected_hashtag  = selected_hashtag,
        hashtags_in_genre = hashtags_in_genre,
        genre_list_all    = genre_list_all,   # インページ検索エリア用
        stats             = stats,
        admin_user        = admin_user,
    )


# ======================================================================
# [2] 自己紹介ページ
# ======================================================================

@blog_bp.route('/about')
def about():
    """
    管理者の自己紹介ページを表示する。

    【処理の流れ】
      STEP 1. 管理者ユーザーを DB から取得（アバター・ニックネーム表示用）
      STEP 2. about.html をレンダリング
    """
    admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()
    return render_template('about.html', admin_user=admin_user)


# ======================================================================
# [3] 使い方ページ
# ======================================================================

@blog_bp.route('/howto')
def howto():
    """
    このブログの使い方ページ（静的コンテンツ）を表示する。
    """
    return render_template('howto.html')


# ======================================================================
# [4] 関連記事取得ヘルパー
# ======================================================================

def _get_related_posts(post: Post, pub_filter, max_count: int = 4) -> list:
    """
    指定した記事に対する関連記事を最大 max_count 件取得して返す。

    取得は以下の優先順位で段階的に行い、合計が max_count に達した時点で終了する。

      STEP 1: 同じジャンル × 同じタグあり（最も関連度が高い）
      STEP 2: 同じタグのみ（ジャンル不問）
      STEP 3: 同じジャンルのみ（タグ不問）
      STEP 4: 最新記事（関連条件なし）

    各 STEP 内では created_at DESC（新しい順）で取得する。
    前の STEP で取得済みの記事は次の STEP 以降の候補から除外する（重複排除）。

    @param post:       現在閲覧中の Post オブジェクト
    @param pub_filter: 公開状態の絞り込み条件（SQLAlchemy フィルター式）
    @param max_count:  最大取得件数（デフォルト 4）
    @return:           STEP 順に並べた Post オブジェクトのリスト
    """
    # ------------------------------------------------------------------
    # STEP 0. 初期化
    # ------------------------------------------------------------------
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


# ======================================================================
# [5] 記事詳細ページ
# ======================================================================

@blog_bp.route('/<int:id>/detail', methods=['GET'])
def detail(id):
    """
    記事を取得し、マークダウン変換・画像埋め込み・地図埋め込み・
    YouTube 埋め込みを行って表示する。
    非公開記事は管理者のみ閲覧可能。

    【処理の流れ】
      STEP 1. 記事を取得。存在しなければトップへリダイレクト
      STEP 2. 非公開記事は投稿者本人以外を弾く
      STEP 3. 本文の連続空行を <br> に展開（_expand_blank_lines）
      STEP 4. Markdown → HTML 変換（toc / nl2br 拡張）
      STEP 5. [toc] マーカーがなければ記事冒頭用の目次 HTML を用意
      STEP 6. [imgN] タグを <img> / <figure> に置換（キャプションはエスケープ）
      STEP 7. 未使用の [imgN] タグを除去
      STEP 8. [map:] タグを Google マップ iframe に置換
      STEP 9. [youtube:] タグをファサード埋め込みに置換
      STEP 10. 関連記事とサブラベルを生成
      STEP 11. detail.html をレンダリング
    """
    # ------------------------------------------------------------------
    # STEP 1. 記事の取得
    # ------------------------------------------------------------------
    post = db.session.get(Post, id)

    if not post:
        flash("指定された記事が見つかりません。")
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. 非公開記事のアクセス制御
    # ------------------------------------------------------------------
    if not post.is_published:
        if not current_user.is_authenticated or post.user_id != current_user.id:
            flash("この記事は非公開に設定されているため閲覧できません。")
            return redirect('/')

    # ------------------------------------------------------------------
    # STEP 3. 本文の前処理（連続空行の展開）
    # ------------------------------------------------------------------
    body_content   = post.body
    has_toc_marker = '[toc]' in body_content

    body_content = _expand_blank_lines(body_content)

    # ------------------------------------------------------------------
    # STEP 4. Markdown → HTML 変換
    # ------------------------------------------------------------------
    md = markdown.Markdown(
        extensions=['toc', 'nl2br'],
        extension_configs={'toc': {'toc_depth': '2-3', 'marker': '[toc]'}}
    )

    display_body = md.convert(body_content)

    # ------------------------------------------------------------------
    # STEP 5. 目次の扱い
    # ------------------------------------------------------------------
    # 本文中に [toc] があれば変換時にその位置へ展開済みなので None、
    # なければ記事冒頭に表示するための目次 HTML を渡す。
    toc_html = None if has_toc_marker else md.toc

    # ------------------------------------------------------------------
    # STEP 6. 画像タグの埋め込み（[img1], [img2] → <img> タグ or <figure> タグ）
    # ------------------------------------------------------------------
    # 【セキュリティ修正】キャプションを markupsafe.escape() でエスケープ
    # キャプションは display_body（| safe で出力される HTML）に
    # 直接文字列連結されるため、" や < を含む入力があると
    # alt 属性を突き破って任意の HTML/属性を注入できてしまっていた。
    # 単一管理者運用でも、自己 XSS・アカウント奪取時の被害拡大防止として
    # 出力時エスケープを徹底する（防御的プログラミング）。
    if post.img_name:
        images   = post.img_name.split(',')
        captions = post.img_captions.split('\t') if post.img_captions else []

        for index, img_file in enumerate(images):
            img_file = re.sub(r'[/\\]', '', img_file.strip())
            raw_caption = captions[index].strip() if index < len(captions) else ''
            caption     = escape(raw_caption)  # HTML 特殊文字（< > & " '）を無害化

            if caption:
                # キャプションあり → <figure> + <figcaption>
                img_tag = (
                    f'<figure class="post-figure">'
                    f'<img src="/static/img/posts/{img_file}" alt="{caption}" style="max-width:100%; height:auto;">'
                    f'<figcaption class="post-figcaption">{caption}</figcaption>'
                    f'</figure>'
                )
            else:
                # キャプションなし → 中央寄せの <img> のみ
                img_tag = (
                    f'<span style="display:block; text-align:center; margin: 15px 0;">'
                    f'<img src="/static/img/posts/{img_file}" style="max-width:100%; height:auto;">'
                    f'</span>'
                )

            display_body = display_body.replace(f'[img{index+1}]', img_tag)

    # ------------------------------------------------------------------
    # STEP 7. 未使用の [imgN] タグを除去
    # ------------------------------------------------------------------
    # マークダウン変換後は [img1] が <p>[img1]</p> になっている場合があるため
    # <p> タグごと除去してから、念のため素の [imgN] タグも除去する。
    display_body = re.sub(r'<p>\[img\d+\]</p>\n?', '', display_body)
    display_body = re.sub(r'\[img\d+\]', '', display_body)

    # ------------------------------------------------------------------
    # STEP 8. 地図タグの変換（[map:場所名] → Google Maps iframe）
    # ------------------------------------------------------------------
    display_body = re.sub(r'\[map:([^\]]+)\]', _replace_map, display_body)

    # ------------------------------------------------------------------
    # STEP 9. YouTube タグの変換
    # ------------------------------------------------------------------
    display_body = re.sub(
        r'(?:<p>)?\[youtube:([^\]]+)\](?:</p>)?',
        _replace_youtube,
        display_body
    )

    # ------------------------------------------------------------------
    # STEP 10. 関連記事の取得とサブラベル生成
    # ------------------------------------------------------------------
    # (10-1) 公開状態の絞り込み条件（ログイン中は自分の非公開記事も対象）
    if current_user.is_authenticated:
        pub_filter = (Post.is_published == True) | (Post.user_id == current_user.id)
    else:
        pub_filter = Post.is_published == True

    related_posts = _get_related_posts(post, pub_filter, max_count=4)

    # (10-2) 関連記事セクションのサブラベル生成
    #        「何を基準に関連付けたか」をユーザーに示す表示用テキスト
    tag_names = [t.name for t in post.hashtags]
    if post.genre and post.genre != '未分類' and tag_names:
        related_sub_label = f'📂 {post.genre} / {"、".join(f"#{n}" for n in tag_names[:2])} を表示中'
    elif post.genre and post.genre != '未分類':
        related_sub_label = f'{post.genre} を表示中'
    elif tag_names:
        related_sub_label = f'{"、".join(f"#{n}" for n in tag_names[:2])} を表示中'
    else:
        related_sub_label = '最新記事を表示中'

    # ------------------------------------------------------------------
    # STEP 11. テンプレートのレンダリング
    # ------------------------------------------------------------------
    return render_template(
        'detail.html',
        post              = post,
        display_body      = display_body,
        toc_html          = toc_html,
        related_posts     = related_posts,
        related_sub_label = related_sub_label,
    )


# ======================================================================
# [6] ジャンル一覧ページ
# ======================================================================

@blog_bp.route('/genre', methods=['GET'])
def genre_list():
    """
    ジャンル一覧ページを表示する。

    【処理の流れ】
      STEP 1. DEFAULT_GENRES を辞書順にソート
      STEP 2. '未分類' が含まれていれば末尾へ移動
      STEP 3. genre.html をレンダリング
    """
    genres_list = sorted(DEFAULT_GENRES)
    if '未分類' in genres_list:
        genres_list.remove('未分類')
        genres_list.append('未分類')
    return render_template('genre.html', genres=genres_list)


# ======================================================================
# [7] 内部ヘルパー関数群
# ======================================================================

# ----------------------------------------------------------------------
# (7-1) 構造行の判定
# ----------------------------------------------------------------------
def _is_structural_line(s: str) -> bool:
    """
    Markdown の「構造行」（空行展開の対象外にすべき行）かどうかを判定する。

    構造行 = 見出し（#）・コードブロック（```）・目次マーカー（[toc]）。
    これらの直前直後の空行は Markdown の構文上の意味を持つため、
    _expand_blank_lines() で <br> に置き換えてはいけない。
    """
    stripped = s.strip()
    return (
        stripped.startswith('#') or
        stripped.startswith('```') or
        stripped == '[toc]'
    )


# ----------------------------------------------------------------------
# (7-2) 連続空行の <br> 展開
# ----------------------------------------------------------------------
def _expand_blank_lines(text: str) -> str:
    """
    本文中の「2 行以上の連続空行」を <br> に展開する。

    通常の Markdown では空行を何行連ねても段落区切り 1 つに潰されるが、
    ブログでは「意図的に行間を空ける」表現ができるようにしたい。
    そこで連続空行の 2 行目以降を <br> に置き換えて行間を保持する。

    【処理の流れ】
      STEP 1. 本文を行単位に分割し、先頭から走査
      STEP 2. 空行の連続をまとめてカウント
      STEP 3. 前後が構造行（見出し等）or 空行 1 行だけなら、そのまま維持
              （Markdown の構文を壊さないため）
      STEP 4. それ以外は「空行 1 行 + <br> ×（連続数 - 1）」に変換
      STEP 5. 行を結合して返す
    """
    lines  = text.split('\n')
    result = []
    i      = 0

    # STEP 1. 先頭から走査
    while i < len(lines):
        line = lines[i]

        if line.strip() == '':
            # STEP 2. 空行の連続をカウント
            blank_count = 0
            while i < len(lines) and lines[i].strip() == '':
                blank_count += 1
                i += 1

            prev_line = result[-1] if result else ''
            next_line = lines[i] if i < len(lines) else ''

            if (_is_structural_line(prev_line) or
                    _is_structural_line(next_line) or
                    blank_count == 1):
                # STEP 3. 構文上意味のある空行はそのまま維持
                result.extend([''] * blank_count)
            else:
                # STEP 4. 2 行目以降の空行を <br> に変換して行間を保持
                result.append('')
                result.extend(['<br>'] * (blank_count - 1))
        else:
            result.append(line)
            i += 1

    # STEP 5. 行を結合して返す
    return '\n'.join(result)


# ----------------------------------------------------------------------
# (7-3) 地図タグの変換
# ----------------------------------------------------------------------
def _replace_map(m: re.Match) -> str:
    """
    [map:場所名] を Google Maps の iframe 埋め込みに変換する。

    【セキュリティ修正】
    1. ラベル表示用の場所名を markupsafe.escape() でエスケープ。
       従来は入力がそのまま HTML に埋め込まれていたため、
       [map:"><script>...] のような入力で div を突き破れた。
    2. iframe の src に埋め込む URL エンコードを
       place.replace(' ', '+') から urllib.parse.quote() に変更。
       replace 方式では " や & などが未エンコードのまま残り、
       属性値の突き破りや意図しないクエリパラメータ注入が可能だった。
       quote() は URL 上安全な文字以外を %XX 形式に正しく変換する。

    【処理の流れ】
      STEP 1. 正規表現マッチから場所名を取り出す
      STEP 2. HTML 出力用（escape）と URL 用（quote）に別々にエンコード
      STEP 3. ラベル + iframe を組み立てた HTML を返す
    """
    # STEP 1. 場所名の取り出し
    place = m.group(1).strip()

    # STEP 2. 用途別エンコード
    place_label = escape(place)          # HTML 出力用（ラベル・表示テキスト）
    encoded     = quote(place, safe='')  # URL クエリ用（すべての予約文字をエンコード）

    # STEP 3. HTML の組み立て
    return (
        f'<div class="post-map-wrapper">'
        f'<div class="post-map-label">📍 {place_label}</div>'
        f'<iframe class="post-map-iframe"'
        f' src="https://maps.google.com/maps?q={encoded}&output=embed&hl=ja"'
        f' loading="lazy" allowfullscreen></iframe>'
        f'</div>'
    )


# ----------------------------------------------------------------------
# (7-4) YouTube 動画 ID の抽出
# ----------------------------------------------------------------------
def _extract_youtube_id(raw: str) -> str | None:
    """
    YouTube の URL / 動画 ID 文字列から 11 文字の動画 ID を抽出する。

    対応形式（STEP 順に判定し、最初にマッチしたものを返す）:
      STEP 1. 通常 URL      : ...watch?v=XXXXXXXXXXX
      STEP 2. 短縮 URL      : youtu.be/XXXXXXXXXXX
      STEP 3. ショート動画  : /shorts/XXXXXXXXXXX
      STEP 4. 埋め込み URL  : /embed/XXXXXXXXXXX
      STEP 5. 動画 ID のみ  : XXXXXXXXXXX（11 文字ちょうど）
      STEP 6. どれにも該当しなければ None
    """
    raw = raw.strip()

    # STEP 1. 通常 URL（?v= または &v=）
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    # STEP 2. 短縮 URL
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    # STEP 3. ショート動画
    m = re.search(r'/shorts/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    # STEP 4. 埋め込み URL
    m = re.search(r'/embed/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    # STEP 5. 動画 ID 単体
    m = re.fullmatch(r'[A-Za-z0-9_-]{11}', raw)
    if m:
        return raw

    # STEP 6. 認識不可
    return None


# ----------------------------------------------------------------------
# (7-5) YouTube タグの変換
# ----------------------------------------------------------------------
def _replace_youtube(m: re.Match) -> str:
    """
    [youtube:URL] をファサード形式の埋め込みに変換する。

    ファサード形式 = 最初はサムネイル画像 + 再生ボタンだけを表示し、
    クリックされたときに初めて iframe を生成する軽量な埋め込み方式。
    （実際の iframe 生成は detail.html の ytPlay() が行う）

    【セキュリティ修正】
    動画 ID を認識できなかった場合のエラーメッセージに
    ユーザー入力（raw）をそのまま埋め込んでいたため、
    [youtube:<script>...] のような入力がそのまま HTML として
    出力される経路になっていた。escape() を適用して無害化する。

    ※ 正常系の video_id は正規表現 [A-Za-z0-9_-]{11} で
       抽出済みのため HTML/URL 上安全な文字しか含まない。

    【処理の流れ】
      STEP 1. 正規表現マッチから URL / ID 文字列を取り出す
      STEP 2. _extract_youtube_id() で動画 ID を抽出
      STEP 3. 抽出失敗 → エスケープ済みエラーメッセージを返す
      STEP 4. 抽出成功 → サムネイル URL / 埋め込み URL を組み立てて
              ファサード HTML を返す
    """
    # STEP 1〜2. 動画 ID の抽出
    raw      = m.group(1)
    video_id = _extract_youtube_id(raw)

    # STEP 3. 抽出失敗時はエスケープ済みメッセージを返す
    if not video_id:
        return f'<p style="color:#c0392b;">[youtube: 動画IDを認識できませんでした → {escape(raw)}]</p>'

    # STEP 4. ファサード HTML の組み立て
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