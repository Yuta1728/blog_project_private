# ======================================================================
# services/hashtags.py — ハッシュタグの解析・同期・掃除（ドメインロジック層）
# ======================================================================
#
# 【役割】
#   ハッシュタグに関する処理をまとめたサービスモジュール。
#   従来 views/admin.py に直書きされていたヘルパー群をここへ移した。
#
# 【このファイルの構成（目次）】
#   [1] parse_hashtag_input()      : 入力文字列 → タグ名リスト
#   [2] sync_hashtags()            : Post とタグリストの同期
#   [3] delete_orphaned_hashtags() : 孤立タグの一括削除
#
# 【依存】
#   re は標準ライブラリで軽量なため、トップレベルで import している
#   （画像処理と違い、遅延 import のメリットがない）。
# ======================================================================

import re
from extensions import db
from models import Post, Hashtag


# ======================================================================
# [1] 入力文字列 → タグ名リスト
# ======================================================================
def parse_hashtag_input(raw: str) -> list[str]:
    """
    フォームから受け取ったハッシュタグ入力文字列を
    「# なしのタグ名リスト」に変換する。

    対応する入力形式:
      "#Flask #Python ブログ" → ['Flask', 'Python', 'ブログ']
      "Flask,Python,ブログ"   → ['Flask', 'Python', 'ブログ']
      "Flask　Python"         → ['Flask', 'Python']  （全角スペースも対応）

    @param raw: フォームの hashtag_input フィールドの値
    @return: タグ名文字列のリスト（'#' なし）
    """
    # STEP 1. 前処理
    raw = raw.strip()
    if not raw:
        return []

    # STEP 2. 区切り文字: 半角スペース・全角スペース・カンマ・読点 のいずれか 1 文字以上
    tokens = re.split(r'[\s　,、]+', raw)

    # STEP 3〜4. '#' 除去 + フィルタリング
    names, seen = [], set()
    for token in tokens:
        name = token.lstrip('#').strip()  # 先頭の # を除去
        if name and name not in seen and len(name) <= 50:
            names.append(name)
            seen.add(name)  # 重複チェック用セットに追加

    return names


# ======================================================================
# [2] Post とタグリストの同期
# ======================================================================
def sync_hashtags(post: Post, tag_names: list[str]) -> None:
    """
    post.hashtags リレーションを tag_names リストと同期する。
    「既存タグがあれば再利用、なければ新規作成」を行う。

    @param post: 同期対象の Post オブジェクト
    @param tag_names: 新しいタグ名リスト（'#' なし）
    """
    new_tags = []
    for name in tag_names:
        # 既存タグの検索・再利用
        tag = Hashtag.query.filter_by(name=name).first()
        if not tag:
            # DB に存在しない新タグ → 新規作成
            tag = Hashtag(name=name)
            db.session.add(tag)
        new_tags.append(tag)

    # リレーションを上書き（中間テーブルの更新は SQLAlchemy が自動処理）
    post.hashtags = new_tags


# ======================================================================
# [3] 孤立タグの一括削除
# ======================================================================
def delete_orphaned_hashtags() -> None:
    """
    どの記事にも紐付いていない孤立ハッシュタグを一括削除する。
    記事削除後・記事編集後に、commit 前に呼んでセッションに乗せてから commit する。

    ~Hashtag.posts.any() は中間テーブルを「タグ側から」参照する NOT EXISTS で、
    ix_post_hashtags_hashtag_id が効く経路のひとつ。
    """
    orphaned = Hashtag.query.filter(~Hashtag.posts.any()).all()
    for tag in orphaned:
        db.session.delete(tag)