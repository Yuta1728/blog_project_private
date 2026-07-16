"""Add indexes to Post (created_at / genre / is_published / user_id + composite)

【背景】
Post には created_at・genre・is_published・user_id にインデックスが無かったため、
以下のクエリがいずれも全表スキャン（+ ソート）になっていた。

  - トップ一覧      : WHERE is_published = True ORDER BY created_at DESC
  - ジャンル絞り込み: WHERE genre = ?
  - 公開状態フィルタ: WHERE is_published = True（統計カウント等）
  - マイページ      : WHERE user_id = ? ORDER BY created_at DESC
  - 詳細/権限チェック: WHERE user_id = ?

記事数が増えると一覧・検索・詳細ページが目に見えて遅くなるため、
models.py に index=True を付与したうえで、DB 側にもインデックスを追加する。

【追加するインデックス】
  単体:
    ix_post_created_at    (created_at)
    ix_post_genre         (genre)
    ix_post_is_published  (is_published)
    ix_post_user_id       (user_id)
  複合:
    ix_post_is_published_created_at  (is_published, created_at)
      → 「公開記事を新しい順に先頭 N 件」を取るトップの主経路を
        インデックス走査だけで処理できるようにする。
        昇順で作成するが、PostgreSQL / SQLite とも逆順走査が可能なため
        ORDER BY created_at DESC でもそのまま利用できる。

【冪等性・互換性メモ】
  batch_alter_table を使うことで SQLite でも安全に動作する
  （SQLite は ALTER でのインデックス追加に制約があるため）。
  PostgreSQL では通常の CREATE INDEX として発行される。

Revision ID: add_post_indexes
Revises: add_thumbnail_img
Create Date: 2026-07-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_post_indexes'
down_revision = 'add_thumbnail_img'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.create_index('ix_post_created_at',   ['created_at'],   unique=False)
        batch_op.create_index('ix_post_genre',        ['genre'],        unique=False)
        batch_op.create_index('ix_post_is_published', ['is_published'], unique=False)
        batch_op.create_index('ix_post_user_id',      ['user_id'],      unique=False)
        batch_op.create_index(
            'ix_post_is_published_created_at',
            ['is_published', 'created_at'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_index('ix_post_is_published_created_at')
        batch_op.drop_index('ix_post_user_id')
        batch_op.drop_index('ix_post_is_published')
        batch_op.drop_index('ix_post_genre')
        batch_op.drop_index('ix_post_created_at')