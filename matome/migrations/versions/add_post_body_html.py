"""Add body_html / toc_html cache columns to Post

【背景】
detail() は記事本文（Markdown + 独自タグ）をアクセスのたびに
markdown.convert() で HTML へ変換し、さらに [imgN]/[map:]/[youtube:] の
置換を毎回行っていた。本文は投稿・編集時にしか変化しないため、
閲覧のたびに同じ変換を繰り返すのは無駄が大きい（improvement.md 項目 5）。

【この変更でやること】
レンダリング済み HTML を保存するキャッシュ列を Post に追加する。
  body_html : Markdown 変換 + 独自タグ置換まで済ませた本文 HTML
  toc_html  : 記事冒頭に表示する目次 HTML（[toc] マーカー使用時は NULL）

投稿・編集時に rendering.render_post_body() で生成して保存し、
detail() は body_html をそのまま出力する。
既存記事（body_html が NULL）は detail() 側でその場生成し、
ベストエフォートで保存（遅延バックフィル）するため、
両列とも nullable=True で追加する。

Revision ID: add_post_body_html
Revises: add_post_indexes
Create Date: 2026-07-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_post_body_html'
down_revision = 'add_post_indexes'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('body_html', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('toc_html',  sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('toc_html')
        batch_op.drop_column('body_html')