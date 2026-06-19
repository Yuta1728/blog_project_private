# MIT Blog

個人用ブログアプリケーション。Flask + PostgreSQL で構築した、マークダウン記事投稿・管理システムです。

---

## 主な機能

- **記事の投稿・編集・削除**（管理者のみ）
- **マークダウン記法**による本文入力（H2/H3見出し、太字、目次など）
- **複数画像アップロード**と `[img1]`, `[img2]` 形式での本文埋め込み
- **画像キャプション**の設定
- **デフォルトサムネイル**の選択（11種類）
- **ジャンル分類**（プリセット27種 + カスタムジャンル作成）
- **ハッシュタグ**の付与・絞り込みフィルター
- **キーワード検索**（タイトル・ハッシュタグを横断）
- **公開/非公開**切り替え
- **地図挿入**（`[map:場所名]` でGoogle Mapsを埋め込み）
- **目次自動生成**（`[toc]` マーカー）
- **もっと見る**ボタンによる段階的な記事表示
- **ニックネーム**変更
- ブルートフォース対策付き**管理者ログイン**（セッションベースのロックアウト）
- **CSRF保護**（Flask-WTF）

---

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| バックエンド | Python 3.10 / Flask 3.1 |
| データベース | PostgreSQL 18 |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy |
| マイグレーション | Alembic / Flask-Migrate |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF (CSRF) / Werkzeug (パスワードハッシュ) / filetype (MIMEチェック) |
| マークダウン | Python-Markdown (toc, nl2br 拡張) |
| インフラ | Docker Compose (PostgreSQL) |
| フロントエンド | Jinja2 / Vanilla JS / CSS |

---

## ディレクトリ構成

```
matome/
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数読み込み
├── constants.py            # デフォルトジャンル定義
├── extensions.py           # db / login_manager / migrate
├── models.py               # User / Post / Hashtag モデル
├── requirements.txt
├── docker-compose.yml
│
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一覧・詳細・ジャンル一覧
│   └── admin.py            # 投稿作成・編集・削除・マイページ
│
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/
│   ├── img/posts/          # アップロード画像の保存先
│   └── img/thbnails/       # デフォルトサムネイル
│
├── migrations/             # Alembic マイグレーションファイル
└── init/                   # PostgreSQL 初期化 SQL
```

---

## セットアップ

### 前提条件

- Python 3.10
- Docker / Docker Compose

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd matome
```

### 2. 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env` ファイルをプロジェクトルートに作成します。

```env
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password_hash   # Werkzeug でハッシュ化したもの
ADMIN_LOGIN_PATH=your_secret_login_path   # 例: secret-login-abc123

SECRET_KEY=your_strong_secret_key
```

> **補足：パスワードハッシュの生成**
> ```python
> from werkzeug.security import generate_password_hash
> print(generate_password_hash("your_password"))
> ```

### 4. PostgreSQL の起動

```bash
docker compose up -d
```

### 5. データベースのマイグレーション

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flask シェルから直接登録します。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import os

user = User(
    username=os.getenv("ADMIN_USERNAME"),
    password=generate_password_hash("your_password"),
    nickname="管理者名"
)
db.session.add(user)
db.session.commit()
```

### 7. 開発サーバーの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスします。

管理者ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` です。

---

## 環境変数一覧

| 変数名 | 必須 | 説明 |
|---|---|---|
| `POSTGRES_USER` | ✅ | PostgreSQL ユーザー名 |
| `POSTGRES_PASSWORD` | ✅ | PostgreSQL パスワード |
| `POSTGRES_DB` | ✅ | データベース名 |
| `ADMIN_USERNAME` | ✅ | 管理者のユーザー名 |
| `ADMIN_PASSWORD` | ✅ | 管理者パスワード（ハッシュ値） |
| `ADMIN_LOGIN_PATH` | ✅ | ログインページのパス（秘密のURL） |
| `SECRET_KEY` | ✅ (本番) | Flask セッション用シークレットキー |
| `DATABASE_URL` | — | 本番DBのURL（設定時は本番モードで起動） |

---

## 本文記法

| 記法 | 説明 |
|---|---|
| `## 見出し` | H2 見出し |
| `### 見出し` | H3 見出し |
| `**太字**` | 太字テキスト |
| `[toc]` | その位置に目次を挿入 |
| `[img1]`, `[img2]` | アップロード画像をその位置に挿入 |
| `[map:場所名]` | Google Maps を埋め込み |

---

## セキュリティ

- ログイン試行が **5回失敗**すると **5分間ロックアウト**（セッションベース）
- ファイルアップロードは **拡張子 + MIMEタイプ**の二重チェック（画像偽装防止）
- アップロード上限 **30MB**（超過時は 413 ハンドラでフラッシュメッセージ表示）
- 全フォームに **CSRFトークン**を適用
- 管理者ページへの URL は `.env` で秘匿化
- Open Redirect 対策（削除後リダイレクト時に同一オリジンを検証）