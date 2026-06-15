# MIT Blog — 個人ブログアプリ

Flask + PostgreSQL で構築した個人運営向けのブログアプリです。
マークダウン記法による記事投稿・編集、ジャンル管理、ハッシュタグ絞り込みなどの機能を備えています。

---

## 主な機能

- **記事の投稿・編集・削除**（管理者のみ）
- **マークダウン記法**による本文入力（見出し・太字・目次・画像埋め込み）
- **ジャンル管理**（既定ジャンルの選択 or 新規ジャンルの作成）
- **ハッシュタグ**の付与・絞り込み表示
- **公開 / 非公開**の切り替え
- **複数画像アップロード**（PNG / JPG / GIF / WebP）
- **デフォルトサムネイル**の選択（11種類）
- **キーワード検索**
- **ニックネーム変更**（マイページ）
- レスポンシブ対応（PC / スマートフォン）

---

## 技術スタック

| 種別 | 使用技術 |
|------|----------|
| バックエンド | Python 3.10 / Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / Alembic (Flask-Migrate) |
| データベース | PostgreSQL 18 (Docker) |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF (CSRF保護) / Werkzeug |
| マークダウン | Python-Markdown（toc / nl2br 拡張） |
| 画像検証 | filetype（マジックナンバー検証） |
| フロントエンド | Jinja2 テンプレート / バニラ JS / CSS |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── extensions.py           # db / login_manager / migrate の初期化
├── models.py               # DB モデル（User / Post / Hashtag）
├── views/
│   ├── auth.py             # ログイン / ログアウト
│   ├── blog.py             # トップ画面 / 記事詳細 / ジャンル一覧
│   └── admin.py            # 投稿作成 / 編集 / 削除 / マイページ
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # スタイルシート
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル画像
├── migrations/             # Alembic マイグレーションファイル
├── init/                   # Docker 用 DB 初期化 SQL
└── docker-compose.yml
```

---

## セットアップ

### 必要な環境

- Python 3.10
- Docker / Docker Compose

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成してください。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your-secret-key

# 管理者アカウント
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_hashed_password   # Werkzeug でハッシュ化した値
ADMIN_LOGIN_PATH=your-secret-login-path
```

> **注意：** `ADMIN_LOGIN_PATH` はログイン画面の URL パスになります。推測されにくい文字列を設定してください（例: `a1b2c3d4`）。

### 3. 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Docker で PostgreSQL を起動

```bash
docker compose up -d
```

### 5. DB マイグレーションの実行

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flask シェルを使って管理者ユーザーを登録します。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

user = User(
    username="<ADMIN_USERNAMEと同じ値>",
    password=generate_password_hash("<ログインパスワード>"),
    nickname="管理者"
)
db.session.add(user)
db.session.commit()
```

### 7. アプリの起動

```bash
flask run
```

ブラウザで `http://localhost:5000` を開くと、トップ画面が表示されます。  
ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` にアクセスしてください。

---

## 主要な画面

| 画面 | URL | 説明 |
|------|-----|------|
| トップ | `/` | 記事一覧（ジャンル・ハッシュタグ・キーワードで絞り込み可） |
| 記事詳細 | `/<id>/detail` | 記事本文の表示（目次・画像付き） |
| ジャンル一覧 | `/genre` | ジャンルのカテゴリ別一覧 |
| ログイン | `/<ADMIN_LOGIN_PATH>` | 管理者ログイン |
| 新規投稿 | `/create` | 記事の新規作成（要ログイン） |
| 編集 | `/<id>/update` | 記事の編集（要ログイン） |
| マイページ | `/mypage` | 自分の投稿一覧・ニックネーム変更 |

---

## セキュリティ対策

- **CSRF 保護**：Flask-WTF によりすべてのフォームに CSRF トークンを付与
- **ファイル検証**：拡張子チェックに加え、`filetype` ライブラリによるマジックナンバー検証で画像偽装を防止
- **ファイルサイズ制限**：アップロード上限 30 MB（超過時は 413 エラーハンドラーで対応）
- **ファイル名サニタイズ**：`werkzeug.utils.secure_filename` を使用
- **非公開記事の保護**：未ログイン時・他ユーザーからは非公開記事へのアクセスを遮断
- **SECRET_KEY 検証**：本番環境で未設定の場合は起動を拒否
- **秘密のログイン URL**：ログインページのパスを環境変数で隠蔽

---

## マークダウン記法ガイド

投稿本文では以下の記法が使えます。

| 記法 | 効果 |
|------|------|
| `## 見出し` | 大見出し（H2） |
| `### 見出し` | 中見出し（H3） |
| `**テキスト**` | 太字 |
| `[toc]` | 目次を挿入（省略時は先頭に自動挿入） |
| `[img1]` `[img2]` … | アップロード画像を本文中に挿入 |

---

## ライセンス

個人利用を目的としたプロジェクトです。