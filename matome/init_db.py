# ======================================================================
# init_db.py — データベース初期化スクリプト（SQLite / マイグレーション不要）
# ======================================================================
#
# 【役割】
#   マイグレーション（flask db upgrade）を使わない環境向けに、
#   テーブル作成と管理者ユーザーの登録を一括で行うスクリプト。
#   PythonAnywhere 無料枠のように SQLite を使う場合に利用する。
#
# 【重要】
#   このアプリはログイン時に「管理者ユーザー（ADMIN_USERNAME）」が
#   DB に存在していることを前提にしている。
#   空の DB のままだとログインできないため、テーブル作成と同時に
#   管理者ユーザーも作成する。
#
# 【実行方法】
#   1. 仮想環境を有効化する（PythonAnywhere では workon <venv名>）
#   2. .env に ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_LOGIN_PATH /
#      ADMIN_GATE_KEY / SECRET_KEY / USE_SQLITE / FLASK_ENV を設定しておく
#   3. プロジェクト直下で以下を実行:
#          python init_db.py
#
#   何度実行しても安全（テーブル・ユーザーが既にあればスキップする）。
# ======================================================================

from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db
from models import User
import config

# werkzeug が生成するパスワードハッシュの接頭辞（ハッシュ済みかどうかの判定用）
_HASH_PREFIXES = ('pbkdf2:', 'scrypt:', 'argon2')


def _resolve_password_hash(raw: str) -> str:
    """
    ADMIN_PASSWORD の値を「DB に保存するハッシュ」に変換する。

    - 既にハッシュ済み（pbkdf2:/scrypt:/argon2 で始まる）ならそのまま使う
    - 平文が渡された場合はここでハッシュ化する

    どちらの形式でも受け付けることで、初心者が平文を設定しても
    正しくログインできるようにする（安全側・利便性重視）。
    """
    raw = raw or ''
    if raw.startswith(_HASH_PREFIXES):
        return raw
    return generate_password_hash(raw)


def main():
    app = create_app()
    with app.app_context():
        # --------------------------------------------------------------
        # 1) 全テーブルを作成（既に存在するテーブルはそのまま）
        # --------------------------------------------------------------
        db.create_all()
        print('[OK] テーブルを作成しました。')

        # --------------------------------------------------------------
        # 2) 管理者ユーザーを作成（既に存在すれば作成しない）
        # --------------------------------------------------------------
        if not config.ADMIN_USERNAME:
            raise SystemExit('[ERROR] ADMIN_USERNAME が未設定です。.env を確認してください。')

        existing = User.query.filter_by(username=config.ADMIN_USERNAME).first()
        if existing:
            print(f'[SKIP] 管理者ユーザー "{config.ADMIN_USERNAME}" は既に存在します。')
        else:
            user = User(
                username=config.ADMIN_USERNAME,
                password=_resolve_password_hash(config.ADMIN_PASSWORD),
                nickname=None,
            )
            db.session.add(user)
            db.session.commit()
            print(f'[OK] 管理者ユーザー "{config.ADMIN_USERNAME}" を作成しました。')

        print('\n初期化が完了しました。Web タブから Reload してください。')


if __name__ == '__main__':
    main()