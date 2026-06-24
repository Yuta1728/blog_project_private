# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリケーションです。マークダウン記事の投稿・管理に加え、ジャンル分類・ハッシュタグ・画像アップロード・Google マップ埋め込み・YouTube 埋め込みに対応しています。

---

## 技術スタック

| カテゴリ | 使用技術 |
|---|---|
| バックエンド | Python 3.10 / Flask 3.1 |
| データベース | PostgreSQL 18（Docker 経由） |
| ORM | Flask-SQLAlchemy / Flask-Migrate (Alembic) |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF）/ Werkzeug（パスワードハッシュ）/ filetype（MIME 検証）|
| マークダウン | Python-Markdown（TOC・nl2br 拡張）|
| フロントエンド | Jinja2 テンプレート / 素の CSS・JS |

---

## ディレクトリ構成

```
.
├── app.py                  # Application Factory
├── config.py               # .env 読み込み・設定値
├── constants.py            # デフォルトジャンル一覧
├── extensions.py           # db / login_manager / migrate インスタンス
├── models.py               # User / Post / Hashtag モデル
├── requirements.txt
├── docker-compose.yml      # PostgreSQL コンテナ
├── migrations/             # Alembic マイグレーション
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
└── static/
    ├── css/
    └── img/
        ├── posts/          # アップロード画像の保存先
        └── thbnails/       # デフォルトサムネイル画像
```

---

## 機能一覧

### 一般閲覧者向け

- 記事一覧（最新順）・キーワード検索・ジャンル絞り込み
- ハッシュタグによる絞り込み
- 記事詳細（マークダウンレンダリング・目次自動生成）
- Google マップ埋め込み（`[map:場所名]` 記法）
- YouTube 埋め込み（`[youtube:URL]` 記法、ファサードパターンで遅延読み込み）
- ジャンル一覧ページ

### 管理者向け

- 秘密の URL によるログイン（ブルートフォース対策：5回失敗で5分ロック）
- 記事の新規投稿・編集・削除
- 複数画像アップロード（`[img1]`, `[img2]` 記法で本文中に配置）
- 画像へのキャプション付与
- デフォルトサムネイル選択
- ジャンル・ハッシュタグ管理
- 公開 / 非公開設定
- ニックネーム変更
- マークダウンツールバー（H2/H3/太字/目次/地図/YouTube/画像挿入）

---

## セットアップ

### 前提条件

- Python 3.10
- Docker / Docker Compose
- Node.js（不要）

### 1. リポジトリのクローン

```bash
git clone <リポジトリURL>
cd <プロジェクトディレクトリ>
```

### 2. 仮想環境の作成と依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成します。

```env
# PostgreSQL 接続情報（docker-compose.yml と合わせる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# 管理者認証情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=<werkzeug generate_password_hash で生成したハッシュ値>
ADMIN_LOGIN_PATH=your-secret-login-path

# セッション署名キー（本番環境では必須）
SECRET_KEY=your-very-secret-key
```

**`ADMIN_PASSWORD` のハッシュ生成方法：**

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

**管理者ユーザーを DB に登録する方法：**

```python
# flask shell などで実行
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import os

user = User(
    username=os.getenv("ADMIN_USERNAME"),
    password=generate_password_hash("your_password"),
    nickname="MIT"
)
db.session.add(user)
db.session.commit()
```

### 4. PostgreSQL の起動

```bash
docker-compose up -d
```

ホスト側のポート `54321` にマッピングされます。

### 5. データベースマイグレーション

```bash
flask db upgrade
```

### 6. アプリケーションの起動

```bash
python app.py
# または
flask run
```

ブラウザで `http://localhost:5000` にアクセスします。

---

## ログイン

管理者ログインページの URL は `.env` の `ADMIN_LOGIN_PATH` で設定した値です。

```
http://localhost:5000/<ADMIN_LOGIN_PATH>
```

例：`ADMIN_LOGIN_PATH=secret-abc123` の場合 → `http://localhost:5000/secret-abc123`

---

## マークダウン記法

本文内で使用できる独自タグは以下のとおりです。

| タグ | 説明 |
|---|---|
| `[toc]` | 目次を自動生成して挿入 |
| `[img1]`, `[img2]` ... | アップロードした画像をその位置に表示 |
| `[map:東京スカイツリー]` | Google マップを埋め込み |
| `[youtube:https://youtu.be/xxxxx]` | YouTube 動画を埋め込み（動画 ID 直接指定も可）|

---

## 環境変数一覧

| 変数名 | 説明 | 必須 |
|---|---|---|
| `POSTGRES_USER` | DB ユーザー名 | ✅ |
| `POSTGRES_PASSWORD` | DB パスワード | ✅ |
| `POSTGRES_DB` | DB 名 | ✅ |
| `ADMIN_USERNAME` | 管理者ユーザー名 | ✅ |
| `ADMIN_PASSWORD` | 管理者パスワード（ハッシュ値）| ✅ |
| `ADMIN_LOGIN_PATH` | ログインページのパス | ✅ |
| `SECRET_KEY` | Flask セッション署名キー（本番必須）| 本番のみ必須 |
| `DATABASE_URL` | 本番 DB 接続 URL（Heroku/Render 等）| 本番のみ |

---

## セキュリティ

- **CSRF 保護**：Flask-WTF により全フォームにトークン検証を適用
- **パスワードハッシュ**：Werkzeug の `generate_password_hash` / `check_password_hash`
- **ブルートフォース対策**：5回連続失敗で5分間ロックアウト
- **秘密のログイン URL**：ログインページの存在自体を隠蔽
- **画像検証の多層防御**：拡張子チェック → MIME タイプ検証（filetype）→ ファイル名サニタイズ（Werkzeug）→ UUID でリネーム
- **ファイルサイズ制限**：30MB を超えるアップロードを拒否
- **Open Redirect 対策**：削除後リダイレクト時に同一オリジンを検証

---

## マイグレーション管理

```bash
# モデル変更後、差分を検出してマイグレーションファイルを生成
flask db migrate -m "変更内容の説明"

# DB に変更を適用
flask db upgrade

# 1つ前のバージョンに戻す
flask db downgrade
```