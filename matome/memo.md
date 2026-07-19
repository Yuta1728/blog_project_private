# 実装依頼プロンプト：MITO Blog 表示速度・操作性改善

以下のプロンプトを、リポジトリを読み込ませた状態の AI アシスタント（Claude Code 等）に渡してください。

---

## プロンプト本文

あなたは Flask 製個人ブログアプリ「MITO Blog」の改修を担当するエンジニアです。
このリポジトリ（Application Factory パターン / `create_app()` 方式、PythonAnywhere 無料枠 + SQLite 運用、ローカルは PostgreSQL）に対して、**ページの読み込み速度・アクセス速度・体感的な操作性の向上**を目的とした改修を、以下の優先順に段階的に実施してください。

### 前提・全体の制約

- 各改修は `improvement.md` 第2版の項目番号（A-6, A-7, B-4, 16, B-1, B-7, 15, B-3）に対応します。実装前に該当項目の「現状 → 影響 → 対処方法」を必ず読み、意図を踏襲してください。
- 既存コードのコメントスタイル（ファイル冒頭の目次、`STEP N.` 形式、改修理由を背景から書く日本語コメント）を維持し、変更箇所には「なぜ変えたか」を同じ流儀で記述してください。
- **ユーザーから見える挙動・デザインは変えないこと**（速度・転送量・安定性のみ改善する）。
- SQLite（本番）と PostgreSQL（ローカル）の両方で動作すること。DB 方言依存の処理は既存マイグレーション（`add_trgm_search_index.py`）の分岐方法を参考にすること。
- 各ステージ完了ごとに、変更ファイル一覧と動作確認手順を報告してから次に進むこと。
- 対応済み項目（A-1 / A-2 / A-3）には手を付けないこと。

---

### ステージ 1：不要な CSS/JS の配信整理（A-6）

1. `base.html` で全ページ読み込みになっている `mobile-editor.css` を、`create.html` / `update.html` の `{% block extra_css %}` へ移動する。
2. `base.html` に約 250 行インラインで埋め込まれている「スマホ編集ツールバー用 JS」（`#bodyTextarea` / `#md-toolbar` を対象とする IIFE）を `static/js/mobile-editor.js` として切り出し、`create.html` / `update.html` の末尾でのみ `editor.js` と同じ方法で読み込む。
3. テーマ切り替え・ドロワー開閉・スクロール連動ヘッダーの JS も `static/js/base.js` に切り出し、全ページで外部ファイルとして読み込む（キャッシュを効かせるため）。
4. **例外**：`<head>` のダークモード初期化スクリプトは FOUC 防止のためインラインのまま残すこと。
5. 完了条件：記事一覧・詳細ページの HTML に編集ツールバー用 JS が含まれないこと。create/update ページでツールバーのドッキング・カーソル追従が従来どおり動くこと。

### ステージ 2：静的ファイルのキャッシュバスティング（A-7）

1. `app.py` に、ファイルの mtime をクエリパラメータとして付与するテンプレートグローバル `static_url(filename)` を追加する（`improvement.md` A-7 のコード例に準拠）。
2. `app.config['SEND_FILE_MAX_AGE_DEFAULT']` を 1 年に設定する。
3. 全テンプレートの `url_for('static', filename=...)` による CSS / JS / favicon の参照を `static_url(...)` に置き換える。**記事画像（`img/posts/`）とサムネイル画像の参照は対象外**とし、理由（ファイル名が UUID で不変のためバスティング不要）をコメントに残す。
4. 完了条件：CSS を更新すると URL の `?v=` が変わり、ブラウザキャッシュを残したまま即座に反映されること。

### ステージ 3：モバイル向け画像転送量の削減（B-4 簡易版 + 項目 16）

1. `views/admin.py` の `BODY_IMAGE_MAX_EDGE` を 1600 → 1200 に下げる（記事最大表示幅 860px の 2 倍解像度でも 1200px で足りるため）。`srcset` による複数サイズ生成は今回のスコープ外とし、コメントに将来課題として残す。
2. `rendering.py` が生成する本文中の `<img>`（`[imgN]` 置換・figure 内・地図/YouTube サムネイル以外の本文画像）へ `loading="lazy" decoding="async"` を付与する。
3. **注意**：項目 16 は `body_html` キャッシュのため既存記事に反映されない。この時点ではステージ 6（B-3）で解消される旨をコメントに明記するだけでよい。
4. 完了条件：新規投稿の本文画像に lazy 属性が付き、長辺 1200px に縮小されること。

### ステージ 4：DB クエリの仕上げ（B-1 / B-7）

1. **B-1**：`views/blog.py` の `detail()` で `post` 取得を `Post.query.options(db.joinedload(Post.user)).filter(Post.id == id).first()` に変更し、`post.user` 参照による追加クエリを解消する。
2. **B-7**：`app.py` の DB 設定で、SQLite 以外（PostgreSQL）のときのみ `SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}` を設定する。SQLite では設定しない理由をコメントに残す。
3. 完了条件：記事詳細表示で user テーブルへの個別 SELECT が発生しないこと。既存の権限チェック・非公開記事の制御が従来どおり動くこと。

### ステージ 5：関連記事クエリの統合（引き継ぎ項目 15）

1. `views/blog.py` の `_get_related_posts()` を、CASE 式で優先度スコア（同ジャンル×同タグ=4 / 同タグ=3 / 同ジャンル=2 / その他=1）を付け、`ORDER BY score DESC, created_at DESC LIMIT 4` の **1 クエリ**にまとめる。
2. 現在の 4 段階 STEP の優先順位・重複排除・自分自身の除外・公開状態フィルタ（`pub_filter`）の挙動を完全に維持すること。既存の詳細な STEP コメントは、新しい実装の説明に書き換える。
3. `Post.hashtags.any(...)` の EXISTS が `ix_post_hashtags_hashtag_id` を使える形を保つこと。
4. 完了条件：タグあり記事・タグなし記事・ジャンル未分類記事のそれぞれで、従来と同じ関連記事が同じ順で表示されること（変更前後で手動比較する手順を提示すること）。

### ステージ 6：body_html キャッシュのバージョン管理（B-3）

1. `rendering.py` に `RENDER_VERSION` 定数を追加し、rendering.py を変更したら +1 する運用ルールを冒頭コメントに明記する。
2. `Post` に `render_version = db.Column(db.Integer, nullable=True)` を追加し、既存マイグレーションの流儀（背景コメント付き、`batch_alter_table` 使用、リビジョンチェーンの正しい `down_revision`）でマイグレーションを作成する。
3. `create()` / `update()` での保存時、および `detail()` の遅延バックフィル時に `render_version = RENDER_VERSION` を保存する。
4. `detail()` の再生成条件を `post.body_html is None or post.render_version != RENDER_VERSION` に変更する。既存の「失敗しても表示は続ける + `logger.exception` で記録」の方針は維持する。
5. 全記事を一括再生成する CLI コマンド `flask rerender-posts` を追加する（対象件数と成功/失敗件数を出力）。
6. 完了条件：ステージ 3 で追加した `loading="lazy"` が、詳細ページ閲覧時または CLI 実行で既存記事にも反映されること。

---

### 最終報告に含めること

- 変更ファイルの一覧とステージ対応表
- 追加したマイグレーションの適用手順（PythonAnywhere の SQLite 運用では `rm instance/blog.db` → `python init_db.py` になる点を deploy_pythonanywhere.md の運用に沿って明記）
- 各ステージの動作確認チェックリスト
- 今回スコープ外とした関連項目（B-4 の srcset 本対応、A-4 画像 DoS、B-5 サニタイズ 等）とその理由