# app.py
import os
from flask import Flask
from extensions import db, login_manager, migrate
from models import User
import config

# Blueprintの登録（ここで各機能のルーティングファイルを合体）
from views.auth import auth_bp
from views.blog import blog_bp
from views.admin import admin_bp

def create_app():
    app = Flask(__name__)

    # アプリ・データベース設定の統合と固定化
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", os.urandom(24))

    # PostgreSQL接続用URLの設定
    local_db_url = f"postgresql+psycopg://{config.postgre_user}:{config.postgre_password}@localhost:54321/{config.postgre_DB}"
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", local_db_url)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 拡張機能の初期化
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # 遷移先URLの設定（既存のまま変更なし）
    login_manager.login_view = 'auth.secret_login'
    login_manager.login_message = "ログインしてください。"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(admin_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)


    