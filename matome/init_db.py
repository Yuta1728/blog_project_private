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
# 【スキーマ二重管理への対策（このリビジョンでの変更点）】
#   従来このスクリプトは db.create_all() でテーブルを作るだけで、
#   Alembic の管理テーブル（alembic_version）にリビジョンを
#   スタンプしていなかった。そのため create_all() で作成した DB に
#   後から flask db upgrade でマイグレーション運用へ移行しようとすると、
#   Alembic は「まだ 1 つもマイグレーションが適用されていない」とみなし、
#   起点リビジョン（user / post を create_table する f8bd789a6d74）から
#   実行しようとして「テーブルが既に存在する」エラーになり整合が取れなかった。
#   （この懸念は f8bd789a6d74 の docstring 自身も指摘している。）
#
#   対策として、create_all() の直後に Alembic の履歴を head（最新）へ
#   スタンプする。create_all() が構築するスキーマは models.py の現在の状態
#   （＝マイグレーションチェーンの終端 head）と一致するため、
#   「head まで適用済み」とマークするのは正確であり、
#   これにより将来 flask db upgrade を実行しても既適用分は再実行されず、
#   SQLite（create_all 経由）と PostgreSQL（Alembic 経由）の両運用で
#   alembic_version の状態が食い違わなくなる。
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
from flask_migrate import stamp   # Alembic のリビジョンをスタンプする（履歴を head に合わせる）
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
        # 1.5) Alembic の履歴を head（最新）にスタンプする
        # --------------------------------------------------------------
        # create_all() が作るスキーマは models.py の現在の状態と一致し、
        # それはマイグレーションチェーンの終端（head）と同じ。
        # ここで alembic_version に head を書き込んでおくことで、
        # 「create_all で作った DB に後から flask db upgrade を実行すると
        #   起点から再適用されてしまう」という不整合を防ぐ。
        #
        # stamp() は alembic_version テーブルが無ければ作成し、
        # 既にあれば head に更新する（実行のたびに head へ揃うので冪等）。
        # migrations/ ディレクトリが無い等でスタンプに失敗しても、
        # テーブル自体は作成済みで動作には支障がないため、
        # 例外はワークフローを止めず警告として通知するにとどめる。
        try:
            stamp(revision='head')
            print('[OK] マイグレーション履歴を最新（head）にスタンプしました。')
        except Exception as e:
            print(f'[WARN] Alembic 履歴のスタンプをスキップしました: {e}')
            print('       （テーブルは作成済みのため動作に支障はありません。'
                  'マイグレーション運用へ移行する場合は migrations/ の存在を確認してください。）')

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