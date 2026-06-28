# MIT Blog

Flask製のパーソナルブログアプリケーションです。マークダウンによる記事執筆、画像・地図・YouTube動画の埋め込み、ジャンル・ハッシュタグによる記事管理など、ブログに必要な機能を一通り備えています。

---

## 主な機能

- **記事管理**: 新規投稿・編集・削除・公開/非公開の切り替え
- **マークダウン記述**: 見出し・太字・箇条書き・目次（[toc]）に対応
- **メディア埋め込み**: 画像（複数枚対応）・Google Maps・YouTube動画
- **画像キャプション**: 画像ごとに説明文を設定、詳細ページで figure/figcaption として表示
- **ジャンル管理**: プリセットジャンルの選択 + 独自ジャンルの新規作成
- **ハッシュタグ**: 記事へのタグ付け、タグ・ジャンルによる絞り込み
- **全文検索**: タイトル・ハッシュタグをまたいだキーワード検索
- **関連記事表示**: ジャンル・タグの一致度に基づいて最大4件を自動表示
- **セキュリティ**: CSRF保護・ブルートフォース対策・ファイルアップロード多層防御
- **レスポンシブデザイン**: PC・スマートフォンの両方に対応

---

## 技術スタック

| 分類 | 使用技術 |
|------|---------|
| バックエンド | Python 3.10 / Flask 3.1 |
| データベース | PostgreSQL（psycopg3） |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy |
| マイグレーション | Alembic / Flask-Migrate |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF）/ Werkzeug |
| マークダウン | Python-Markdown（toc・nl2br拡張） |
| インフラ | Docker Compose（PostgreSQL） |
| フロントエンド | Vanilla JS / CSS（フレームワークなし） |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── constants.py            # デフォルトジャンル一覧
├── extensions.py           # Flask拡張のインスタンス定義
├── models.py               # DBモデル（User / Post / Hashtag）
├── requirements.txt
├── docker-compose.yml
│
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
│
├── templates/              # Jinja2テンプレート
├── static/
│   ├── css/                # スタイルシート
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル画像
│
└── migrations/             # Alembicマイグレーションファイル
```

---

## セットアップ

### 前提条件

- Python 3.10+
- Docker / Docker Compose

### 1. リポジトリのクローン

```bash
git clone <リポジトリURL>
cd <プロジェクトディレクトリ>
```

### 2. 仮想環境の作成と依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定します。

```env
# PostgreSQL接続情報
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flaskセッション署名キー（ランダムな長い文字列を設定）
SECRET_KEY=your-secret-key

# 管理者情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_hashed_password  # Werkzeugでハッシュ化した値
ADMIN_LOGIN_PATH=your-secret-login-path  # ログインページのURL（例: secret-abc123）
```

> **パスワードのハッシュ化方法**
> ```python
> from werkzeug.security import generate_password_hash
> print(generate_password_hash("your_password"))
> ```

### 4. データベースの起動

```bash
docker-compose up -d
```

### 5. データベースのマイグレーション

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flaskシェルで管理者アカウントを作成します。

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
    password=os.getenv("ADMIN_PASSWORD"),
    nickname="管理者"
)
db.session.add(user)
db.session.commit()
```

### 7. アプリケーションの起動

```bash
python app.py
# または
flask run
```

ブラウザで `http://localhost:5000` にアクセスします。  
ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` から行います。

---

## 本番環境へのデプロイ

本番環境では以下の環境変数を設定してください。

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
SECRET_KEY=your-very-long-random-secret-key
FLASK_ENV=production
```

`DATABASE_URL` が設定されている場合、自動的に本番モードとして動作します。  
`SECRET_KEY` が未設定の場合は起動時にエラーになります。

---

## 記事の書き方

### マークダウン記法

```markdown
## H2見出し
### H3見出し

**太字テキスト**

● 箇条書き項目1
● 箇条書き項目2

[toc]  ← 目次を自動生成
```

### メディア埋め込みタグ

本文中に以下のタグを記述することでメディアを埋め込めます。

| タグ | 説明 |
|------|------|
| `[img1]` | アップロードした1枚目の画像を挿入 |
| `[map:東京スカイツリー]` | Google Mapsを埋め込み |
| `[youtube:https://youtu.be/xxxxx]` | YouTube動画を埋め込み（クリックで再生） |

---

## セキュリティについて

- **ログインページのURL隠蔽**: `ADMIN_LOGIN_PATH` で推測されにくいパスを設定
- **ブルートフォース対策**: 5回連続失敗で5分間ロックアウト
- **ファイルアップロード検証**: 拡張子チェック + MIMEタイプチェック（偽装対策）
- **CSRF保護**: 全フォームにCSRFトークンを適用
- **Open Redirect対策**: 削除後のリダイレクト先を同一オリジンに限定

---

## ライセンス

このプロジェクトは個人利用を目的として開発されています。