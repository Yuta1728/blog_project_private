# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリケーションです。  
マークダウン記法による記事執筆・ハッシュタグ管理・画像アップロード・YouTube／地図埋め込みなど、ブログに必要な機能を一通り備えています。

---

## 主な機能

| カテゴリ | 機能 |
|---|---|
| 記事管理 | 作成・編集・削除・公開/非公開切替 |
| コンテンツ | マークダウン記法・目次（TOC）自動生成 |
| メディア | 複数画像アップロード・画像キャプション・デフォルトサムネイル |
| 埋め込み | Google マップ・YouTube（ファサードパターン） |
| 分類 | ジャンル・ハッシュタグによる絞り込み |
| 検索 | タイトル・ハッシュタグのキーワード検索 |
| 管理 | 管理者ログイン（秘密の URL・ブルートフォース対策）|
| UX | レスポンシブデザイン・スクロール連動ヘッダー |

---

## 技術スタック

- **バックエンド**: Python 3.10 / Flask 3.x
- **DB**: PostgreSQL（接続: psycopg 3）
- **ORM / マイグレーション**: Flask-SQLAlchemy / Flask-Migrate（Alembic）
- **認証**: Flask-Login + Werkzeug（パスワードハッシュ）
- **CSRF 対策**: Flask-WTF
- **マークダウン変換**: Python-Markdown（toc・nl2br 拡張）
- **ファイル検証**: filetype ライブラリ（MIME タイプ判定）
- **コンテナ**: Docker Compose（ローカル PostgreSQL）

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── constants.py            # デフォルトジャンル定数
├── extensions.py           # db / login_manager / migrate インスタンス
├── models.py               # User / Post / Hashtag モデル
├── requirements.txt
├── docker-compose.yml
│
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
│
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル
└── migrations/             # Alembic マイグレーションファイル
```

---

## セットアップ

### 必要な環境

- Python 3.10+
- Docker & Docker Compose

### 1. リポジトリをクローン

```bash
git clone <リポジトリURL>
cd <プロジェクトディレクトリ>
```

### 2. 仮想環境を作成して依存パッケージをインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数を設定

プロジェクトルートに `.env` ファイルを作成します。

```env
# PostgreSQL 接続情報
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション署名キー（本番環境では長くランダムな文字列を使用）
SECRET_KEY=your-secret-key

# 管理者情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=<werkzeug でハッシュ化したパスワード>
ADMIN_LOGIN_PATH=your-secret-login-path
```

**パスワードのハッシュ化方法:**

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

### 4. データベースを起動

```bash
docker compose up -d
```

### 5. テーブルを作成（マイグレーション実行）

```bash
flask db upgrade
```

### 6. 管理者ユーザーを登録

Flask シェルで直接 DB に挿入します。

```python
flask shell

from extensions import db
from models import User
from werkzeug.security import generate_password_hash

user = User(
    username="your_admin_username",
    password=generate_password_hash("your_password"),
    nickname="MIT"
)
db.session.add(user)
db.session.commit()
```

### 7. アプリを起動

```bash
python app.py
# または
flask run
```

ブラウザで `http://localhost:5000` にアクセスします。  
管理者ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` から行います。

---

## 記事の書き方

### マークダウン記法

本文はマークダウン形式で記述します。エディタ上部のツールバーから主要な書式を挿入できます。

```markdown
## H2 見出し（大見出し）
### H3 見出し（中見出し）

**太字テキスト**

[toc]  ← 目次を自動生成（見出しから作られます）
```

### 画像の挿入

フォームで画像ファイルをアップロードすると、本文中に `[img1]`・`[img2]` のタグで埋め込めます。  
各画像にキャプション（説明文）を設定することも可能です。

```
本文テキスト...
[img1]
続きのテキスト...
[img2]
```

### 地図・YouTube の挿入

ツールバーのボタンからモーダルを開いて挿入します。  
本文には以下の形式で保存されます。

```
[map:東京スカイツリー]
[youtube:https://www.youtube.com/watch?v=XXXXXXXXXXX]
```

---

## セキュリティ対策

- **ログイン URL の秘匿**: `ADMIN_LOGIN_PATH` に推測困難な文字列を設定し、ログインページの存在を隠蔽
- **ブルートフォース対策**: 5 回連続失敗で 5 分間ロックアウト
- **パスワードハッシュ化**: Werkzeug の `generate_password_hash` / `check_password_hash` を使用
- **CSRF 対策**: Flask-WTF によるトークン検証を全フォームに適用
- **ファイルアップロード検証**: 拡張子チェック（第 1 層）+ filetype による MIME タイプ判定（第 2 層）
- **ファイル名のサニタイズ**: `secure_filename` + UUID によるランダムリネーム
- **アップロードサイズ制限**: 30MB 上限（`MAX_CONTENT_LENGTH`）
- **Open Redirect 対策**: リダイレクト先を同一オリジンに限定

---

## 本番環境へのデプロイ

環境変数 `DATABASE_URL`（または `FLASK_ENV=production`）が設定されている場合、アプリは本番モードで起動します。  
本番環境では必ず `SECRET_KEY` を設定してください（未設定の場合は起動時にエラー）。

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
SECRET_KEY=長くてランダムな文字列
```

---

## ライセンス

個人利用を目的としたプロジェクトです。