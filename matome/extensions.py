# extensions.py
#
# 【役割】
# Flask の拡張機能（プラグイン）を「インスタンスだけ先に作っておく」ファイル。
#
# なぜ app.py に直接書かないのか？
#   → app.py で from extensions import db と書けば
#     app.py と models.py の双方から同じ db オブジェクトを参照できる。
#     app.py 内で db = SQLAlchemy(app) と書いてしまうと
#     models.py が app.py を import して循環インポートが発生するため、
#     このファイルで「中立な場所」に置いている。（Application Factory パターン）

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

# -------------------------------------------------------------------
# db: データベース操作の中心オブジェクト
#
# SQLAlchemy の ORM（Object-Relational Mapping）インスタンス。
# models.py で db.Column / db.relationship などを使ってテーブル定義し、
# views/ 内で db.session.add() / db.session.commit() などを使って
# データの読み書きを行う。
# 実際の DB への接続は app.py の db.init_app(app) 時に行われる。
# -------------------------------------------------------------------
db = SQLAlchemy()

# -------------------------------------------------------------------
# login_manager: ログイン状態の管理オブジェクト
#
# Flask-Login が提供するセッション管理の中心。
# - @login_required デコレータで未ログイン時のアクセスを制御
# - current_user でテンプレート・ビューから現在のユーザー情報を取得
# - login_manager.login_view でログインページの URL を指定（app.py で設定）
# - login_manager.user_loader でセッションから User を復元するコールバックを登録
# -------------------------------------------------------------------
login_manager = LoginManager()

# -------------------------------------------------------------------
# migrate: データベーススキーマのバージョン管理オブジェクト
#
# Alembic（マイグレーションツール）を Flask と連携させるラッパー。
# models.py でテーブル定義を変更した後に
#   flask db migrate -m "変更内容"  → 差分を検出して migrations/versions/ にファイル生成
#   flask db upgrade                → 実際の DB に変更を適用
# というワークフローで使用する。
# -------------------------------------------------------------------
migrate = Migrate()