# 個人ブログアプリ

FlaskとPostgreSQLを使って構築した、シンプルな個人ブログシステムです。マークダウン記法による記事投稿・管理、画像アップロード、ジャンル分類などの機能を備えています。

---

## 機能一覧

- **記事管理**：投稿・編集・削除・一覧表示・詳細表示
- **公開/非公開設定**：記事ごとに公開状態をトグルで切り替え
- **マークダウン記法**：`## 見出し`・`**太字**` など対応、目次（`[toc]`）自動生成
- **画像アップロード**：複数画像対応、`[img1]` プレースホルダーで本文に埋め込み
- **デフォルトサムネイル**：11種類のカテゴリ画像から選択可能
- **ジャンル分類**：既定ジャンルへの分類、または新規ジャンルの作成
- **キーワード検索**：タイトルによる絞り込み
- **管理者認証**：秘密URLによるセキュアなログイン
- **マイページ**：ニックネーム設定、自分の投稿一覧・絞り込み
- **レスポンシブデザイン**：スマホ・PC両対応（ハンバーガーメニュー付き）

---

## 技術スタック

| カテゴリ | 使用技術 |
|---|---|
| バックエンド | Python / Flask |
| データベース | PostgreSQL（psycopg3）|
| ORM | SQLAlchemy / Flask-SQLAlchemy |
| マイグレーション | Flask-Migrate / Alembic |
| 認証 | Flask-Login |
| マークダウン変換 | Python-Markdown |
| コンテナ | Docker / Docker Compose |
| フロントエンド | Jinja2 / Vanilla CSS・JS |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── extensions.py           # Flask拡張機能のインスタンス化
├── models.py               # DBモデル定義（User, Post）
├── requirements.txt
├── docker-compose.yml
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一覧・詳細・ジャンル（公開側）
│   └── admin.py            # 投稿・編集・削除・マイページ（管理者側）
├── templates/              # Jinja2テンプレート
├── static/
│   ├── css/                # ページ別CSSファイル
│   └── img/                # アップロード画像・サムネイル画像
├── migrations/             # Alembicマイグレーションファイル
└── init/                   # Docker初期化SQL
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定します。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your_secret_key

# 管理者アカウント
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password   # ハッシュ化して init/01_login.sql に記載
ADMIN_LOGIN_PATH=your_secret_path    # 例: my-secret-login
```

### 3. Dockerでデータベースを起動

```bash
docker compose up -d
```

PostgreSQLが `localhost:54321` で起動します。

### 4. Python仮想環境のセットアップ

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. データベースのマイグレーション

```bash
flask db upgrade
```

### 6. アプリケーションの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスします。

---

## 管理者ログイン

管理者用ログインページには通常のURLからはアクセスできません。`.env` の `ADMIN_LOGIN_PATH` で設定した秘密のパスを使用します。

```
http://localhost:5000/<ADMIN_LOGIN_PATH>
```

---

## 記事の書き方

| 記法 | 説明 |
|---|---|
| `## 見出し` | 大見出し（H2）|
| `### 見出し` | 中見出し（H3）|
| `**テキスト**` | 太字 |
| `[toc]` | 目次を挿入（未記入の場合は先頭に自動挿入）|
| `[img1]` | アップロード画像の1枚目を挿入（`[img2]` で2枚目…）|

---

## 環境変数一覧

| 変数名 | 説明 | 必須 |
|---|---|---|
| `POSTGRES_USER` | PostgreSQLユーザー名 | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQLパスワード | ✅ |
| `POSTGRES_DB` | データベース名 | ✅ |
| `SECRET_KEY` | FlaskセッションのSECRET_KEY | ✅ |
| `ADMIN_USERNAME` | 管理者ユーザー名 | ✅ |
| `ADMIN_PASSWORD` | 管理者パスワード（ハッシュ化済み） | ✅ |
| `ADMIN_LOGIN_PATH` | 秘密のログインURLパス | ✅ |
| `DATABASE_URL` | 本番環境用DB接続URL（省略時はローカル設定を使用）| — |