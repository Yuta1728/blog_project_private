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
#   [5] detail()             : 記事詳細ページ（キャッシュ済み本文 HTML を出力）
#   [6] genre_list()         : ジャンル一覧ページ
#
# 【本文レンダリングの方針変更（improvement.md 項目 5）】
#   以前 detail() は本文（Markdown + [imgN]/[map:]/[youtube:] などの独自タグ）を
#   アクセスのたびに変換していた。本文は投稿・編集時にしか変わらないため、
#   変換ロジックは rendering.py の render_post_body() に切り出し、
#     ・投稿時（views/admin.py の create）
#     ・編集時（views/admin.py の update）
#   に生成した結果を Post.body_html / Post.toc_html に保存する方式へ変更した。
#   detail() は保存済み HTML をそのまま出力するだけになり、毎回の再変換が消える。
#
#   この機能の導入前に作成された既存記事は body_html が NULL のため、
#   detail() 側で「NULL ならその場で生成し、ベストエフォートで保存（バックフィル）」
#   してからレンダリングする。
#
# ======================================================================

from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user
from sqlalchemy import func
from extensions import db
from models import Post, Hashtag, User
from constants import DEFAULT_GENRES, GENRE_GROUPS  # GENRE_GROUPS: ジャンル一覧のグループ描画に使用
from rendering import render_post_body              # 本文 → (body_html, toc_html) 変換
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
        # max(coalesce(updated_at, created_at)) で
        # 「更新日時があればそれ、なければ投稿日時」の最大値を 1 クエリで取得する。
        # これにより NULL の影響を受けず、新規投稿も更新として扱われる。
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
    記事を取得し、キャッシュ済みの本文 HTML（body_html / toc_html）を表示する。
    非公開記事は管理者のみ閲覧可能。

    【本文レンダリングの扱い】
    本文 HTML は投稿・編集時に rendering.render_post_body() で生成され、
    Post.body_html / Post.toc_html に保存されている。ここではそれを
    そのまま出力するだけなので、アクセスのたびの再変換が発生しない。

    ただしこの機能の導入前に作られた既存記事は body_html が NULL のため、
    その場で生成し、ベストエフォートで保存（遅延バックフィル）してから表示する。

    【処理の流れ】
      STEP 1. 記事を取得。存在しなければトップへリダイレクト
      STEP 2. 非公開記事は投稿者本人以外を弾く
      STEP 3. キャッシュ済み本文 HTML を取得（NULL なら生成 + 遅延保存）
      STEP 4. 関連記事とサブラベルを生成
      STEP 5. detail.html をレンダリング
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
    # STEP 3. 本文 HTML・目次 HTML の取得
    # ------------------------------------------------------------------
    # body_html が保存済み（非 NULL）ならそのまま使う。
    # 未生成（既存記事など）の場合のみ、その場で生成する。
    if post.body_html is not None:
        display_body = post.body_html
        toc_html     = post.toc_html
    else:
        display_body, toc_html = render_post_body(
            post.body, post.img_name, post.img_captions
        )
        # 遅延バックフィル: 生成結果を保存して次回以降の再変換を無くす。
        # GET 中の書き込みだが、キャッシュのウォームアップとして許容する。
        # 失敗しても表示は継続させたいので、例外は握りつぶして rollback する。
        try:
            post.body_html = display_body
            post.toc_html  = toc_html
            db.session.commit()
        except Exception:
            db.session.rollback()

    # ------------------------------------------------------------------
    # STEP 4. 関連記事の取得とサブラベル生成
    # ------------------------------------------------------------------
    # (4-1) 公開状態の絞り込み条件（ログイン中は自分の非公開記事も対象）
    if current_user.is_authenticated:
        pub_filter = (Post.is_published == True) | (Post.user_id == current_user.id)
    else:
        pub_filter = Post.is_published == True

    related_posts = _get_related_posts(post, pub_filter, max_count=4)

    # (4-2) 関連記事セクションのサブラベル生成
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
    # STEP 5. テンプレートのレンダリング
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

    グループ構造は constants.GENRE_GROUPS に一元化し、そのまま genre.html に渡す。
    「DB に実在するがプリセットに無いジャンル（＝ユーザー独自作成分）」は
    extra_genres として集約し、テンプレート側の「その他」グループに表示する。

    【処理の流れ】
      STEP 1. 公開状態を考慮して、記事で実際に使われているジャンルを取得
      STEP 2. プリセット（DEFAULT_GENRES）と '未分類' を除いた
              「独自ジャンル」を辞書順に整理
      STEP 3. GENRE_GROUPS（グループ定義）と extra_genres を渡して描画
    """
    # ------------------------------------------------------------------
    # STEP 1. 記事で使われているジャンルを取得（公開状態を考慮）
    # ------------------------------------------------------------------
    # 未ログイン: 公開記事のジャンルのみ
    # ログイン中: 公開記事 + 自分の記事のジャンル
    if current_user.is_authenticated:
        pub_condition = (Post.is_published == True) | (Post.user_id == current_user.id)
    else:
        pub_condition = (Post.is_published == True)

    used_genres_raw = (
        db.session.query(Post.genre)
        .filter(pub_condition, Post.genre != None, Post.genre != '')
        .distinct()
        .all()
    )
    used_genres_set = {g[0] for g in used_genres_raw}

    # ------------------------------------------------------------------
    # STEP 2. 独自ジャンル（プリセット・未分類を除く）を辞書順に整理
    # ------------------------------------------------------------------
    known = set(DEFAULT_GENRES) | {'未分類'}
    extra_genres = sorted(used_genres_set - known)

    # ------------------------------------------------------------------
    # STEP 3. テンプレートのレンダリング
    # ------------------------------------------------------------------
    return render_template(
        'genre.html',
        genre_groups = GENRE_GROUPS,   # プリセットのグループ定義（唯一の情報源）
        extra_genres = extra_genres,   # ユーザーが独自作成した実在ジャンル
    )