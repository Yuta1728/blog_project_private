# ======================================================================
# config.py — 環境変数の読み込み・提供
# ======================================================================
#
# 【役割】
#   .env ファイルから環境変数を読み込み、
#   アプリ全体で使いやすい変数名で提供するモジュール。
#
#   【なぜ環境変数を使うのか】
#   パスワードや接続情報などの機密情報をソースコードに直書きすると
#   Git で管理した際に情報漏洩のリスクがある。
#   .env ファイルは .gitignore に登録してリポジトリに含めないことで
#   ソースコードを公開しても機密情報が漏れない設計にしている。
#
# 【このファイルの構成（目次）】
#   [1] .env ファイルの読み込み（load_dotenv）
#   [2] PostgreSQL 接続情報
#   [3] 管理者認証情報
#   [4] ADMIN_LOGIN_PATH 未設定チェック（フェイルクローズ）
#
# 【処理フロー図】
#
#   import config（app.py などから読み込まれた瞬間に実行される）
#        │
#        ▼
#   [1] load_dotenv() ──► .env の KEY=VALUE を OS 環境変数として登録
#        │
#        ▼
#   [2][3] os.getenv() で各値を Python 変数に取り込む
#        │
#        ▼
#   [4] ADMIN_LOGIN_PATH が空なら ValueError で起動を止める
#       （設定漏れをアプリ起動前の最も早い段階で検出）
#
# ======================================================================

import os
from dotenv import load_dotenv  # python-dotenv: .env ファイルを読み込むライブラリ


# ======================================================================
# [1] .env ファイルの読み込み
# ======================================================================
# load_dotenv():
#   プロジェクトルートの .env ファイルを探して、
#   記載された KEY=VALUE を os の環境変数として登録する。
#   この行より後の os.getenv() で .env の値が取得できるようになる。
load_dotenv()


# ======================================================================
# [2] PostgreSQL 接続情報
# ======================================================================
# docker-compose.yml の environment セクションと同じキー名で .env に記載する。
#
# app.py でこれらを使って接続 URL を組み立てる：
#   f"postgresql+psycopg://{postgre_user}:{postgre_password}@localhost:15432/{postgre_DB}"
postgre_user     = os.getenv("POSTGRES_USER")      # DB ユーザー名
postgre_password = os.getenv("POSTGRES_PASSWORD")  # DB パスワード
postgre_DB       = os.getenv("POSTGRES_DB")        # DB 名


# ======================================================================
# [3] 管理者認証情報
# ======================================================================
# ADMIN_USERNAME : ログインフォームで入力するユーザー名
# ADMIN_PASSWORD : DB に保存するためのハッシュ化済みパスワード
#                  （views/auth.py で check_password_hash() と照合する）
# ADMIN_LOGIN_PATH : ログインページの URL パス
#                    例: "secret-login-abc123" → /secret-login-abc123 でアクセス
#                    推測されにくいランダムな文字列にすることで
#                    ログインページの存在自体を隠蔽するセキュリティ対策
ADMIN_USERNAME   = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD")
ADMIN_LOGIN_PATH = os.getenv("ADMIN_LOGIN_PATH")


# ======================================================================
# [4] 【セキュリティ改善②】ADMIN_LOGIN_PATH 未設定チェック（フェイルクローズ）
# ======================================================================
# ADMIN_LOGIN_PATH が未設定のまま起動すると、os.getenv() が None を返し、
# views/auth.py のルート定義 f'/{config.ADMIN_LOGIN_PATH}' が
# 文字どおり「/None」という推測可能なパスになってしまう。
#
# ゲートキー（ADMIN_GATE_KEY）のフェイルクローズにより実害は出ないが、
# 設定漏れに気付かないまま運用を続けるリスクを避けるため、
# ここで明示的にエラーを発生させて起動自体を拒否する。
# （config.py は app.py より先に import されるため、
#   アプリ起動前の最も早い段階で設定漏れを検出できる）
if not ADMIN_LOGIN_PATH:
    raise ValueError("【重大なエラー】環境変数 'ADMIN_LOGIN_PATH' が設定されていません。")