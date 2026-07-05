# app.py
#
# 【役割】
# Flask アプリケーションを生成・設定するエントリーポイント。
# create_app() 関数でアプリを組み立てる「Application Factory パターン」を採用。
#
# Application Factory パターンのメリット:
#   - テスト時に設定を変えた別アプリを簡単に作れる
#   - extensions.py と組み合わせることで循環インポートを避けられる

import os
from flask import Flask, flash, redirect, url_for, abort
from flask_wtf.csrf import CSRFProtect  # 全フォームへの CSRF トークン強制適用
from werkzeug.middleware.proxy_fix import ProxyFix  # リバースプロキシ配下での HTTPS 判定補正
from extensions import db, login_manager, migrate
from models import User
import config

# Blueprint: 機能ごとにルートをまとめたモジュール（別ファイルで定義）
from views.auth  import auth_bp   # ログイン・ログアウト関連
from views.blog  import blog_bp   # 一般公開ページ（一覧・詳細・ジャンル）
from views.admin import admin_bp  # 管理者専用ページ（投稿・編集・削除・マイページ）


def create_app():
    """
    Flask アプリインスタンスを生成して返すファクトリ関数。
    直接 app = Flask(__name__) とグローバルに書かず、
    関数の中で作ることで設定の柔軟性と循環インポート回避を実現する。
    """
    app = Flask(__name__)

    # ===================================================================
    # 【セキュリティ改善①】ProxyFix の適用（リバースプロキシ対応）
    # ===================================================================
    # Render / Heroku などの PaaS では、HTTPS はリバースプロキシ
    # （ロードバランサー）で終端され、Flask アプリ自体には HTTP で届く。
    # そのままだと request.is_secure が本番でも False と判定されてしまい、
    # views/auth.py のゲート Cookie に Secure 属性が付かなくなる。
    #
    # ProxyFix ミドルウェアを適用すると、プロキシが付与する
    # X-Forwarded-Proto / X-Forwarded-Host ヘッダを信頼して
    # request.is_secure や url_for(_external=True) が
    # 「実際のクライアントから見た接続情報（https）」を正しく返すようになる。
    #
    # 引数の意味:
    #   x_proto=1 → 直前 1 段のプロキシの X-Forwarded-Proto を信頼する
    #   x_host=1  → 直前 1 段のプロキシの X-Forwarded-Host  を信頼する
    # （PaaS は通常プロキシ 1 段構成のため 1 を指定。多段構成なら段数に合わせる）
    #
    # 注意: ローカル開発（プロキシなし・直接アクセス）では
    #       X-Forwarded-* ヘッダ自体が存在しないため挙動は変わらない。
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ===================================================================
    # SECRET_KEY の設定（セッション・CSRF トークンの署名に使用）
    # ===================================================================
    # 本番環境判定: DATABASE_URL または FLASK_ENV=production が設定されていれば本番とみなす
    is_production = os.getenv("DATABASE_URL") is not None or os.getenv("FLASK_ENV") == "production"
    secret_key    = os.getenv("SECRET_KEY")

    if not secret_key:
        if is_production:
            # 本番環境で SECRET_KEY が未設定のままだと
            # セッション改ざんや CSRF 攻撃のリスクがあるため起動自体を拒否する
            raise ValueError("【重大なエラー】本番環境の環境変数 'SECRET_KEY' が設定されていません。")
        else:
            # 開発環境では固定値をフォールバックとして使用（利便性優先）
            secret_key = "dev-secret-key-for-local-use"

    app.config['SECRET_KEY'] = secret_key

    # ===================================================================
    # ファイルアップロードサイズ制限
    # ===================================================================
    # 30MB を超えるリクエストは Werkzeug が 413 エラーを返す。
    # 悪意あるユーザーによる大容量ファイル送信（DoS 攻撃）への対策。
    app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB

    # ===================================================================
    # データベース接続 URL の設定
    # ===================================================================
    # ローカル開発用 URL（docker-compose で 55432 番ポートにマッピングした PostgreSQL）
    local_db_url = (
        f"postgresql+psycopg://{config.postgre_user}:{config.postgre_password}"
        f"@localhost:55432/{config.postgre_DB}"
    )
    # 本番環境では DATABASE_URL 環境変数を使用（Heroku / Render など PaaS が自動設定する）
    # 未設定の場合はローカル用 URL にフォールバック
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", local_db_url)

    # モデル変更のたびにイベントを発行する機能（使わないのでオフにしてメモリ節約）
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ===================================================================
    # 拡張機能の初期化（extensions.py で作ったインスタンスを app に紐付け）
    # ===================================================================
    db.init_app(app)           # SQLAlchemy を app に接続
    migrate.init_app(app, db)  # Alembic マイグレーションを app + db に接続
    login_manager.init_app(app)  # Flask-Login を app に接続

    # ===================================================================
    # CSRF 保護の適用
    # ===================================================================
    # CSRFProtect を init_app すると、POST/PUT/DELETE などの変更系リクエスト全てに
    # csrf_token フィールドの検証が強制される。
    # テンプレート側では {{ csrf_token() }} で hidden フィールドとして埋め込む。
    csrf = CSRFProtect()
    csrf.init_app(app)

    # ===================================================================
    # Flask-Login の詳細設定
    # ===================================================================
    # -------------------------------------------------------------------
    # 【セキュリティ修正】login_view を設定しない（= 秘密 URL の隠蔽）
    #
    # 従来は login_view = 'auth.secret_login' としていたため、
    # 未ログインの一般ユーザーが /create や /mypage のような
    # 推測しやすい URL にアクセスすると、Flask-Login が親切に
    # 「秘密のログインページ」へリダイレクトしてしまい、
    # ADMIN_LOGIN_PATH で隠したはずの URL が漏洩する経路になっていた。
    #
    # 対策:
    #   - login_view を None のままにする
    #   - unauthorized_handler で 404 を返し、
    #     管理者専用ページの「存在自体」を隠す
    #     （一般ユーザーには「そんなページは無い」ように見える）
    # -------------------------------------------------------------------
    login_manager.login_view = None

    @login_manager.unauthorized_handler
    def unauthorized():
        # 未ログイン状態で @login_required なページへアクセスされた場合、
        # ログインページへ誘導せず 404 Not Found を返して存在を偽装する。
        abort(404)

    # -------------------------------------------------------------------
    # user_loader コールバック
    # Flask-Login がリクエストのたびにセッションの user_id から
    # User オブジェクトを復元するために呼ぶ関数。
    # これがないと current_user が常に AnonymousUser になってしまう。
    # -------------------------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ===================================================================
    # カスタムエラーハンドラー: 413 Request Entity Too Large
    # ===================================================================
    # MAX_CONTENT_LENGTH を超えるファイルがアップロードされたとき、
    # デフォルトでは 413 エラーページが返るだけだが、
    # このハンドラによりフラッシュメッセージ付きでマイページにリダイレクトする。
    @app.errorhandler(413)
    def request_entity_too_large(error):
        flash("アップロードされたファイルの合計サイズが30MBを超えています。", "danger")
        return redirect(url_for('admin.mypage'))

    # ===================================================================
    # Blueprint の登録
    # ===================================================================
    # 各 Blueprint が持つルート定義をアプリに組み込む。
    # 登録後は Blueprint 内の @xxx_bp.route() が有効になる。
    app.register_blueprint(auth_bp)   # /login, /logout 系
    app.register_blueprint(blog_bp)   # /, /about, /howto, /genre, /<id>/detail 系
    app.register_blueprint(admin_bp)  # /create, /<id>/update, /<id>/delete, /mypage 系

    return app


# ===================================================================
# 直接実行時のエントリポイント（python app.py で起動）
# ===================================================================
# `flask run` コマンドではなく python app.py で直接実行する場合に使われる。
# debug=True にすると:
#   - コード変更時にサーバーが自動リロードされる
#   - エラー発生時にブラウザ上でトレースバックが確認できる
# 本番環境では debug=True にしてはいけない（内部情報が漏洩するリスクあり）
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)


    