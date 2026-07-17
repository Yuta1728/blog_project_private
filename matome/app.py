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
#   [2] create_app() : アプリ生成ファクトリ関数
#        (2-1) ProxyFix の適用（リバースプロキシ対応）
#        (2-2) SECRET_KEY の設定
#        (2-3) セッション Cookie の属性設定
#        (2-4) アップロードサイズ制限
#        (2-5) データベース接続 URL の設定（PostgreSQL / SQLite 両対応）
#        (2-6) 拡張機能の初期化（db / migrate / login_manager）
#        (2-7) CSRF 保護の適用
#        (2-8) Flask-Login の詳細設定（unauthorized_handler / user_loader）
#        (2-9) セキュリティヘッダーの付与
#        (2-10) カスタムエラーハンドラー（413）
#        (2-11) Blueprint の登録
#   [3] 直接実行時のエントリポイント（python app.py）
#
# 【処理フロー図】
#
#   python app.py 実行
#        │
#        ▼
#   create_app() ──► Flask インスタンス生成
#        │              │
#        │              ├─ (2-1)〜(2-5) 各種設定（プロキシ・鍵・Cookie・DB）
#        │              ├─ (2-6)〜(2-7) 拡張機能を app に紐付け
#        │              ├─ (2-8)〜(2-10) 認証まわり・ヘッダー・エラー処理
#        │              └─ (2-11) Blueprint 登録（auth / blog / admin）
#        ▼
#   app.run() ──► リクエスト待ち受け開始
#
# ======================================================================


# ======================================================================
# [1] import / Blueprint の読み込み
# ======================================================================

import os
from flask import Flask, flash, redirect, url_for, abort
from flask_wtf.csrf import CSRFProtect  # 全フォームへの CSRF トークン強制適用
from werkzeug.middleware.proxy_fix import ProxyFix  # リバースプロキシ配下での HTTPS 判定補正
from extensions import db, login_manager, migrate
from models import User
import config

# Blueprint: 機能ごとにルートをまとめたモジュール（views/ 配下で定義）
from views.auth  import auth_bp   # ログイン・ログアウト関連
from views.blog  import blog_bp   # 一般公開ページ（一覧・詳細・ジャンル）
from views.admin import admin_bp  # 管理者専用ページ（投稿・編集・削除・マイページ）


# ======================================================================
# [2] create_app() : アプリ生成ファクトリ関数
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
    # STEP 2. 【セキュリティ改善①】ProxyFix の適用（リバースプロキシ対応）
    # ------------------------------------------------------------------
    # Render / Heroku / PythonAnywhere などでは、HTTPS はリバースプロキシで
    # 終端され、Flask アプリ自体には HTTP で届く。そのままだと
    # request.is_secure が本番でも False と判定されてしまうため、
    # ProxyFix で X-Forwarded-Proto / X-Forwarded-Host を信頼して補正する。
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ------------------------------------------------------------------
    # STEP 3. SECRET_KEY の設定（セッション・CSRF トークンの署名に使用）
    # ------------------------------------------------------------------
    # 本番環境判定:
    #   - DATABASE_URL が設定されている（PaaS の PostgreSQL 等）か
    #   - FLASK_ENV=production が設定されている
    # のいずれかであれば本番とみなす。
    #
    # 【PythonAnywhere での注意】
    #   SQLite 運用（USE_SQLITE=1）では DATABASE_URL を設定しないため、
    #   必ず環境変数に FLASK_ENV=production を設定して本番扱いにすること。
    #   これにより SECRET_KEY の必須化・Secure Cookie が有効になる。
    is_production = os.getenv("DATABASE_URL") is not None or os.getenv("FLASK_ENV") == "production"
    secret_key    = os.getenv("SECRET_KEY")

    if not secret_key:
        if is_production:
            raise ValueError("【重大なエラー】本番環境の環境変数 'SECRET_KEY' が設定されていません。")
        else:
            secret_key = "dev-secret-key-for-local-use"

    app.config['SECRET_KEY'] = secret_key

    # ------------------------------------------------------------------
    # STEP 4. 【セキュリティ修正】セッション Cookie の属性を明示的に設定
    # ------------------------------------------------------------------
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE']   = is_production

    # ------------------------------------------------------------------
    # STEP 5. ファイルアップロードサイズ制限（30MB）
    # ------------------------------------------------------------------
    app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB

    # ------------------------------------------------------------------
    # STEP 6. データベース接続 URL の設定（PostgreSQL / SQLite 両対応）
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

    elif use_sqlite:
        # (2) SQLite（PythonAnywhere など）
        basedir      = os.path.abspath(os.path.dirname(__file__))
        instance_dir = os.path.join(basedir, 'instance')
        os.makedirs(instance_dir, exist_ok=True)   # instance/ がなければ作成
        sqlite_path  = os.path.join(instance_dir, 'blog.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_path}"

    else:
        # (3) ローカル開発用フォールバック（docker-compose の PostgreSQL）
        local_db_url = (
            f"postgresql+psycopg://{config.postgre_user}:{config.postgre_password}"
            f"@localhost:15432/{config.postgre_DB}"
        )
        app.config['SQLALCHEMY_DATABASE_URI'] = local_db_url

    # モデル変更のたびにイベントを発行する機能（使わないのでオフにしてメモリ節約）
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ------------------------------------------------------------------
    # STEP 7. 拡張機能の初期化（extensions.py で作ったインスタンスを app に紐付け）
    # ------------------------------------------------------------------
    db.init_app(app)             # SQLAlchemy を app に接続
    migrate.init_app(app, db)    # Alembic マイグレーションを app + db に接続
    login_manager.init_app(app)  # Flask-Login を app に接続

    # ------------------------------------------------------------------
    # STEP 8. CSRF 保護の適用
    # ------------------------------------------------------------------
    csrf = CSRFProtect()
    csrf.init_app(app)

    # ------------------------------------------------------------------
    # STEP 9. Flask-Login の詳細設定
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
    # STEP 10. 【セキュリティ修正】セキュリティヘッダーの付与
    # ------------------------------------------------------------------
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    # ------------------------------------------------------------------
    # STEP 11. カスタムエラーハンドラー: 413 Request Entity Too Large
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def request_entity_too_large(error):
        flash("アップロードされたファイルの合計サイズが30MBを超えています。", "danger")
        return redirect(url_for('admin.mypage'))

    # ------------------------------------------------------------------
    # STEP 12. Blueprint の登録
    # ------------------------------------------------------------------
    app.register_blueprint(auth_bp)   # /login, /logout 系
    app.register_blueprint(blog_bp)   # /, /about, /howto, /genre, /<id>/detail 系
    app.register_blueprint(admin_bp)  # /create, /<id>/update, /<id>/delete, /mypage 系

    return app


# ======================================================================
# [3] 直接実行時のエントリポイント（python app.py で起動）
# ======================================================================
#
# 【重要】PythonAnywhere では app.run() は使われない。
#   PythonAnywhere は WSGI ファイルから create_app() を呼び出して
#   application 変数として公開する方式のため、この __main__ ブロックは
#   ローカル開発でのみ実行される（サーバー上では import されるだけ）。

if __name__ == '__main__':
    app = create_app()

    is_production = (
        os.getenv("DATABASE_URL") is not None
        or os.getenv("FLASK_ENV") == "production"
    )

    debug_mode = (
        not is_production
        and os.getenv("FLASK_DEBUG", "").lower() in ("1", "true")
    )

    app.run(debug=debug_mode)