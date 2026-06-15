"""Add img_captions to Post

Revision ID: add_img_captions
Revises: add_hashtag_tables
Create Date: 2026-06-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_img_captions'
down_revision = 'add_hashtag_tables'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('img_captions', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('img_captions')