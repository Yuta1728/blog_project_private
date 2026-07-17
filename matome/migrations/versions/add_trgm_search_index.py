"""Add pg_trgm GIN indexes for keyword search (PostgreSQL only)

【背景】(improvement.md 項目 7)
index() のキーワード検索は
    Post.title.ilike('%word%')  /  Hashtag.name.ilike('%word%')
のように「先頭 %」を伴う部分一致で行っている。先頭ワイルドカードの
LIKE/ILIKE は通常の B-tree インデックスが効かず全表スキャンになるため、
記事数が増えると検索が遅くなる。

【この変更でやること（当面の index 化）】
PostgreSQL の pg_trgm 拡張を有効化し、部分一致検索の対象カラム
（post.title / hashtag.name）に GIN トリグラム索引を張る。
トリグラム索引は「先頭 %」を含む ILIKE '%word%' でも索引走査が効くため、
クエリ（views/blog.py）を一切変えずに部分一致検索を高速化できる。

  ix_post_title_trgm    : post.title    に対する gin_trgm_ops 索引
  ix_hashtag_name_trgm  : hashtag.name  に対する gin_trgm_ops 索引

なお、tsvector によるスコア付き全文検索は将来の拡張課題として残す。
まずはトリグラム索引で「index 化と併用」する段階に留める。

【方言（DB 種別）による分岐 — 重要】
このアプリは PostgreSQL（本番・ローカル）と SQLite（無料ホスティング）の
両方で動く。pg_trgm は PostgreSQL 専用の拡張のため、SQLite では
拡張も gin_trgm_ops 索引も作れない。そこで upgrade/downgrade とも
接続先の方言を判定し、PostgreSQL 以外では何もしない（no-op）ようにする。
SQLite は小規模利用を想定しており、全表スキャンでも実害は小さい。

【ORM メタデータに載せない理由】
この索引は gin_trgm_ops という拡張依存の演算子クラスを使うため、
models.py の __table_args__ には載せていない
（載せると SQLite 側の db.create_all() が失敗する）。
そのぶん、将来 `flask db migrate` の autogenerate が
「メタデータに無い索引」として DROP を提案しないよう、
migrations/env.py の include_object で名前末尾 '_trgm' の索引を
autogenerate の対象外にしている。

Revision ID: add_trgm_search_index
Revises: add_post_body_html
Create Date: 2026-07-18 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_trgm_search_index'
down_revision = 'add_post_body_html'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # PostgreSQL 以外（SQLite 等）では pg_trgm を使えないためスキップする
    if bind.dialect.name != 'postgresql':
        return

    # トリグラム拡張を有効化（ILIKE '%word%' を索引で高速化するのに必要）
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # 部分一致検索の対象カラムに GIN トリグラム索引を張る。
    # IF NOT EXISTS を付けて、再実行やスタンプ済み環境でも安全にする。
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_post_title_trgm '
        'ON post USING gin (title gin_trgm_ops)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_hashtag_name_trgm '
        'ON hashtag USING gin (name gin_trgm_ops)'
    )


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name != 'postgresql':
        return

    op.execute('DROP INDEX IF EXISTS ix_hashtag_name_trgm')
    op.execute('DROP INDEX IF EXISTS ix_post_title_trgm')

    # pg_trgm 拡張は他の機能から使われている可能性があるため、
    # ここでは DROP EXTENSION は行わない（索引の削除だけに留める）。