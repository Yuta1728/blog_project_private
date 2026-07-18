"""Add index on post_hashtags.hashtag_id (tag -> post direction)

【背景】(improvement.md 第2版 項目 A-1)
中間テーブル post_hashtags は (post_id, hashtag_id) の複合主キーしか持って
いなかった。複合インデックスは「先頭カラムから順に」しか使えないため、
post_id を起点にした検索（記事 → タグ）には効くが、hashtag_id を起点にした
検索（タグ → 記事）にはインデックスがまったく効かない。

その結果、以下の経路がすべて中間テーブルの全表スキャンになっていた。

  - views/blog.py index()  ハッシュタグ絞り込み
        query.join(Post.hashtags).filter(Hashtag.name == ...)
  - views/blog.py index()  ジャンル内で使われているタグ一覧
        db.session.query(Hashtag).join(Hashtag.posts)
  - views/blog.py index()  統計のハッシュタグ種類数
        count(distinct Hashtag.id) ... join(Hashtag.posts)
  - views/blog.py _get_related_posts()  STEP 1 / STEP 2
        Post.hashtags.any(Hashtag.name.in_(...))
  - views/admin.py delete_orphaned_hashtags()  孤立タグ判定
        ~Hashtag.posts.any()

これらのコストは「記事数 × タグ数」に比例して増えるため、記事が増えると
タグ絞り込み・関連記事・統計が目に見えて遅くなる。

【この変更でやること】
post_hashtags.hashtag_id に単体インデックスを追加し、
「タグ → 記事」方向の検索でもインデックス走査で済むようにする。

  ix_post_hashtags_hashtag_id  (hashtag_id)

多対多の中間テーブルでは、複合主キーの逆順（hashtag_id, post_id）の
複合インデックスを張るのが定石だが、単体インデックスでも
「hashtag_id で該当行を絞り込む」目的は十分果たせる
（絞り込んだ後は主キー経由で post_id を引く形になる）ため、
ここではシンプルな単体インデックスを採用している。

【batch_alter_table を使わない理由】
このプロジェクトの既存マイグレーションは SQLite 対応のため
batch_alter_table を多用しているが、batch モードは「テーブルを作り直して
差し替える」方式であり、カラム型変更や制約変更のように SQLite が
ALTER で対応できない操作のために使うもの。

一方 CREATE INDEX は SQLite / PostgreSQL のいずれもテーブルを作り直さずに
実行できるため、batch モードは不要（むしろ中間テーブルを再構築すると
外部キーの取り扱いで余計なリスクを負う）。そのため op.create_index を
そのまま使用する。

Revision ID: add_post_hashtags_index
Revises: add_trgm_search_index
Create Date: 2026-07-18 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_post_hashtags_index'
down_revision = 'add_trgm_search_index'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_post_hashtags_hashtag_id',
        'post_hashtags',
        ['hashtag_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_post_hashtags_hashtag_id', table_name='post_hashtags')