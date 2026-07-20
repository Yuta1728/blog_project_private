"""Add render_version to Post (レンダラのバージョン記録)

【背景】(improvement.md 第2版 項目 B-3)
記事本文の HTML は投稿・編集時に生成して Post.body_html / toc_html へ
キャッシュしているが、このキャッシュを「捨てる（無効化する）手段」が無かった。
再生成のきっかけが記事の編集しかないため、rendering.py を修正しても
（地図の枠デザイン変更、YouTube 埋め込みの改修、loading="lazy" の追加など）
既存記事は古い HTML のまま表示され続け、全記事を手で開いて
再保存しない限り新しい出力に切り替わらなかった。

【この変更でやること】
「その HTML を生成したときの rendering.py のバージョン」を記録する
render_version 列を Post に追加する。

  render_version : rendering.RENDER_VERSION の値（整数）

views/blog.py の detail() は
    body_html が NULL、または render_version != RENDER_VERSION
のときに本文 HTML を生成し直して保存する。
つまり rendering.py を変更したら RENDER_VERSION を +1 するだけで、
既存記事も次のアクセス時に自動で作り直される。

【nullable=True にしている理由】
この列を追加する前に作られた既存レコードは NULL になる。
NULL は RENDER_VERSION と必ず不一致になるため、そのまま
「再生成の対象」として扱える（移行時に初期値を埋める必要がない）。
逆に既存値を現行バージョンで埋めてしまうと、
出力が変わっているかどうかに関わらず再生成されなくなるため、
あえて NULL のままにしておく。

アクセスを待たずに一括で作り直したい場合は、
app.py に追加した管理コマンドを使う。
    flask rerender-posts
    flask rerender-posts --all

Revision ID: add_post_render_version
Revises: add_post_hashtags_index
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_post_render_version'
down_revision = 'add_post_hashtags_index'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite でも安全に動作するよう batch モードで実行する
    # （このプロジェクトの既存マイグレーションと同じ方針）
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('render_version', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('render_version')