"""環境変数を管理するモジュール"""

import os
from dotenv import load_dotenv

load_dotenv()
postgre_user = os.getenv("POSTGRES_USER")
postgre_password = os.getenv("POSTGRES_PASSWORD")
postgre_DB = os.getenv("POSTGRES_DB")

# .envから管理者情報と秘密のURLを取得
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_LOGIN_PATH = os.getenv("ADMIN_LOGIN_PATH")