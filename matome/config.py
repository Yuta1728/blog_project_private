"""
config.py

【役割】
.env ファイルから環境変数を読み込み、アプリ全体で使いやすい変数名で提供するモジュール。

【なぜ環境変数を使うのか】
パスワードや接続情報などの機密情報をソースコードに直書きすると
Git で管理した際に情報漏洩のリスクがある。
.env ファイルは .gitignore に登録してリポジトリに含めないことで
ソースコードを公開しても機密情報が漏れない設計にしている。
"""

import os
from dotenv import load_dotenv  # python-dotenv: .env ファイルを読み込むライブラリ

# -------------------------------------------------------------------
# load_dotenv()
# プロジェクトルートの .env ファイルを探して、
# 記載された KEY=VALUE を os の環境変数として登録する。
# この行より後の os.getenv() で .env の値が取得できるようになる。
# -------------------------------------------------------------------
load_dotenv()

# -------------------------------------------------------------------
# PostgreSQL 接続情報
# docker-compose.yml の environment セクションと同じキー名で .env に記載する。
#
# app.py でこれらを使って接続 URL を組み立てる：
#   f"postgresql+psycopg://{postgre_user}:{postgre_password}@localhost:55432/{postgre_DB}"
# -------------------------------------------------------------------
postgre_user     = os.getenv("POSTGRES_USER")      # DB ユーザー名
postgre_password = os.getenv("POSTGRES_PASSWORD")  # DB パスワード
postgre_DB       = os.getenv("POSTGRES_DB")        # DB 名

# -------------------------------------------------------------------
# 管理者認証情報
#
# ADMIN_USERNAME : ログインフォームで入力するユーザー名
# ADMIN_PASSWORD : DB に保存するためのハッシュ化済みパスワード
#                  （views/auth.py で check_password_hash() と照合する）
# ADMIN_LOGIN_PATH : ログインページの URL パス
#                    例: "secret-login-abc123" → /secret-login-abc123 でアクセス
#                    推測されにくいランダムな文字列にすることで
#                    ログインページの存在自体を隠蔽するセキュリティ対策
# -------------------------------------------------------------------
ADMIN_USERNAME   = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD")
ADMIN_LOGIN_PATH = os.getenv("ADMIN_LOGIN_PATH")