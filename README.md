# MITO Blog

Flask 製の個人ブログアプリケーションです。Markdown での記事投稿、画像・地図・YouTube 動画の埋め込み、ハッシュタグ／ジャンルによる分類、ダークモードなどを備えた、単一管理者運用を前提としたブログシステムです。

Application Factory パターン・Blueprint による機能分割・多層防御のセキュリティ設計を採用しています。

---

## 主な機能

### 閲覧者向け（誰でも利用可）

- **記事一覧**：サムネイル付きカード表示、ページ番号方式のページ送り（1ページ4件）
- **検索・絞り込み**：キーワード検索（タイトル・タグ）、ジャンル絞り込み、ハッシュタグ絞り込みの組み合わせ
- **記事詳細**：Markdown をレンダリングした本文、目次（TOC）の自動生成、関連記事の表示（最大4件）
- **各種埋め込み**：本文中への画像（キャプション付き）、Google マップ、YouTube 動画（サムネイル→タップ再生のファサード方式）の埋め込み
- **統計情報**：トップページに総投稿数・ハッシュタグ数・最終更新日を表示
- **ダークモード**：ヘッダーのボタンで切り替え。選択は `localStorage` に保存され、初回描画前に適用されるためチラつきなし
- **静的ページ**：自己紹介（`/about`）・使い方（`/howto`）・ジャンル一覧（`/genre`）

### 管理者向け（ログイン必須）

- **記事の投稿・編集・削除**
- **リッチな編集ツールバー**：H2/H3 見出し・太字・目次・箇条書き・地図・YouTube の挿入ボタン、画像挿入ボタン、スマホ向けのキーボード追従ツールバー
- **画像管理**：複数枚アップロード、1枚ずつ追加、個別削除、キャプション編集、プレビュー
- **デフォルトサムネイル**：画像未アップロード時に選択できる12種のプリセットサムネイル
- **公開設定**：記事ごとに公開／非公開を切り替え（非公開記事は管理者のみ閲覧可能）
- **マイページ**：投稿一覧、使用ジャンル一覧、ニックネーム変更

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム保護 | Flask-WTF（CSRF） |
| Markdown 変換 | Markdown（`toc` / `nl2br` 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |
| データベース | PostgreSQL（本番・ローカル）／ SQLite（PythonAnywhere 無料枠） |
| フロントエンド | 素の HTML / CSS / JavaScript（テンプレートは Jinja2） |

---

## ディレクトリ構成

```
.
├── app.py                  # エントリーポイント（create_app ファクトリ）
├── config.py               # 環境変数の読み込み・提供
├── constants.py            # デフォルトジャンル一覧などの定数
├── extensions.py           # 拡張機能インスタンス（db / login_manager / migrate）
├── models.py               # ORM モデル（Post / User / Hashtag / 中間テーブル）
├── init_db.py              # SQLite 向け DB 初期化スクリプト
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # ページ別・機能別 CSS（Coastal Dawn テーマ）
│   └── img/                # 投稿画像・サムネイル
├── migrations/             # Alembic マイグレーション
├── docker-compose.yml      # ローカル開発用 PostgreSQL
├── requirements.txt        # 依存パッケージ（PostgreSQL ドライバ含む）
├── requirements-pythonanywhere.txt  # SQLite 運用向け依存（psycopg 除外）
└── deploy_pythonanywhere.md          # PythonAnywhere デプロイ手順書
```

---

## アーキテクチャの要点

### Application Factory パターン

`app.py` の `create_app()` でアプリを組み立てます。拡張機能のインスタンス（`db` など）は `extensions.py` に置くことで、`app.py` と `models.py` の間の循環インポートを回避しています。

### Blueprint による機能分割

ルートは役割ごとに3つの Blueprint に分割されています。

- `auth_bp`：認証（`/<秘密パス>`, `/logout`）
- `blog_bp`：一般公開ページ（`/`, `/about`, `/howto`, `/genre`, `/<id>/detail`）
- `admin_bp`：管理者専用（`/create`, `/<id>/update`, `/<id>/delete`, `/mypage`）

### データモデル

```
User (管理者) ──1対多──▶ Post (記事) ──多対多──▶ Hashtag (タグ)
                                    (post_hashtags 中間テーブル経由)
```

`Post.hashtags` は `lazy='selectin'` を指定し、一覧表示時の N+1 問題を防いでいます。`Post.updated_at` は `nullable=True` とし、「未更新」を `NULL` で表現することで更新日時の誤表示を防いでいます。

---

## セキュリティ設計

このアプリは単一管理者運用を前提に、複数の防御層を重ねています。

- **秘密のログイン URL**：ログインパスを環境変数 `ADMIN_LOGIN_PATH` で隠蔽
- **ゲートキー方式**：合言葉（`ADMIN_GATE_KEY`）付き URL または Cookie を持たない訪問者にはログインページを `404` で隠す。ゲートキー未設定時は「常に 404」とするフェイルクローズ設計
- **ブルートフォース対策**：連続5回失敗でセッションを5分間ロックアウト
- **パスワードハッシュ**：`werkzeug` でハッシュ化し、平文比較は行わない
- **CSRF 保護**：全フォームに CSRF トークンを強制
- **画像アップロード検証**：拡張子チェック（第1層）＋ MIME タイプ判定（第2層）＋ UUID ファイル名（第3層）＋ 30MB 容量制限（第4層）
- **XSS 対策**：画像キャプション・地図ラベル・YouTube エラー表示など、HTML 直組み立て箇所で `markupsafe.escape()` を適用。ハッシュタグプレビューは `textContent` で構築
- **Open Redirect 対策**：削除後のリダイレクトで同一オリジンを検証
- **セキュリティヘッダー**：`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` を付与
- **リバースプロキシ対応**：`ProxyFix` により本番の HTTPS 判定を補正し、Secure Cookie を正しく有効化
- **未認証アクセスの隠蔽**：`@login_required` なページへの未ログインアクセスは `404` を返す

### データ整合性

画像ファイルと DB の不整合を防ぐため、次の順序を厳守しています。

1. 画像を保存（`_save_images()` は全成功か全掃除のアトミック動作）
2. DB 変更を `commit`
3. `commit` 成功後に初めて旧ファイルを物理削除

`commit` が失敗した場合は `rollback` し、今回保存した新ファイルを掃除します。万一物理削除に失敗しても「孤立ファイルが残るだけ」で済む安全側の設計です。

---

## セットアップ（ローカル開発）

### 前提

- Python 3.10
- Docker / Docker Compose（ローカルの PostgreSQL 用）

### 手順

1. リポジトリを取得し、仮想環境を作成します。

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. プロジェクト直下に `.env` を作成します（値は自分の環境に合わせてください）。

   ```env
   # データベース（ローカル PostgreSQL）
   POSTGRES_USER=blog_user
   POSTGRES_PASSWORD=blog_password
   POSTGRES_DB=blog_db

   # 管理者アカウント
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your-password          # 平文・ハッシュ済みどちらでも可
   ADMIN_LOGIN_PATH=secret-login-xxxxxxxx
   ADMIN_GATE_KEY=長いランダム文字列

   # セッション・CSRF 署名用（本番では必須）
   SECRET_KEY=別の長いランダム文字列
   ```

   ランダム文字列は次のコマンドで生成できます（`SECRET_KEY` と `ADMIN_GATE_KEY` には別々の値を使用）。

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. PostgreSQL を起動します。

   ```bash
   docker compose up -d
   ```

4. マイグレーションを適用します。

   ```bash
   flask db upgrade
   ```

   > 管理者ユーザーが未作成の場合は `python init_db.py` でテーブル作成と管理者ユーザー作成をまとめて実行できます。

5. アプリを起動します。

   ```bash
   python app.py
   ```

   デバッグモードで起動するには `FLASK_DEBUG=1` を設定します（本番判定時は無効）。

---

## デプロイ（PythonAnywhere 無料枠）

SQLite を使った PythonAnywhere へのデプロイ手順は、リポジトリ内の [`deploy_pythonanywhere.md`](deploy_pythonanywhere.md) に詳細をまとめています。要点は次のとおりです。

- 依存は `requirements-pythonanywhere.txt`（PostgreSQL ドライバを除外）を使用
- 環境変数に `USE_SQLITE=1` と `FLASK_ENV=production` を設定
- DB の初期化は `python init_db.py`（`db.create_all()` ＋ 管理者ユーザー作成）
- WSGI ファイルから `create_app()` を呼び出して `application` として公開
- 更新の反映は「PC で修正 → GitHub に push → サーバーで `git pull` → Web タブで Reload」

### DB 接続の優先順位

`app.py` は次の順で接続先を決定します。

1. `DATABASE_URL`（設定されていれば最優先）
2. `USE_SQLITE=1`（`instance/blog.db` を SQLite として使用）
3. どちらもなければローカルの PostgreSQL（`docker-compose`）

---

## 本文の書き方（Markdown 記法と独自タグ）

記事本文は Markdown で記述でき、加えて以下の独自タグが使えます（編集画面のツールバーから挿入できます）。

| 記法 | 効果 |
|------|------|
| `## 見出し` / `### 見出し` | H2 / H3 見出し |
| `**太字**` | 太字 |
| `[toc]` | 目次をその位置に展開（未使用時は記事冒頭に自動表示） |
| `[imgN]` | N 番目のアップロード画像を挿入（キャプションがあれば `<figure>` 化） |
| `[map:場所名]` | Google マップの埋め込み |
| `[youtube:URL]` | YouTube 動画の埋め込み（サムネイル→タップ再生） |

連続した空行は2行目以降が `<br>` に展開され、意図的な行間の表現が可能です。

---

## ライセンス

学習・個人利用を目的としたプロジェクトです。