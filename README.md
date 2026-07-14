# MITO Blog

Flask 製の個人用ブログアプリケーションです。Markdown による記事投稿、画像・地図・YouTube の埋め込み、ハッシュタグ／ジャンルによる絞り込み、ダークモードなどを備えた **単一管理者向け** のブログシステムです。

Application Factory パターン（`create_app()`）で構築されており、ローカル開発（PostgreSQL）と無料ホスティング（PythonAnywhere / SQLite）の両方に対応しています。

---

## 目次

- [主な機能](#主な機能)
- [技術スタック](#技術スタック)
- [ディレクトリ構成](#ディレクトリ構成)
- [動作の仕組み](#動作の仕組み)
- [セットアップ（ローカル開発）](#セットアップローカル開発)
- [環境変数](#環境変数)
- [データベースの初期化](#データベースの初期化)
- [ルート一覧](#ルート一覧)
- [記事本文の独自記法](#記事本文の独自記法)
- [セキュリティ設計](#セキュリティ設計)
- [本番デプロイ](#本番デプロイ)

---

## 主な機能

### 管理者のみの操作（要ログイン）

記事の作成・管理に関わる操作で、ログインが必要です。

- **記事の投稿・編集・削除**。`/create`・`/<id>/update`・`/<id>/delete` から行う。
- **Markdown 対応の本文入力**。専用ツールバーから H2/H3 見出し・太字・目次（`[toc]`）・箇条書きを挿入できる。
- **複数画像のアップロード**。本文中に `[imgN]` で任意の位置へ配置でき、画像ごとにキャプションを付けられる。編集時は画像の個別削除・差し替えにも対応。
- **サムネイルの設定**。専用サムネイルのアップロード、プリセットからのデフォルトサムネイル選択に対応（未設定時はシステム共通サムネイルへフォールバック）。
- **地図・YouTube の挿入**。`[map:場所名]`（Google マップ）と `[youtube:URL]`（YouTube）を本文に埋め込む。
- **ジャンル・ハッシュタグの付与**。プリセットからの選択に加え、独自ジャンル・タグの新規作成が可能。
- **公開／非公開の切り替え**。非公開記事は管理者のみ閲覧できる。
- **マイページ**（`/mypage`）。自分の投稿一覧の確認と、表示名（ニックネーム）の変更。

### 閲覧者の操作（誰でも）

ログイン不要で、すべての訪問者が利用できる操作です。

- **記事の閲覧**。公開記事の一覧・詳細を閲覧できる（非公開記事は表示されない）。
- **キーワード検索**。タイトル・ハッシュタグを対象に検索できる。
- **ジャンル／ハッシュタグでの絞り込み**。キーワードと組み合わせた **キーワード × ジャンル × ハッシュタグ** の絞り込みが可能。
- **関連記事の閲覧**。記事詳細ページで、関連度の高い記事を自動表示（ジャンル×タグ → タグ → ジャンル → 最新記事 の優先順で最大 4 件）。
- **地図・YouTube の表示／再生**。埋め込まれた地図の閲覧、YouTube はサムネイルのクリックで再生（ファサード方式）。
- **統計の確認**。トップページで総投稿数・ハッシュタグ数・最終更新日を確認できる。
- **自己紹介・使い方ページの閲覧**（`/about`・`/howto`）。

### 共通の UI / UX（管理者・閲覧者ともに利用可）

- **ダークモード**（設定は `localStorage` に保存、システム設定も検出）。
- **レスポンシブ対応**（スマホ用ドロワーメニュー、スクロール連動ヘッダー、モバイル編集ツールバーの改善）。
- **ページネーション**（記事一覧、マイページの「もっと見る」）。

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.1 |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy |
| マイグレーション | Alembic / Flask-Migrate |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF (CSRFProtect) |
| Markdown 変換 | Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype（MIME 判定） |
| DB | PostgreSQL（ローカル / 本番）または SQLite（PythonAnywhere） |
| フロント | 素の HTML / CSS / JavaScript（フレームワーク不使用） |

---

## ディレクトリ構成

```
.
├── app.py                     # エントリーポイント（create_app ファクトリ）
├── config.py                  # .env からの環境変数読み込み
├── constants.py               # デフォルトジャンル一覧
├── extensions.py              # Flask 拡張機能インスタンス（db / login_manager / migrate）
├── init_db.py                 # SQLite 用のDB初期化スクリプト
├── models.py                  # ORM モデル（Post / User / Hashtag / post_hashtags）
│
├── views/                     # Blueprint 単位のルート定義
│   ├── auth.py                # ログイン・ログアウト
│   ├── blog.py                # 一般公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py               # 管理者ページ（投稿・編集・削除・マイページ）
│
├── templates/                 # Jinja2 テンプレート
│   ├── base.html              # 共通レイアウト（ヘッダー・ドロワー・JS）
│   ├── index.html             # トップ（記事一覧）
│   ├── detail.html            # 記事詳細
│   ├── create.html            # 新規投稿フォーム
│   ├── update.html            # 記事編集フォーム
│   ├── mypage.html            # マイページ
│   ├── genre.html             # ジャンル一覧
│   ├── login.html             # 管理者ログイン
│   ├── about.html / howto.html
│   └── hero.html / stats.html / search_area.html   # 部分テンプレート
│
├── static/
│   ├── css/                   # ページ単位のスタイル + dark-mode.css 等
│   ├── img/posts/             # アップロード画像・サムネイル
│   ├── img/thbnails/          # プリセット／システムデフォルトのサムネイル
│   └── favicon/
│
├── migrations/                # Alembic マイグレーション
│
├── requirements.txt                   # ローカル／PostgreSQL 用の依存
├── requirements-pythonanywhere.txt    # PythonAnywhere／SQLite 用の依存
├── docker-compose.yml                 # ローカル開発用 PostgreSQL
├── deploy_pythonanywhere.md           # PythonAnywhere デプロイ手順
└── wsgi_pythonanywhere.py             # WSGI 設定サンプル
```

---

## 動作の仕組み

### Application Factory パターン
`app.py` の `create_app()` が Flask インスタンスを生成し、各種設定・拡張機能の初期化・Blueprint の登録を行います。拡張機能（`db` / `login_manager` / `migrate`）は `extensions.py` に「インスタンスだけ」を定義しておき、`create_app()` 内で `init_app()` により app に紐付けることで、循環インポートを回避しています。

### データモデル

```
User (管理者)              Hashtag
 ├ id                       ├ id
 ├ username                 └ name
 ├ password (ハッシュ)          ▲
 └ nickname                    │ 多対多（post_hashtags 経由）
     │ 1対多                    │
     ▼                         ▼
Post (記事) ◄──────── post_hashtags（中間テーブル）
 ├ id / title / body / genre
 ├ created_at / updated_at
 ├ img_name（本文画像・カンマ区切り）
 ├ img_captions（タブ区切り）
 ├ thumbnail_img（専用サムネイル）
 ├ default_thumb（プリセットサムネイル）
 └ is_published
```

- **サムネイルの優先順位**: `thumbnail_img` → `default_thumb` → `system-default.jpg`
- **`updated_at` は nullable**。新規投稿時は `NULL`（未更新を明示）、編集時のみ現在時刻をセットする。

### 記事本文のレンダリングフロー（記事詳細ページ）
`views/blog.py` の `detail()` は、投稿本文に対して次の変換を順に適用します。

```
post.body（Markdown + 独自タグ）
  → 連続空行を <br> に展開
  → Markdown → HTML 変換（toc / nl2br）
  → [imgN] を <img> / <figure> に置換（キャプションは escape）
  → [map:...] を Google マップ iframe に置換
  → [youtube:...] をファサード埋め込みに置換
  → detail.html へ display_body として渡す
```

---

## セットアップ（ローカル開発）

### 前提
- Python 3.10
- Docker（ローカルの PostgreSQL を使う場合）

### 手順

```bash
# 1. リポジトリを取得
git clone <このリポジトリのURL>
cd <プロジェクトフォルダ>

# 2. 仮想環境の作成・有効化
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. 依存パッケージのインストール
pip install -r requirements.txt

# 4. .env を作成（次章「環境変数」を参照）

# 5. ローカル PostgreSQL を起動（docker-compose 使用時）
docker compose up -d

# 6. マイグレーションでテーブルを作成
flask db upgrade

# 7. アプリを起動
python app.py
```

起動後、`http://127.0.0.1:5000` にアクセスします。

> **メモ**: `docker-compose.yml` はホストの `15432` 番ポートに PostgreSQL を公開します。`app.py` は `DATABASE_URL` 未設定かつ `USE_SQLITE` 未設定のとき、この `localhost:15432` に接続します。

---

## 環境変数

`.env` をプロジェクト直下（`config.py` と同じ場所）に作成します。`config.py` が絶対パスで読み込むため、起動場所に依存しません。

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `SECRET_KEY` | 本番で必須 | セッション・CSRF トークン署名用の秘密鍵。未設定だと本番起動時にエラー。 |
| `ADMIN_USERNAME` | ✅ | 管理者ログインのユーザー名。 |
| `ADMIN_PASSWORD` | ✅ | 管理者パスワード（平文・ハッシュ済みどちらも可）。 |
| `ADMIN_LOGIN_PATH` | ✅ | ログインページの URL パス（推測されにくいランダム文字列）。未設定だと起動時にエラー。 |
| `ADMIN_GATE_KEY` | ✅ | ログインページを表示するための合言葉（ゲートキー）。 |
| `FLASK_ENV` | 任意 | `production` で本番モード（Secure Cookie 有効化・`SECRET_KEY` 必須化）。 |
| `FLASK_DEBUG` | 任意 | `1` / `true` でデバッグモード（本番以外でのみ有効）。 |
| `DATABASE_URL` | 任意 | 明示指定時は最優先で使用（PostgreSQL / SQLite どちらも可）。 |
| `USE_SQLITE` | 任意 | `1` で `instance/blog.db` を SQLite として使用（PythonAnywhere 向け）。 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 任意 | ローカル PostgreSQL 接続用。 |

`.env` の例（ローカル PostgreSQL）:

```dotenv
SECRET_KEY=ここにランダムな長い文字列
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-password
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx
ADMIN_GATE_KEY=別のランダムな長い文字列

POSTGRES_USER=blog_user
POSTGRES_PASSWORD=blog_password
POSTGRES_DB=blog_db
```

ランダム文字列は次のコマンドで生成できます（`SECRET_KEY` と `ADMIN_GATE_KEY` は別々の値を使用してください）:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### DB 接続先の決定ロジック（`app.py`）

```
(1) DATABASE_URL が設定されていれば最優先
(2) USE_SQLITE=1 なら instance/blog.db（SQLite）
(3) いずれもなければ localhost:15432 のローカル PostgreSQL
```

---

## データベースの初期化

### マイグレーションを使う場合（PostgreSQL 推奨）

```bash
flask db upgrade                       # 既存マイグレーションを適用
# モデル変更後:
flask db migrate -m "変更内容"          # 差分から新しいマイグレーションを生成
flask db upgrade                       # 生成した差分を適用
```

管理者ユーザーは別途 DB に登録する必要があります（`ADMIN_USERNAME` と一致するユーザーが存在しないとログインできません）。

### マイグレーションを使わない場合（SQLite）

`init_db.py` がテーブル作成と管理者ユーザー登録を一括で行います。

```bash
python init_db.py
```

`db.create_all()` でテーブルを作成し、`ADMIN_USERNAME` の管理者ユーザーを作成します（`ADMIN_PASSWORD` は平文・ハッシュ済みどちらでも受け付け、平文なら自動でハッシュ化）。何度実行しても安全です。

---

## ルート一覧

### 一般公開（`views/blog.py`）

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | トップ（記事一覧・検索・絞り込み・統計） |
| GET | `/<id>/detail` | 記事詳細 |
| GET | `/genre` | ジャンル一覧 |
| GET | `/about` | 管理者の自己紹介 |
| GET | `/howto` | 使い方 |

### 認証（`views/auth.py`）

| メソッド | パス | 説明 |
|----------|------|------|
| GET/POST | `/<ADMIN_LOGIN_PATH>` | 管理者ログイン（ゲートキーで保護） |
| GET | `/logout` | ログアウト |

### 管理者専用（`views/admin.py`、要ログイン）

| メソッド | パス | 説明 |
|----------|------|------|
| GET/POST | `/create` | 新規投稿 |
| GET/POST | `/<id>/update` | 記事編集 |
| POST | `/<id>/delete` | 記事削除 |
| GET/POST | `/mypage` | マイページ（投稿一覧・ニックネーム変更） |

> 未ログインで管理者ページにアクセスすると、ログイン画面へ誘導せず **404 を返して存在を隠します**。

---

## 記事本文の独自記法

Markdown に加えて、以下の独自タグを本文で使えます（ツールバーから挿入可能）。

| 記法 | 変換結果 |
|------|----------|
| `[toc]` | 目次（本文中の見出しから自動生成） |
| `[imgN]` | N 番目のアップロード画像を挿入（キャプションがあれば `<figure>` として表示） |
| `[map:場所名]` | Google マップの埋め込み（例: `[map:東京スカイツリー]`） |
| `[youtube:URL]` | YouTube 埋め込み（URL・短縮 URL・shorts・embed・動画 ID に対応。クリックで再生開始） |

---

## セキュリティ設計

このアプリは学習を兼ねて、多層的なセキュリティ対策を実装しています。

- **ログイン URL の隠蔽**: `ADMIN_LOGIN_PATH` によりログインページの URL 自体を秘匿。
- **ゲートキー方式**: `ADMIN_GATE_KEY` を含む合言葉付き URL で初回アクセスし、Cookie を発行。Cookie を持たない訪問者にはログインページも 404 を返す（設定漏れ時は 404 にフォールバックするフェイルクローズ設計）。
- **ブルートフォース対策**: ログイン連続失敗 5 回で 5 分間ロックアウト（セッションベース）。
- **パスワードのハッシュ化**: Werkzeug の `check_password_hash` で照合。平文は保存しない。
- **CSRF 対策**: 全フォームに CSRF トークンを強制（Flask-WTF）。
- **ファイルアップロード検証（多層防御）**: 拡張子チェック → `filetype` による MIME タイプチェック → UUID によるファイル名ランダム化 → 30MB の容量制限。
- **アトミックなファイル保存**: 画像保存は「全成功 or 全掃除」を保証。DB コミット失敗時は保存済みファイルを掃除し、コミット成功後にのみ旧ファイルを物理削除して整合性を担保。
- **XSS 対策**: 画像キャプション・地図の場所名・YouTube の入力を `markupsafe.escape` でエスケープ。ハッシュタグのプレビュー生成も `innerHTML` を避け DOM API で構築。
- **Open Redirect 対策**: 削除後のリダイレクト先を同一オリジンかどうか検証。
- **セキュリティヘッダー**: `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` を付与。
- **Secure Cookie**: 本番では `SESSION_COOKIE_SECURE` を有効化。`ProxyFix` によりリバースプロキシ配下でも HTTPS を正しく判定。

---

## 本番デプロイ

PythonAnywhere 無料枠（SQLite 運用）への GitHub 経由デプロイ手順は、
[`deploy_pythonanywhere.md`](./deploy_pythonanywhere.md) に詳細な仕様書としてまとめてあります。

概要:

1. コードを GitHub に push
2. PythonAnywhere で `git clone`
3. 仮想環境を作成し `requirements-pythonanywhere.txt` をインストール
4. サーバー上で `.env` を作成（`USE_SQLITE=1` / `FLASK_ENV=production` を含める）
5. `python init_db.py` でテーブルと管理者ユーザーを作成
6. Web タブで Manual configuration（Python 3.10）を設定し、WSGI ファイルを編集
7. Reload して公開

更新は「PC で修正 → GitHub に push → サーバーで `git pull` → Web タブで Reload」が基本の流れです。

---

## ライセンス

個人利用・学習目的のプロジェクトです。