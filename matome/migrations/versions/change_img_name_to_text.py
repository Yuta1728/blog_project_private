"""Change img_name from String(100) to Text

【背景】
UUID 化した画像ファイル名は 1 件あたり約 40 文字あるため、
3 枚以上アップロードするとカンマ区切り文字列が 100 文字を超え、
PostgreSQL で "value too long for type character varying(100)" が発生していた。
可変長の Text 型に変更して桁あふれを解消する。

Revision ID: change_img_name_to_text
Revises: make_updated_at_nullable
Create Date: 2026-07-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'change_img_name_to_text'
down_revision = 'make_updated_at_nullable'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column(
            'img_name',
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    # 注意: 100 文字を超えるデータが存在する場合、
    # ダウングレードは失敗する（またはデータの切り捨てが必要になる）。
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column(
            'img_name',
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )