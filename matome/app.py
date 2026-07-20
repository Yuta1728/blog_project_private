# ======================================================================
# app.py — Flask アプリケーションのエントリーポイント
# ======================================================================
#
# 【役割】
#   Flask アプリを生成・設定する起点となるファイル。
#   create_app() 関数でアプリを組み立てる「Application Factory パターン」を採用。
#
#   Application Factory パターンのメリット:
#     - テスト時に設定を変えた別アプリを簡単に作れる
#     - extensions.py と組み合わせることで循環インポートを避けられる
#
# 【このファイルの構成（目次）】
#   [1] import / Blueprint の読み込み
#   [2] _is_production()      : 本番環境かどうかの判定ヘルパー
#   [3] _configure_logging()  : アプリケーションログの設定（improvement.md 第2版 項目 A-5）
#   [3.5] _register_static_url_helper(): static_url の登録（improvement.md 第2版 項目 A-7）
#   [4] _register_cli_commands(): 管理コマンドの登録（improvement.md 第2版 項目 B-3）
#   [5] create_app()          : アプリ生成ファクトリ関数
#        (5-1) 本番判定
#        (5-2) ログ設定
#        (5-3) ProxyFix の適用（リバースプロキシ対応）
#        (5-4) SECRET_KEY の設定
#        (5-5) セッション Cookie の属性設定
#        (5-6) アップロードサイズ制限
#        (5-7) データベース接続 URL の設定（PostgreSQL / SQLite 両対応）
#        (5-7.5) static_url の登録（A-7）
#        (5-8) 拡張機能の初期化（db / migrate / login_manager）
#        (5-9) CSRF 保護の適用
#        (5-10) Flask-Login の詳細設定（unauthorized_handler / user_loader）
#        (5-11) セキュリティヘッダーの付与
#        (5-12) カスタムエラーハンドラー（413）
#        (5-13) Blueprint の登録
#        (5-14) 管理コマンドの登録
#   [6] 直接実行時のエントリポイント（python app.py）
#
# 【処理フロー図】
#
#   python app.py 実行
#        │
#        ▼
#   create_app() ──► Flask インスタンス生成
#        │              │
#        │              ├─ (5-1)〜(5-2) 本番判定・ログ設定（最優先で有効化）
#        │              ├─ (5-3)〜(5-7) 各種設定（プロキシ・鍵・Cookie・DB）
#        │              ├─ (5-8)〜(5-9) 拡張機能を app に紐付け
#        │              ├─ (5-10)〜(5-12) 認証まわり・ヘッダー・エラー処理
#        │              ├─ (5-13) Blueprint 登録（auth / blog / admin）
#        │              └─ (5-14) CLI コマンド登録（rerender-posts）
#        ▼
#   app.run() ──► リクエスト待ち受け開始
#
# ======================================================================


# ======================================================================
# [1] import / Blueprint の読み込み
# ======================================================================

import os
import sys
import logging
import click                                       # CLI コマンドのオプション定義に使用
from flask import Flask, flash, redirect, url_for, abort
from flask.logging import default_handler          # Flask が既定で付ける StreamHandler
from flask_wtf.csrf import CSRFProtect  # 全フォームへの CSRF トークン強制適用
from werkzeug.middleware.proxy_fix import ProxyFix  # リバースプロキシ配下での HTTPS 判定補正
from extensions import db, login_manager, migrate
from models import User, Post
from rendering import render_post_body, RENDER_VERSION
import config

# Blueprint: 機能ごとにルートをまとめたモジュール（views/ 配下で定義）
from views.auth  import auth_bp   # ログイン・ログアウト関連
from views.blog  import blog_bp   # 一般公開ページ（一覧・詳細・ジャンル）
from views.admin import admin_bp  # 管理者専用ページ（投稿・編集・削除・マイページ）


# ======================================================================
# [2] 本番環境判定ヘルパー
# ======================================================================

def _is_production() -> bool:
    """
    現在の実行環境が「本番」かどうかを判定する。

    判定条件:
      - DATABASE_URL が設定されている（PaaS の PostgreSQL 等）か
      - FLASK_ENV=production が設定されている
    のいずれかであれば本番とみなす。

    【PythonAnywhere での注意】
      SQLite 運用（USE_SQLITE=1）では DATABASE_URL を設定しないため、
      必ず環境変数に FLASK_ENV=production を設定して本番扱いにすること。
      これにより SECRET_KEY の必須化・Secure Cookie が有効になる。

    【関数化した理由】
      従来この判定式は create_app() の中と __main__ ブロックの 2 か所に
      同じ内容で書かれていた。条件を変更する際の修正漏れを防ぐため、
      1 か所に集約する。
    """
    return (
        os.getenv("DATABASE_URL") is not None
        or os.getenv("FLASK_ENV") == "production"
    )


# ======================================================================
# [3] ログ設定（improvement.md 第2版 項目 A-5）
# ======================================================================

def _configure_logging(app: Flask, is_production: bool) -> None:
    """
    アプリケーションログ（app.logger）の出力先とフォーマットを設定する。

    【背景】
    従来このアプリはログ設定を一切持たず、各ビューの
        except Exception:
            db.session.rollback()
            flash('エラーが発生しました', 'danger')
    のような箇所で例外を握り潰していた。
    ユーザーには「エラーが発生しました」と表示されるが、
    サーバー側には原因（トレースバック）が一切残らないため、
    「投稿できない」「画像が保存できない」といった障害が起きても
    何が起きたのか調べる手段がなかった。

    【この設定でやること】
    標準エラー出力（stderr）へ、時刻・レベル・発生場所つきで出力する
    ハンドラを 1 つ登録する。各ビューは
        current_app.logger.exception('...')
    を呼ぶだけで、メッセージとトレースバックがここへ流れる。

    【なぜ stderr なのか】
    PythonAnywhere は WSGI プロセスの stderr をそのまま
    「Error log」に書き出す。ローカル開発でもコンソールに出るため、
    追加の設定なしに本番・開発の双方でログを確認できる。
    ファイル出力が必要になった場合は、ここに
    RotatingFileHandler を追加すればよい（呼び出し側は変更不要）。

    【ログレベル】
      環境変数 LOG_LEVEL があればそれを優先。
      無ければ 本番 = INFO / 開発 = DEBUG。
      logger.exception() は ERROR レベルなので、
      どの設定でも障害の記録は必ず残る。

    @param app:           設定対象の Flask アプリ
    @param is_production: 本番環境かどうか（既定レベルの決定に使う）
    """
    # ------------------------------------------------------------------
    # STEP 1. 出力レベルの決定
    # ------------------------------------------------------------------
    level_name = os.getenv('LOG_LEVEL', 'INFO' if is_production else 'DEBUG').upper()
    # 不正な値（タイポなど）が入っていても落ちないよう INFO にフォールバックする
    level = getattr(logging, level_name, logging.INFO)

    # ------------------------------------------------------------------
    # STEP 2. Flask 既定のハンドラを外す
    # ------------------------------------------------------------------
    # app.logger は初回アクセス時に Flask が default_handler を自動で付ける。
    # そのまま自前のハンドラを追加すると同じログが 2 行出てしまうため、
    # 既定のものを取り除いてから登録する。
    app.logger.removeHandler(default_handler)

    # ------------------------------------------------------------------
    # STEP 3. 自前のハンドラを登録（多重登録の防止つき）
    # ------------------------------------------------------------------
    # create_app() はテスト等で複数回呼ばれることがある。app.logger は
    # アプリ名ごとの共有ロガーのため、素直に addHandler すると
    # 呼ばれるたびにハンドラが増え、ログが 2 行・3 行と重複していく。
    # 目印の属性を付けておき、既に自前ハンドラがあれば付け替える。
    for handler in list(app.logger.handlers):
        if getattr(handler, '_mitoblog_handler', False):
            app.logger.removeHandler(handler)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    stream_handler._mitoblog_handler = True   # 多重登録判定用の目印

    app.logger.addHandler(stream_handler)
    app.logger.setLevel(level)

    # ルートロガーへ伝播させない（伝播すると環境によっては二重出力になる）
    app.logger.propagate = False

    app.logger.info('ログ設定を初期化しました (level=%s, production=%s)',
                    level_name, is_production)


# ======================================================================
# [3.5] 静的ファイルのキャッシュバスティング（improvement.md 第2版 項目 A-7）
# ======================================================================

def _register_static_url_helper(app: Flask) -> None:
    """
    テンプレートから使う static_url() を登録し、静的ファイルのキャッシュ期間を延ばす。

    【背景・なぜ必要か（項目 A-7）】
    各テンプレートは A-7 の対応で、静的ファイルの参照を
        url_for('static', filename='css/index.css')
    から
        static_url('css/index.css')
    へ書き換えている。しかし呼び出される側の static_url は Flask/Jinja の
    標準関数ではなく「このアプリが自分で用意する関数」であり、
    ここで @app.template_global として登録して初めてテンプレートから使える。

    登録し忘れると、テンプレートは未定義の関数を呼ぶことになり
        jinja2.exceptions.UndefinedError: 'static_url' is undefined
    になる（＝テンプレートだけ A-7 化して app.py が未対応の状態で起きる）。

    【static_url が何をするか】
    ファイルの更新時刻（mtime）を ?v=... というクエリとして URL に付ける。
        /static/css/index.css?v=1721500000
    ファイルを更新すると mtime が変わり URL も変わるため、
    ブラウザは「別ファイル」とみなして新しい内容を取得する。
    これにより、静的ファイルを長期間キャッシュさせても
    「更新したのに古い CSS が残る」問題が起きない
    （＝Ctrl+Shift+R での強制リロードが不要になる）。

    あわせて SEND_FILE_MAX_AGE_DEFAULT を 1 年に設定し、
    静的ファイルに長期キャッシュを効かせる（?v= が付くので安全）。

    @param app: 対象の Flask アプリ
    """
    # 静的ファイルのブラウザキャッシュ期間を 1 年に延ばす。
    # URL に ?v=mtime が付くため、更新時は URL が変わって即反映される。
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 60 * 60 * 24 * 365  # 1 年（秒）

    @app.template_global()
    def static_url(filename: str) -> str:
        """
        テンプレート用ヘルパー。url_for('static', ...) に ?v=mtime を付けて返す。

        使い方（テンプレート側）:
            href="{{ static_url('css/index.css') }}"

        - ファイルが存在すれば mtime（更新時刻の整数秒）を v として付与する。
        - 何らかの理由でファイルが見つからない場合は v=0 とし、
          少なくとも url_for と同等の URL を返して 500 を避ける
          （存在しないパスは元々 404 になるだけで、ここでは落とさない）。
        """
        try:
            path = os.path.join(app.static_folder, filename)
            version = int(os.path.getmtime(path)) if os.path.exists(path) else 0
        except OSError:
            # 稀な I/O エラーでもテンプレート描画を止めない
            version = 0
        return url_for('static', filename=filename, v=version)


# ======================================================================
# [4] 管理コマンドの登録（improvement.md 第2版 項目 B-3）
# ======================================================================

def _register_cli_commands(app: Flask) -> None:
    """
    `flask <コマンド名>` で実行できる管理コマンドを登録する。

    【なぜ必要か】
    記事本文の HTML は Post.body_html にキャッシュされており、
    rendering.py を修正しただけでは既存記事に反映されない。
    detail() 側の「バージョン不一致なら再生成」で自動的に追従はするが、
    それはあくまで「その記事にアクセスがあったとき」なので、

      ・記事数が多く、アクセスの少ない記事がいつまでも古いままになる
      ・最初の 1 人だけ変換待ちが発生する（ウォームアップ）
      ・そもそも本当に全記事が更新できるのか事前に確認したい

    といった場面では、まとめて作り直せるコマンドがあると安心できる。

    【使い方】
        flask rerender-posts           … 未生成 or 旧バージョンの記事だけ再生成
        flask rerender-posts --all     … バージョンに関係なく全記事を再生成
        flask rerender-posts --dry-run … 対象件数を数えるだけで保存しない

    ※ Flask の CLI はアプリを見つける必要があるため、実行前に
      環境変数 FLASK_APP=app.py を設定するか、
      プロジェクト直下（app.py のある場所）で実行すること。
    """

    @app.cli.command('rerender-posts')
    @click.option('--all', 'rerender_all', is_flag=True, default=False,
                  help='バージョンに関係なく全記事を再生成する。')
    @click.option('--dry-run', 'dry_run', is_flag=True, default=False,
                  help='対象を表示するだけで DB には保存しない。')
    def rerender_posts(rerender_all: bool, dry_run: bool):
        """記事本文のキャッシュ HTML（body_html / toc_html）を再生成する。"""

        # --------------------------------------------------------------
        # STEP 1. 全記事を取得して対象を絞り込む
        # --------------------------------------------------------------
        # 「render_version != RENDER_VERSION」を SQL で書くと、
        # NULL との比較結果が NULL になり NULL 行が対象から漏れる。
        # 記事数が数千件規模になるまでは全件走査で十分なので、
        # 判定は Python 側で明示的に行う（NULL の扱いを間違えない）。
        posts = Post.query.order_by(Post.id).all()

        targets = [
            p for p in posts
            if rerender_all
            or p.body_html is None
            or p.render_version != RENDER_VERSION
        ]

        click.echo(f'全記事: {len(posts)} 件 / 再生成の対象: {len(targets)} 件 '
                   f'(RENDER_VERSION = {RENDER_VERSION})')

        if not targets:
            click.echo('再生成が必要な記事はありません。')
            return

        if dry_run:
            for p in targets:
                click.echo(f'  [dry-run] post_id={p.id} '
                           f'version={p.render_version} title={p.title[:30]!r}')
            click.echo('--dry-run のため保存は行いませんでした。')
            return

        # --------------------------------------------------------------
        # STEP 2. 1 件ずつ再生成して render_version を更新
        # --------------------------------------------------------------
        for p in targets:
            p.body_html, p.toc_html = render_post_body(
                p.body, p.img_name, p.img_captions
            )
            p.render_version = RENDER_VERSION
            # updated_at は「記事内容の更新日時」なので、
            # 表示上の HTML を作り直しただけのここでは触らない。

        # --------------------------------------------------------------
        # STEP 3. まとめて commit
        # --------------------------------------------------------------
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('本文 HTML の一括再生成に失敗しました。')
            raise click.ClickException(
                '再生成の保存に失敗しました。詳細はログを確認してください。'
            )

        click.echo(f'{len(targets)} 件の記事を再生成しました。')


# ======================================================================
# [5] create_app() : アプリ生成ファクトリ関数
# ======================================================================

def create_app():
    """
    Flask アプリインスタンスを生成して返すファクトリ関数。
    """

    # ------------------------------------------------------------------
    # STEP 1. Flask インスタンスを生成
    # ------------------------------------------------------------------
    app = Flask(__name__)

    # ------------------------------------------------------------------
    # STEP 2. 本番環境かどうかを判定（以降の設定で共用する）
    # ------------------------------------------------------------------
    is_production = _is_production()

    # ------------------------------------------------------------------
    # STEP 3. 【A-5】ログ設定（できるだけ早い段階で有効化する）
    # ------------------------------------------------------------------
    # 以降の初期化処理（DB 接続設定など）で問題が起きたときも
    # ログに残るよう、他の設定より先に済ませておく。
    _configure_logging(app, is_production)

    # ------------------------------------------------------------------
    # STEP 4. 【セキュリティ改善①】ProxyFix の適用（リバースプロキシ対応）
    # ------------------------------------------------------------------
    # Render / Heroku / PythonAnywhere などでは、HTTPS はリバースプロキシで
    # 終端され、Flask アプリ自体には HTTP で届く。そのままだと
    # request.is_secure が本番でも False と判定されてしまうため、
    # ProxyFix で X-Forwarded-Proto / X-Forwarded-Host を信頼して補正する。
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ------------------------------------------------------------------
    # STEP 5. SECRET_KEY の設定（セッション・CSRF トークンの署名に使用）
    # ------------------------------------------------------------------
    secret_key = os.getenv("SECRET_KEY")

    if not secret_key:
        if is_production:
            raise ValueError("【重大なエラー】本番環境の環境変数 'SECRET_KEY' が設定されていません。")
        else:
            secret_key = "dev-secret-key-for-local-use"

    app.config['SECRET_KEY'] = secret_key

    # ------------------------------------------------------------------
    # STEP 6. 【セキュリティ修正】セッション Cookie の属性を明示的に設定
    # ------------------------------------------------------------------
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE']   = is_production

    # ------------------------------------------------------------------
    # STEP 7. ファイルアップロードサイズ制限（30MB）
    # ------------------------------------------------------------------
    app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB

    # ------------------------------------------------------------------
    # STEP 8. データベース接続 URL の設定（PostgreSQL / SQLite 両対応）
    # ------------------------------------------------------------------
    # 優先順位:
    #   (1) DATABASE_URL が設定されていれば最優先（Postgres でも SQLite でも可）
    #   (2) USE_SQLITE=1 なら、プロジェクト内 instance/blog.db を SQLite として使う
    #       （PythonAnywhere 無料枠向け。永続ディスクに DB ファイルが残る）
    #   (3) どちらもなければローカル開発（docker-compose の PostgreSQL）に接続
    #
    # 【PythonAnywhere 無料枠での使い方】
    #   環境変数に USE_SQLITE=1 を設定するだけでよい。
    #   DB ファイルの絶対パスは app.py の位置から自動計算するので、
    #   長い sqlite:////home/... のようなパスを手で書く必要はない。
    database_url = os.getenv("DATABASE_URL")
    use_sqlite   = os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes")

    if database_url:
        # (1) 明示指定を最優先
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.logger.info('DB 接続先: DATABASE_URL（明示指定）を使用します。')

    elif use_sqlite:
        # (2) SQLite（PythonAnywhere など）
        basedir      = os.path.abspath(os.path.dirname(__file__))
        instance_dir = os.path.join(basedir, 'instance')
        os.makedirs(instance_dir, exist_ok=True)   # instance/ がなければ作成
        sqlite_path  = os.path.join(instance_dir, 'blog.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_path}"
        app.logger.info('DB 接続先: SQLite (%s)', sqlite_path)

    else:
        # (3) ローカル開発用フォールバック（docker-compose の PostgreSQL）
        local_db_url = (
            f"postgresql+psycopg://{config.postgre_user}:{config.postgre_password}"
            f"@localhost:15432/{config.postgre_DB}"
        )
        app.config['SQLALCHEMY_DATABASE_URI'] = local_db_url
        app.logger.info('DB 接続先: ローカル PostgreSQL (localhost:15432)')

    # モデル変更のたびにイベントを発行する機能（使わないのでオフにしてメモリ節約）
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ------------------------------------------------------------------
    # STEP 8.5. 【A-7】静的ファイルのキャッシュバスティング（static_url 登録）
    # ------------------------------------------------------------------
    # テンプレートが static_url('...') を呼べるようにする。
    # これを登録しないと base.html などで
    #   UndefinedError: 'static_url' is undefined
    # になる（テンプレートだけ A-7 化して app.py が未対応の状態）。
    _register_static_url_helper(app)

    # ------------------------------------------------------------------
    # STEP 9. 拡張機能の初期化（extensions.py で作ったインスタンスを app に紐付け）
    # ------------------------------------------------------------------
    db.init_app(app)             # SQLAlchemy を app に接続
    migrate.init_app(app, db)    # Alembic マイグレーションを app + db に接続
    login_manager.init_app(app)  # Flask-Login を app に接続

    # ------------------------------------------------------------------
    # STEP 10. CSRF 保護の適用
    # ------------------------------------------------------------------
    csrf = CSRFProtect()
    csrf.init_app(app)

    # ------------------------------------------------------------------
    # STEP 11. Flask-Login の詳細設定
    # ------------------------------------------------------------------
    login_manager.login_view = None

    @login_manager.unauthorized_handler
    def unauthorized():
        # 未ログイン状態で @login_required なページへアクセスされた場合、
        # ログインページへ誘導せず 404 Not Found を返して存在を偽装する。
        abort(404)

    @login_manager.user_loader
    def load_user(user_id):
        # 【非推奨 API の置き換え（improvement.md 項目 6）】
        # 従来の User.query.get() は SQLAlchemy 2.0 で Legacy 扱いのため、
        # 主キー取得の推奨 API である db.session.get() に変更する。
        # 挙動（主キーで 1 件取得。無ければ None）は従来と同じ。
        return db.session.get(User, int(user_id))

    # ------------------------------------------------------------------
    # STEP 12. 【セキュリティ修正】セキュリティヘッダーの付与
    # ------------------------------------------------------------------
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    # ------------------------------------------------------------------
    # STEP 13. カスタムエラーハンドラー: 413 Request Entity Too Large
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def request_entity_too_large(error):
        app.logger.warning('アップロードサイズ超過を検出しました (limit=%s bytes)',
                           app.config.get('MAX_CONTENT_LENGTH'))
        flash("アップロードされたファイルの合計サイズが30MBを超えています。", "danger")
        return redirect(url_for('admin.mypage'))

    # ------------------------------------------------------------------
    # STEP 14. Blueprint の登録
    # ------------------------------------------------------------------
    app.register_blueprint(auth_bp)   # /login, /logout 系
    app.register_blueprint(blog_bp)   # /, /about, /howto, /genre, /<id>/detail 系
    app.register_blueprint(admin_bp)  # /create, /<id>/update, /<id>/delete, /mypage 系

    # ------------------------------------------------------------------
    # STEP 15. 【B-3】管理コマンドの登録（flask rerender-posts）
    # ------------------------------------------------------------------
    _register_cli_commands(app)

    app.logger.info('アプリケーションの初期化が完了しました。')

    return app


# ======================================================================
# [6] 直接実行時のエントリポイント（python app.py で起動）
# ======================================================================
#
# 【重要】PythonAnywhere では app.run() は使われない。
#   PythonAnywhere は WSGI ファイルから create_app() を呼び出して
#   application 変数として公開する方式のため、この __main__ ブロックは
#   ローカル開発でのみ実行される（サーバー上では import されるだけ）。

if __name__ == '__main__':
    app = create_app()

    # 本番判定は _is_production() に一本化した（従来はここに同じ式を再掲していた）
    debug_mode = (
        not _is_production()
        and os.getenv("FLASK_DEBUG", "").lower() in ("1", "true")
    )

    app.run(debug=debug_mode)