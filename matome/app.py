import os
from flask import Flask, flash, redirect, url_for
from flask_wtf.csrf import CSRFProtect  # CSRF保護用
from extensions import db, login_manager, migrate
from models import User
import config

# Blueprintの登録
from views.auth import auth_bp
from views.blog import blog_bp
from views.admin import admin_bp

def create_app():
    app = Flask(__name__)

    # ---SECRET_KEY の安全性強化 ---
    # 開発用（ローカル）か本番用（DATABASE_URL等の有無）かを簡易判定
    is_production = os.getenv("DATABASE_URL") is not None or os.getenv("FLASK_ENV") == "production"
    secret_key = os.getenv("SECRET_KEY")

    if not secret_key:
        if is_production:
            # 本番環境で未設定なら、セッション切断やセキュリティリスクを防ぐため起動を拒否する
            raise ValueError("【重大なエラー】本番環境の環境変数 'SECRET_KEY' が設定されていません。")
        else:
            # 開発環境であれば、開発のしやすさを優先して固定値をフォールバックにする
            secret_key = "dev-secret-key-for-local-use"
            
    app.config['SECRET_KEY'] = secret_key

    # --- 4層目の防御（ファイルアップロード30MB制限） ---
    app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024

    # PostgreSQL接続用URLの設定
    local_db_url = f"postgresql+psycopg://{config.postgre_user}:{config.postgre_password}@localhost:54321/{config.postgre_DB}"
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", local_db_url)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 拡張機能の初期化
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # --- S-02: CSRF保護をアプリ全体に適用 ---
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # 遷移先URLの設定
    login_manager.login_view = 'auth.secret_login'
    login_manager.login_message = "ログインしてください。"
    login_manager.login_message_category = "info"  # フラッシュの色分け対応用にカテゴリーを追加

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ---  30MB容量オーバー(413エラー)発生時のカスタムハンドラー ---
    @app.errorhandler(413)
    def request_entity_too_large(error):
        # 'danger'(赤色)カテゴリーでフラッシュを送信
        flash("アップロードされたファイルの合計サイズが30MBを超えています。", "danger")
        # 安全にマイページ（またはトップページ）へリダイレクト
        return redirect(url_for('admin.mypage'))

    # Blueprintの登録
    app.register_blueprint(auth_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(admin_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)


    