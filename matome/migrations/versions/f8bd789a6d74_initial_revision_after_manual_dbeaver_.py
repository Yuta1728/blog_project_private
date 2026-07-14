"""initial revision (create base tables: user, post)

【修正の背景】
以前このリビジョンは down_revision=None（＝マイグレーションの起点）でありながら、
中身が is_published を NOT NULL に変更する alter_column だけで、
肝心の user / post テーブルを作成する create_table を持っていなかった。
これは「DBeaver で手動作成したテーブルに対して手当てした」経緯によるもの。

その結果、空のデータベースに対して `flask db upgrade` を実行しても
テーブルが 1 つも作られず、スキーマ構築が実質 init_db.py（db.create_all()）
だけに依存する二重管理状態になっていた。

【この修正でやること】
このリビジョン（＝チェーンの起点）で、当時のスキーマどおりに
user テーブルと post テーブルを create_table する。
以降のリビジョンが積み上がる前提の「初期スキーマ」を再現しているため、

  f8bd789a6d74（このファイル: user / post 作成）
      → 42dc0996903d          （post に default_thumb 追加）
      → add_hashtag_tables    （hashtag / post_hashtags 作成）
      → add_img_captions      （post に img_captions 追加）
      → make_updated_at_nullable（post.updated_at を nullable 化）
      → change_img_name_to_text（post.img_name を Text 化）
      → add_thumbnail_img      （post に thumbnail_img 追加）

という後続チェーンが空 DB からでも順に適用でき、
最終的に models.py と一致するスキーマが構築される。

【重要】
このリビジョンは「起点（down_revision=None）」なので、
当時存在しなかったカラム（default_thumb / img_captions / thumbnail_img）は
ここでは作らない。それらは後続リビジョンが追加する。
img_name もこの時点では String(100)（後続の change_img_name_to_text で Text 化）、
updated_at もこの時点では NOT NULL（後続の make_updated_at_nullable で nullable 化）。

なお、既存の本番 DB は alembic_version が既にこのリビジョン以降に
スタンプ済みのため、この upgrade() が再実行されることはなく無害。

Revision ID: f8bd789a6d74
Revises:
Create Date: 2026-05-27 06:25:27.562683

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8bd789a6d74'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # user テーブル
    # ------------------------------------------------------------------
    op.create_table(
        'user',
        sa.Column('id',       sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=30),  nullable=True),
        sa.Column('password', sa.String(length=200), nullable=True),
        sa.Column('nickname', sa.String(length=60),  nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    # ------------------------------------------------------------------
    # post テーブル（この時点のスキーマ）
    #   - default_thumb / img_captions / thumbnail_img は後続で追加するため無し
    #   - img_name は String(100)（後続で Text 化）
    #   - updated_at は NOT NULL（後続で nullable 化）
    # ------------------------------------------------------------------
    op.create_table(
        'post',
        sa.Column('id',           sa.Integer(), nullable=False),
        sa.Column('title',        sa.Text(),    nullable=False),
        sa.Column('body',         sa.Text(),    nullable=False),
        sa.Column('genre',        sa.String(length=100), nullable=False),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('user_id',      sa.Integer(),  nullable=False),
        sa.Column('img_name',     sa.String(length=100), nullable=True),
        sa.Column('is_published', sa.Boolean(),  nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    # 依存関係（post.user_id → user.id）を考慮し post から先に落とす
    op.drop_table('post')
    op.drop_table('user')
