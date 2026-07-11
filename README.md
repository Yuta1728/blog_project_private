# MIT Blog

Flask 製の個人用ブログアプリケーションです。記事の投稿・編集・削除に加え、ジャンル／ハッシュタグによる分類・絞り込み、画像キャプション、Google マップ・YouTube のインライン埋め込み、ダークモードなどを備えています。管理者は 1 名（単一管理者運用）を想定し、ログインページを秘匿する多層防御を実装しています。

Application Factory パターン（`create_app()`）を採用しており、ローカル開発（PostgreSQL）と PythonAnywhere 無料枠（SQLite）の両方で動作します。

---

## 主な機能

### 閲覧者向け
- **記事一覧・検索**：タイトル／ハッシュタグ名でのキーワード検索、ジャンル絞り込み、ジャンル × タグの複合絞り込み。一覧はページ番号方式のページ送り（1 ページ 4 件）。
- **記事詳細**：Markdown レンダリング、目次（`[toc]`）の自動生成、画像キャプション、`[map:場所名]` による Google マップ埋め込み、`[youtube:URL]` によるファサード形式の動画埋め込み（サムネイルをタップして再生）。
- **関連記事**：同ジャンル × 同タグ → 同タグ → 同ジャンル → 最新、の優先順位で最大 4 件を段階的に表示。
- **ダークモード**：ヘッダーのトグルで切り替え。選択は `localStorage` に保存され、初期表示は OS 設定に追従（チラつき防止済み）。
- **サイト統計**：総投稿数・ハッシュタグ数・最終更新日をトップに表示。
- **静的ページ**：自己紹介（`/about`）、使い方（`/howto`）。

### 管理者向け
- **記事の投稿・編集・削除**（`/create`、`/<id>/update`、`/<id>/delete`）。
- **Markdown ツールバー**：見出し・太字・目次・リスト・地図・YouTube・画像タグの挿入。
- **画像管理**：複数一括アップロード／1 枚ずつ追加、プレビュー、キャプション入力、編集時の個別削除（更新まで確定しない）。デフォルトサムネイルの選択にも対応。
- **公開／非公開**の切り替え（非公開記事は投稿者本人のみ閲覧可）。
- **マイページ**（`/mypage`）：投稿一覧、使用ジャンル一覧、ニックネーム変更。

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.1 |
| ORM / DB | SQLAlchemy 2.0、Flask-SQLAlchemy、Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム / CSRF | Flask-WTF（CSRFProtect） |
| Markdown | Markdown（`toc` / `nl2br` 拡張） |
| ファイル検証 | filetype（MIME 判定） |
| DB（本番想定） | PostgreSQL（ローカル）／ SQLite（PythonAnywhere） |
| フロント | 素の HTML / CSS / JavaScript（Jinja2 テンプレート） |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリ生成のエントリーポイント（create_app）
├── config.py               # .env の読み込み・環境変数の提供
├── constants.py            # デフォルトジャンル一覧
├── extensions.py           # db / login_manager / migrate のインスタンス置き場
├── models.py               # ORM モデル（Post / Hashtag / User / 中間テーブル）
├── init_db.py              # マイグレーション不要の DB 初期化スクリプト（SQLite 向け）
├── docker-compose.yml      # ローカル開発用 PostgreSQL
├── requirements.txt        # 依存パッケージ（PostgreSQL ドライバ含む）
├── requirements-pythonanywhere.txt  # SQLite 運用向け（psycopg 系を除外）
├── wsgi_pythonanywhere.py  # PythonAnywhere の WSGI 設定サンプル
├── deploy_pythonanywhere.md # PythonAnywhere デプロイ・運用仕様書
├── migrations/             # Alembic マイグレーション
├── views/
│   ├── auth.py             # ログイン・ログアウト（ゲートキー方式）
│   ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者専用ページ（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
└── static/
    ├── css/                # ページ別 CSS + dark-mode.css
    └── img/                # posts（投稿画像）/ thbnails（デフォルトサムネイル）
```

---

## セットアップ

### 前提

- Python 3.10（`.python-version` は 3.10.11）
- ローカルで PostgreSQL を使う場合は Docker / Docker Compose

### 1. リポジトリの取得と仮想環境

```bash
git clone <このリポジトリのURL>
cd <プロジェクトルート>

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. 環境変数（`.env`）の作成

プロジェクト直下に `.env` を作成します（`config.py` が自身の絶対パスを基準に読み込むため、どこから起動しても確実に読まれます）。

```dotenv
# --- 管理者認証（必須） ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ログインパスワード（平文でもハッシュ済みでも可）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx   # 推測されにくいランダム文字列（必須）
ADMIN_GATE_KEY=別のランダムな長い文字列    # ログインページを開くための合言葉

# --- セッション／CSRF 署名鍵（本番では必須） ---
SECRET_KEY=ランダムな長い文字列

# --- 本番判定 ---
# FLASK_ENV=production                     # 本番のみ。Secure Cookie / SECRET_KEY 必須化が有効に

# --- DB の選択（下記いずれか） ---
# (A) ローカル PostgreSQL（docker-compose）を使う場合
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=blogpass
POSTGRES_DB=blogdb

# (B) SQLite を使う場合（PythonAnywhere など）
# USE_SQLITE=1
```

ランダム文字列の生成例（`SECRET_KEY` と `ADMIN_GATE_KEY` は別々の値を推奨）:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`SECRET_KEY` / `ADMIN_LOGIN_PATH` が未設定だと、本番環境では起動時にエラーで停止します（設定漏れをフェイルクローズで検出）。

### 3. データベースの用意

**DB 接続先の優先順位**（`app.py` STEP 6）:
1. `DATABASE_URL` が設定されていれば最優先
2. `USE_SQLITE=1` なら `instance/blog.db`（SQLite）
3. どちらもなければローカルの PostgreSQL（`localhost:15432`）

#### (A) ローカル PostgreSQL + マイグレーション

```bash
# PostgreSQL を起動（ホスト 15432 → コンテナ 5432）
docker compose up -d

# テーブル作成
flask --app app db upgrade
```

> 管理者ユーザーは `init_db.py` でも作成できます。マイグレーション運用の場合は、必要に応じて別途 `User` レコードを登録してください。

#### (B) SQLite + init スクリプト（マイグレーション不要）

`.env` に `USE_SQLITE=1` を設定したうえで:

```bash
python init_db.py
```

`db.create_all()` でテーブルを作成し、`ADMIN_USERNAME` の管理者ユーザーを登録します。`ADMIN_PASSWORD` は平文・ハッシュ済みどちらでも受け付け、平文の場合は自動でハッシュ化されます。何度実行しても安全です（既存はスキップ）。

### 4. 起動

```bash
python app.py
```

デバッグモードは本番判定でないとき、かつ `FLASK_DEBUG=1`（または `true`）のときのみ有効になります。

---

## 使い方（ログイン）

ログインページは URL とゲートキーの両方で秘匿されています。

1. 合言葉付き URL にアクセス:
   ```
   https://<ホスト>/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
   ```
2. 合言葉が正しければ Cookie（`admin_gate`、90 日有効）が発行され、`?key=` なしの URL にリダイレクトされます。
3. `ADMIN_USERNAME` / `ADMIN_PASSWORD` でログインします。

ゲート Cookie を持たない訪問者にはログインページが **404** として扱われ、存在自体が隠されます。

---

## セキュリティ実装

多層防御を意識して、以下を実装しています。

- **ログインの秘匿**：秘密の URL（`ADMIN_LOGIN_PATH`）＋ ゲートキー Cookie（`ADMIN_GATE_KEY`）の二段構え。未通過は 404。
- **ブルートフォース対策**：ログイン 5 回失敗でセッション単位に 5 分間ロックアウト。エラーメッセージはユーザー名／パスワードのどちらが誤りか明かさない。
- **パスワード**：Werkzeug でハッシュ化して保存・照合（平文比較なし）。
- **CSRF 保護**：全フォームに CSRFProtect を適用。
- **セッション Cookie**：`HttpOnly` / `SameSite=Lax`、本番は `Secure` を有効化。
- **リバースプロキシ対応**：ProxyFix で `X-Forwarded-Proto/Host` を信頼し HTTPS を正しく判定。
- **セキュリティヘッダー**：`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy` を付与。
- **画像アップロード検証**：拡張子ホワイトリスト → MIME タイプ判定（filetype）→ UUID でファイル名をランダム化 → 30MB の容量制限。保存はアトミック（途中失敗時は保存済みファイルを掃除）。
- **XSS 対策**：画像キャプション・地図・YouTube のラベルは `markupsafe.escape`、地図 URL は `urllib.parse.quote` でエンコード。ハッシュタグのプレビューは `textContent` で組み立て。
- **Open Redirect 対策**：削除後のリダイレクトは同一オリジンの Referer のみ許可。
- **未ログインアクセス**：`@login_required` なページは 404 を返して存在を偽装。
- **ファイル／DB 整合性**：画像の物理削除は DB の commit 成功後に実行し、失敗時は新規保存分を掃除して不整合を防止。

---

## デプロイ

PythonAnywhere 無料枠（GitHub 経由・SQLite）への公開手順・更新運用・トラブルシューティングは、同梱の [`deploy_pythonanywhere.md`](./deploy_pythonanywhere.md) にまとめています。要点は以下のとおりです。

- Web アプリは **Manual configuration**（Python 3.10）で作成。
- Virtualenv パスと Static files（`/static/` → プロジェクトの `static`）を設定。
- WSGI ファイルは `from app import create_app` → `application = create_app()`（サンプル: `wsgi_pythonanywhere.py`）。
- `.env` は `.gitignore` により clone に含まれないため、サーバー上で手動作成。
- 依存は `requirements-pythonanywhere.txt`（PostgreSQL ドライバを除外）を使用。
- **コード更新後は必ず Web タブの「Reload」を実行**。

---

## データモデル概要

- **Post**：`title` / `body`（Markdown）/ `genre` / `created_at` / `updated_at`（未更新は NULL）/ `img_name`（カンマ区切り・Text 型）/ `img_captions`（タブ区切り）/ `default_thumb` / `is_published`。`User` と多対一、`Hashtag` と多対多。
- **Hashtag**：`name`（unique）。`Post` と多対多（中間テーブル `post_hashtags`）。どの記事にも紐付かなくなったタグは自動で削除。
- **User**：`username`（unique）/ `password`（ハッシュ）/ `nickname`（任意）。

---

## ライセンス

学習・個人利用目的のプロジェクトです。