"""Make updated_at nullable

Revision ID: make_updated_at_nullable
Revises: add_img_captions
Create Date: 2026-06-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'make_updated_at_nullable'
down_revision = 'add_img_captions'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        # nullable=True に変更する
        # existing_type を明示することで Alembic が型を再定義せずに属性だけ変更できる
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            nullable=True,
        )

    # 既存レコードのうち updated_at == created_at のものは
    # 「一度も編集されていない新規投稿」とみなして NULL に更新する。
    # これにより移行後も detail.html で更新日時が誤表示されなくなる。
    op.execute("""
        UPDATE post
        SET updated_at = NULL
        WHERE updated_at = created_at
    """)


def downgrade():
    # NULL を created_at で埋め戻してから NOT NULL 制約を復元する
    op.execute("""
        UPDATE post
        SET updated_at = created_at
        WHERE updated_at IS NULL
    """)

    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            nullable=False,
        )