"""Add thumbnail_img to Post

【背景】
これまでサムネイルは「本文画像（img_name）の先頭 1 枚」を流用していたが、
本文に載せたい画像とサムネイルにしたい画像は必ずしも一致しないため、
サムネイル専用画像を格納する thumbnail_img カラムを新設する。

サムネイル表示の優先順位:
  1. thumbnail_img（アップロードされた専用サムネイル）
  2. default_thumb（プリセットから選択したデフォルトサムネイル）
  3. system-default.jpg（システム共通のデフォルト）

Revision ID: add_thumbnail_img
Revises: change_img_name_to_text
Create Date: 2026-07-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_thumbnail_img'
down_revision = 'change_img_name_to_text'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('thumbnail_img', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('thumbnail_img')