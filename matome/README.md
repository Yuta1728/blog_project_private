# 個人ブログアプリ

FlaskとPostgreSQLで構築した、管理者1名による個人運用向けのブログアプリケーションです。

---

## 主な機能

- **記事投稿・編集・削除**：タイトル・本文・ジャンル・公開設定を管理
- **Markdownレンダリング**：見出し・太字・目次（`[toc]`）に対応
- **画像アップロード**：複数枚対応、本文内への埋め込み（`[img1]` 記法）
- **サムネイル設定**：アップロード画像またはプリセット画像から選択
- **公開・非公開設定**：記事ごとに切り替え可能
- **ジャンル管理**：既定ジャンルへの選択、または新規ジャンル作成
- **キーワード検索**：タイトルによるリアルタイム絞り込み
- **マイページ**：投稿一覧・ニックネーム変更・ジャンルフィルター
- **CSRF保護**：Flask-WTFによる全フォームへの適用
- **レスポンシブ対応**：スマートフォン・タブレット・PCに対応

---

## 技術スタック

| 分類 | 技術 |
|------|------|
| バックエンド | Python 3 / Flask 3.1 |
| ORM | Flask-SQLAlchemy / SQLAlchemy 2.0 |
| DB | PostgreSQL 18（Docker） |
| マイグレーション | Flask-Migrate / Alembic |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF）、filetype（マジックナンバー検証）、Werkzeug（ファイル名サニタイズ） |
| Markdown | Python-Markdown（toc / nl2br 拡張） |
| フロントエンド | Jinja2テンプレート / Vanilla JS / CSS（note風デザイン） |
| コンテナ | Docker / Docker Compose |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数管理
├── extensions.py           # Flask拡張の初期化（db, login_manager, migrate）
├── models.py               # データモデル（Post, User）
├── requirements.txt
├── docker-compose.yml
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # トップ・詳細・ジャンル一覧
│   └── admin.py            # 投稿作成・編集・削除・マイページ
├── templates/              # Jinja2テンプレート
├── static/
│   ├── css/                # ページ別CSSファイル
│   └── img/
│       ├── posts/          # アップロードされた記事画像
│       └── thbnails/       # プリセットサムネイル画像
├── migrations/             # Alembicマイグレーションファイル
└── init/                   # PostgreSQL初期化SQL
```

---

## セットアップ

### 前提条件

- Docker / Docker Compose がインストール済みであること
- Python 3.10+ がインストール済みであること

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成します。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your-secret-key

# 管理者アカウント
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password

# ログインURL（推測されにくいパスを設定）
ADMIN_LOGIN_PATH=your-secret-login-path
```

> **注意:** 本番環境では `SECRET_KEY` を必ず設定してください。未設定の場合、アプリケーションが起動しません。

### 3. Dockerでデータベースを起動

```bash
docker-compose up -d
```

PostgreSQLが `localhost:54321` で起動します。

### 4. Python仮想環境の作成と依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
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

## 初回ログイン

1. `http://localhost:5000/<ADMIN_LOGIN_PATH>` にアクセス
2. `.env` で設定した `ADMIN_USERNAME` / `ADMIN_PASSWORD` でログイン

> ログインURLは `.env` の `ADMIN_LOGIN_PATH` で自由に設定できます（セキュリティのためデフォルトの `/login` は使用していません）。

---

## 記事の書き方

| 記法 | 説明 |
|------|------|
| `## 見出し` | 大見出し（H2） |
| `### 見出し` | 中見出し（H3） |
| `**テキスト**` | 太字 |
| `[toc]` | 目次を挿入（省略時は記事冒頭に自動挿入） |
| `[img1]` / `[img2]` … | アップロード画像を本文内に埋め込み |

---

## セキュリティ対策

- **CSRF保護**：Flask-WTFによる全フォームへの適用
- **ファイルアップロード検証**：拡張子ホワイトリスト + maジックナンバー（filetype）による二重検証
- **ファイル名サニタイズ**：`werkzeug.utils.secure_filename` + UUID付与
- **アップロードサイズ制限**：最大30MB（超過時は413エラーハンドラーで通知）
- **SECRET_KEY の強制**：本番環境で未設定の場合は起動を拒否
- **管理者のみ投稿可能**：ログインURLを秘匿化し、管理者ユーザー名で二重チェック

---

## 環境変数一覧

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `POSTGRES_USER` | ✅ | PostgreSQLユーザー名 |
| `POSTGRES_PASSWORD` | ✅ | PostgreSQLパスワード |
| `POSTGRES_DB` | ✅ | データベース名 |
| `SECRET_KEY` | ✅（本番） | Flaskセッション署名キー |
| `ADMIN_USERNAME` | ✅ | 管理者ユーザー名 |
| `ADMIN_PASSWORD` | ✅ | 管理者パスワード（ハッシュ化して保存） |
| `ADMIN_LOGIN_PATH` | ✅ | ログインURL（例: `my-secret-path`） |
| `DATABASE_URL` | 任意 | 本番DB接続URL（設定時は本番モードで動作） |
| `FLASK_ENV` | 任意 | `production` で本番モードを明示 |

---

## ライセンス

個人利用を目的として作成されたアプリケーションです。