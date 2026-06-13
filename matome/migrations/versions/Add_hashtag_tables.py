"""add hashtag tables

Revision ID: add_hashtag_tables
Revises: 42dc0996903d
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_hashtag_tables'
down_revision = '42dc0996903d'
branch_labels = None
depends_on = None


def upgrade():
    # hashtag テーブルの作成
    op.create_table(
        'hashtag',
        sa.Column('id',   sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # post_hashtags 中間テーブルの作成
    op.create_table(
        'post_hashtags',
        sa.Column('post_id',    sa.Integer(), nullable=False),
        sa.Column('hashtag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'],    ['post.id']),
        sa.ForeignKeyConstraint(['hashtag_id'], ['hashtag.id']),
        sa.PrimaryKeyConstraint('post_id', 'hashtag_id')
    )


def downgrade():
    op.drop_table('post_hashtags')
    op.drop_table('hashtag')