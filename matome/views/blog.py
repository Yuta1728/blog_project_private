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
# 【キャッシュの無効化（improvement.md 第2版 項目 B-3）】
#   上記のキャッシュには「捨てる手段」が無く、rendering.py を修正しても
#   既存記事は古い HTML のまま表示され続けるという弱点があった。
#   そこで rendering.RENDER_VERSION（レンダラのバージョン）を導入し、
#   各記事は生成時のバージョンを Post.render_version に保持する。
#   detail() は
#       body_html が NULL、または render_version が現在値と不一致
#   のときに再生成して保存するため、rendering.py 変更時は
#   RENDER_VERSION を +1 するだけで既存記事も自動で更新される。
#
# 【N+1 の解消（improvement.md 第2版 項目 B-1）】
#   detail.html は post.user.nickname を参照するが、従来の
#   db.session.get(Post, id) は user を先読みしないため、
#   記事表示のたびに user を取りに行くクエリが 1 本増えていた。
#   joinedload(Post.user) で記事本体と同じ 1 クエリ（JOIN）にまとめる。
#
# 【統計・hero の取得条件の修正（improvement.md 第2版 項目 A-2）】
#   従来 index() は「絞り込みが無ければ」統計 3 クエリ＋管理者取得 1 クエリを
#   実行していたが、テンプレート（index.html）側は
#   「絞り込みが無く、かつ 1 ページ目」のときしか統計・hero を描画しない。
#   そのため 2 ページ目以降のトップページでは、画面に出ないデータのために
#   毎回 4 本の追加クエリが走っていた。
#
#   本ファイルでは判定を show_top_sections という 1 つのフラグに集約し、
#   「テンプレートが描画する条件」と「ビューがクエリを打つ条件」を
#   完全に一致させている。
#
# 【真偽値リテラルの排除（improvement.md 第2版 項目 A-3）】
#   SQLAlchemy 1.4 以降、Python の True / False をそのまま SQL 式として
#   filter() へ渡すのは非推奨のため、sqlalchemy.true() を使う。
#
# 【例外時のログ出力（improvement.md 第2版 項目 A-5）】
#   detail() の遅延バックフィルは失敗しても表示を続ける設計だが、
#   従来は例外を完全に握り潰していたため、書き込みが失敗し続けていても
#   誰も気づけなかった（毎回その場で再変換され、遅いままになる）。
#   current_app.logger で記録を残すよう変更した。
#
# ======================================================================

from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user
from sqlalchemy import func, true          # true(): SQL 式としての「常に真」
from extensions import db
from models import Post, Hashtag, User
from constants import DEFAULT_GENRES, GENRE_GROUPS  # GENRE_GROUPS: ジャンル一覧のグループ描画に使用
from rendering import render_post_body, RENDER_VERSION  # 本文変換とそのバージョン
import config

blog_bp = Blueprint('blog', __name__)


# ======================================================================
# [0] ページネーション設定
# ======================================================================
# 1 ページあたりの表示件数。
# マイページ（views/admin.py の POSTS_PER_PAGE）と同じ 4 件に揃えている。
POSTS_PER_PAGE = 4


# ======================================================================
# [1] トップページ（記事一覧）
# ======================================================================

@blog_bp.route('/', methods=['GET'])
def index():
    """
    記事一覧を表示する。URL クエリパラメータによる
    キーワード検索・ジャンル絞り込み・ハッシュタグ絞り込みに対応。

    【処理の流れ】
      STEP 1. URL クエリパラメータを取得（genre / search / hashtag / page）
      STEP 2. 公開状態でベースクエリを構築
              （ログイン中は自分の非公開記事も含める）
      STEP 3. キーワード・ジャンル・ハッシュタグで絞り込み
      STEP 4. 作成日時の降順でページネーション取得
      STEP 5. トップセクション（統計・hero）を出すかどうかを判定
      STEP 6. ジャンル選択中なら、そのジャンル内のハッシュタグ一覧を取得
      STEP 7. 検索エリア用のジャンル選択肢リストを生成
      STEP 8. トップセクションを出すときだけ統計情報と管理者情報を取得
      STEP 9. index.html をレンダリング
    """
    # ------------------------------------------------------------------
    # STEP 1. URL クエリパラメータの取得
    # ------------------------------------------------------------------
    selected_genre   = request.args.get('genre')
    search_word      = request.args.get('search')
    selected_hashtag = request.args.get('hashtag')

    # ページ番号もここでまとめて取得する。
    # 【A-2】「何ページ目か」は統計クエリを打つかどうかの判定材料でもあるため、
    # 他のクエリパラメータと一緒に先頭で取得する形に整理している。
    page = request.args.get('page', 1, type=int)

    # 絞り込み条件が 1 つでも指定されているか（複数箇所で使うのでここで確定）
    has_filter = bool(selected_genre or search_word or selected_hashtag)

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
    #
    # 【インデックスについて（improvement.md 項目 7）】
    # ここは Post.title.ilike('%word%') のように先頭 % を付けた部分一致のため、
    # 通常の B-Tree インデックスは効かず、そのままだと全表スキャンになる。
    # PostgreSQL では pg_trgm の GIN インデックス
    #   （マイグレーション add_trgm_search_index で
    #     post.title → ix_post_title_trgm / hashtag.name → ix_hashtag_name_trgm を
    #     gin_trgm_ops で作成）
    # により、この ILIKE '%word%' でもインデックスが利用され全表スキャンを
    # 避けられる（検索語がトライグラムを構成できる 3 文字以上のとき）。
    #
    # なお Post.hashtags.any(...) は中間テーブル post_hashtags を経由する
    # EXISTS サブクエリになる。この「タグ側から記事を引く」経路は
    # ix_post_hashtags_hashtag_id（項目 A-1 で追加）が効く。
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
    # 【B-2】記事カードはハッシュタグバッジを表示するため、ここで
    # selectinload によりタグを一括先読みして N+1 を防ぐ。
    #
    # なお models.py 側の lazy='selectin' は撤去し、
    # 「どこで先読みするか」の指定はクエリ側（この options）に一本化した。
    # 従来は両方に指定があり、どちらが効いているのか分かりにくかったうえ、
    # タグを使わない取得（関連記事など）でも無駄な IN クエリが走っていた。
    pagination = (
        query.options(db.selectinload(Post.hashtags))
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=POSTS_PER_PAGE, error_out=False)
    )
    posts = pagination.items

    # ------------------------------------------------------------------
    # STEP 5. トップセクション（統計・hero・「最新の記事」見出し）の表示判定
    # ------------------------------------------------------------------
    # 【A-2】条件は「絞り込みなし かつ 1 ページ目」。これは index.html が
    # stats.html / hero.html / 「📋 最新の記事」見出しを描画する条件と
    # まったく同じもので、このフラグをテンプレートにも渡すことで
    #   ・ビューが無駄なクエリを打たない
    #   ・ビューとテンプレートの条件がずれない
    # の両方を担保する。
    #
    # ページ番号は request.args の生値ではなく pagination.page を使う。
    # paginate(error_out=False) は不正な値（0 や負数）を 1 に丸めるため、
    # テンプレート側の pagination.page == 1 と確実に一致させられる。
    show_top_sections = (not has_filter) and pagination.page == 1

    # ------------------------------------------------------------------
    # STEP 6. ジャンル選択中: そのジャンル内で使われているハッシュタグ一覧
    #         （タグ絞り込みバーの表示用）
    # ------------------------------------------------------------------
    # このクエリは Hashtag → post_hashtags → Post の JOIN であり、
    # 「タグ側から記事を引く」代表例。ix_post_hashtags_hashtag_id（項目 A-1）が効く。
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
    # STEP 7. インページ検索エリア用ジャンルリストの生成
    # ------------------------------------------------------------------
    # search_area.html の <select> に渡す選択肢。
    # DEFAULT_GENRES をベースに、実際に記事が存在するジャンルだけを残す。
    # これにより「記事がないジャンル」を選択肢から除外できる。
    #
    # 表示順: DEFAULT_GENRES の並び順を優先し、
    #         それ以外（管理者が独自追加したジャンル）は末尾に辞書順で追加。
    #
    # ※ 検索エリアは絞り込みの有無やページ番号に関わらず常に表示されるため、
    #   このクエリは STEP 8 の統計とは異なり毎回実行する必要がある。
    #
    # 【A-3】ログイン中は「公開状態で絞らない」＝ WHERE 句に何も足さない、
    # という意味の条件になる。従来はここに Python の True をそのまま
    # 渡していたが、SQLAlchemy 1.4 以降は非推奨のため、
    # SQL 式としての「常に真」を表す sqlalchemy.true() を使う。
    pub_condition = (Post.is_published == True) if not current_user.is_authenticated else true()
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
    # STEP 8. トップセクションを表示するときだけ統計情報・管理者情報を取得
    # ------------------------------------------------------------------
    # 【A-2】show_top_sections（＝絞り込みなし かつ 1 ページ目）に条件を絞り、
    # 2 ページ目以降のトップページから 4 本のクエリを丸ごと削減している。
    stats      = None
    admin_user = None
    if show_top_sections:
        # (8-1) 公開記事の総数
        post_count = Post.query.filter(Post.is_published == True).count()

        # (8-2) 公開記事に付いているハッシュタグの種類数
        #        JOIN + COUNT DISTINCT でこの中では最も重いクエリ。
        #        中間テーブルの走査には ix_post_hashtags_hashtag_id が効く。
        hashtag_count = (
            db.session.query(func.count(func.distinct(Hashtag.id)))
            .join(Hashtag.posts)
            .filter(Post.is_published == True)
            .scalar()
        )

        # (8-3) 最終更新日
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
        # (8-4) hero セクション表示用の管理者情報
        admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()

    # ------------------------------------------------------------------
    # STEP 9. テンプレートのレンダリング
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
        # 【A-2】統計・hero・「最新の記事」見出しの表示可否。
        # ビューがクエリを打った条件そのものを渡すことで、
        # 「クエリは打っていないのにテンプレートが描画しようとする」
        # というずれを構造的に防ぐ。
        show_top_sections = show_top_sections,
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

    STEP 1 / STEP 2 の Post.hashtags.any(...) は中間テーブルを経由する
    EXISTS サブクエリであり、ix_post_hashtags_hashtag_id（項目 A-1）が効く。

    【B-2 の副次効果】
    関連記事カード（detail.html の .related-card）はタイトル・日付・
    サムネイルしか表示せず、ハッシュタグを使わない。
    models.py の lazy='selectin' を外したことで、ここで取得した記事に対する
    「タグ先読みの IN クエリ」が発行されなくなった（最大 4 本の削減）。

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
    # 【A-3】「タグが 1 つも無ければ、そもそも “同じタグを持つ記事” は存在しない」
    # ため、tag_names のチェックを実行条件（if）側に置く。
    # これにより非推奨の真偽値リテラルを filter() に渡さずに済み、
    # 結果が必ず空と分かっているクエリ 1 本も省ける。
    if remaining > 0 and tag_names:
        step1 = (
            Post.query
            .filter(
                pub_filter,
                Post.id.notin_(seen_ids),
                Post.genre == post.genre,
                Post.hashtags.any(Hashtag.name.in_(tag_names)),
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

    ただし次のいずれかに該当する場合は、その場で生成し直して
    ベストエフォートで保存（遅延バックフィル）してから表示する。
      ・body_html が NULL（この機能の導入前に作られた既存記事）
      ・render_version が現在の RENDER_VERSION と一致しない
        （rendering.py を変更してバージョンを上げた後の初回アクセス）

    【処理の流れ】
      STEP 1. 記事を取得（投稿者を joinedload で同時取得）。無ければトップへ
      STEP 2. 非公開記事は投稿者本人以外を弾く
      STEP 3. キャッシュ済み本文 HTML を取得（未生成・旧版なら生成 + 遅延保存）
      STEP 4. 関連記事とサブラベルを生成
      STEP 5. detail.html をレンダリング
    """
    # ------------------------------------------------------------------
    # STEP 1. 記事の取得
    # ------------------------------------------------------------------
    # 【B-1】detail.html は post.user.nickname を参照するため、
    # 従来の db.session.get(Post, id) では user 取得のクエリが 1 本増えていた。
    # joinedload(Post.user) を指定して記事本体と同じ 1 クエリ（LEFT JOIN）に
    # まとめる。
    #
    # あわせて post.hashtags（メタ情報のタグバッジ・関連記事の判定に使う）も
    # selectinload で先読みしておく。
    # models.py 側の lazy='selectin' を外した（B-2）ため、
    # ここで明示しないとタグ参照時に追加クエリが走る点に注意。
    post = (
        Post.query
        .options(
            db.joinedload(Post.user),
            db.selectinload(Post.hashtags),
        )
        .filter(Post.id == id)
        .first()
    )

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
    # 【B-3】キャッシュが「使える」条件は次の 2 つを同時に満たすこと。
    #   (1) body_html が保存済み（非 NULL）である
    #   (2) その HTML を生成したレンダラのバージョンが現在値と一致する
    #
    # (2) を加えたことで、rendering.py を修正して RENDER_VERSION を上げれば、
    # 既存記事も次のアクセス時に自動で作り直される。
    # render_version が NULL のレコード（この仕組みの導入前に作られた記事）は
    # 必ず不一致になるため、そのまま再生成の対象になる。
    is_cache_valid = (
        post.body_html is not None
        and post.render_version == RENDER_VERSION
    )

    if is_cache_valid:
        display_body = post.body_html
        toc_html     = post.toc_html
    else:
        display_body, toc_html = render_post_body(
            post.body, post.img_name, post.img_captions
        )
        # 遅延バックフィル: 生成結果を保存して次回以降の再変換を無くす。
        # GET 中の書き込みだが、キャッシュのウォームアップとして許容する。
        # 失敗しても「表示は続ける」方針は変えない（本文はすでに手元にある）。
        #
        # 【A-5】従来は例外を完全に握り潰していたため、
        # 書き込みが失敗し続けていても誰も気づけなかった。
        # 保存できないと毎回その場で再変換が走り、
        # 「なぜか詳細ページだけ遅い」状態が延々と続いてしまう。
        # ここでログを残しておけば、Error log を見るだけで
        # 「バックフィルに失敗している」と分かる。
        try:
            post.body_html      = display_body
            post.toc_html       = toc_html
            post.render_version = RENDER_VERSION   # 【B-3】生成に使ったバージョンを記録
            db.session.commit()
            current_app.logger.info(
                '本文 HTML を再生成して保存しました (post_id=%s, render_version=%s)',
                post.id, RENDER_VERSION
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                '本文 HTML の遅延バックフィルに失敗しました (post_id=%s)。'
                '表示は継続しますが、次回以降も毎回変換が発生します。', post.id
            )

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
    #
    # ※ こちらは index() STEP 7 と違い、ログイン時も
    #   「公開記事 OR 自分の記事」という SQL 式になるため、
    #   真偽値リテラルは登場しない（A-3 の対象外）。
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