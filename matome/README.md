# 個人ブログ アプリケーション

Flask + PostgreSQL で構築した個人用ブログシステムです。Markdown 記法による記事投稿、ハッシュタグ管理、画像アップロードなどの機能を備えています。

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| バックエンド | Python 3 / Flask 3.1 |
| データベース | PostgreSQL 18 |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy |
| マイグレーション | Alembic / Flask-Migrate |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF (CSRF保護) |
| インフラ | Docker / Docker Compose |
| フロントエンド | Jinja2 テンプレート / バニラ CSS・JS |

---

## 機能一覧

### 公開機能（ログイン不要）
- 記事一覧表示（公開記事のみ）
- ジャンル・キーワードによる絞り込み検索
- ハッシュタグによる絞り込み
- ジャンル一覧ページ
- 記事詳細表示（Markdown レンダリング・目次自動生成）

### 管理者機能（ログイン必要）
- 記事の新規投稿・編集・削除
- 公開 / 非公開の切り替え
- ハッシュタグの付与・編集
- 画像アップロード（複数枚対応、`[img1]` プレースホルダーで本文内に配置）
- デフォルトサムネイル選択（11種類）
- ジャンルの新規作成
- マイページ（投稿一覧・ニックネーム変更）

### セキュリティ対策
- 秘密URLによる管理者ログイン（URLをランダムな文字列に設定可能）
- CSRF トークン保護（全フォーム）
- ファイルアップロード検証（拡張子チェック＋マジックナンバー検証）
- アップロード上限 30 MB（超過時は 413 エラーハンドラーで制御）
- 本番環境での `SECRET_KEY` 未設定時は起動拒否

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数ロード
├── extensions.py           # Flask 拡張機能の初期化
├── models.py               # データベースモデル（Post / User / Hashtag）
├── requirements.txt
├── docker-compose.yml
├── views/
│   ├── auth.py             # 認証 Blueprint（ログイン・ログアウト）
│   ├── blog.py             # 公開 Blueprint（一覧・詳細・ジャンル）
│   └── admin.py            # 管理 Blueprint（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # スタイルシート（ページ別）
│   └── img/
│       ├── posts/          # アップロード画像
│       └── thbnails/       # デフォルトサムネイル
├── migrations/             # Alembic マイグレーションファイル
└── init/                   # PostgreSQL 初期化 SQL
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. 環境変数の設定

`.env` ファイルをプロジェクトルートに作成してください。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your-very-secret-key

# 管理者アカウント
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_hashed_password   # Werkzeug でハッシュ化した文字列
ADMIN_LOGIN_PATH=your-secret-login-path
```

> **`ADMIN_PASSWORD` のハッシュ化方法**
> ```python
> from werkzeug.security import generate_password_hash
> print(generate_password_hash("your_plain_password"))
> ```

### 3. Docker で PostgreSQL を起動

```bash
docker compose up -d
```

### 4. Python 仮想環境とパッケージのインストール

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
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

ブラウザで `http://localhost:5000` にアクセスすると公開トップページが表示されます。

管理者ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` からアクセスしてください。

---

## データモデル

```
User
├── id (PK)
├── username
├── password (ハッシュ化)
└── nickname

Post
├── id (PK)
├── title
├── body (Markdown)
├── genre
├── is_published
├── img_name (カンマ区切りファイル名)
├── default_thumb
├── created_at
├── updated_at
└── user_id (FK → User)

Hashtag
├── id (PK)
└── name (unique)

post_hashtags （中間テーブル）
├── post_id (FK → Post)
└── hashtag_id (FK → Hashtag)
```

---

## 記事の書き方

本文は Markdown 形式で記述します。

| 記法 | 説明 |
|------|------|
| `## 見出し` | 大見出し（H2） |
| `### 見出し` | 中見出し（H3） |
| `**テキスト**` | 太字 |
| `[toc]` | 目次の挿入位置を指定（省略時は自動で先頭に挿入） |
| `[img1]` / `[img2]` … | アップロード画像の挿入位置（1枚目から順に対応） |

---

## 本番デプロイ時の注意事項

- 環境変数 `DATABASE_URL` または `FLASK_ENV=production` を設定すると本番モードで動作します。
- 本番環境では `SECRET_KEY` の設定が必須です（未設定時は起動を拒否します）。
- `debug=True` は開発環境専用です。本番環境では WSGI サーバー（Gunicorn 等）を使用してください。
- `static/img/posts/` ディレクトリにはユーザーがアップロードした画像が保存されます。永続化の設定を忘れずに行ってください。

---

## ライセンス

このプロジェクトは個人利用を目的として開発されています。