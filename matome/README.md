# MIT Blog

Flask と PostgreSQL で構築した個人ブログアプリです。  
マークダウン投稿・画像アップロード・ハッシュタグ・ジャンル分類・YouTube/地図埋め込みなど、ブログに必要な機能をひとつのシンプルなアプリで実現しています。

---

## 特徴

- **マークダウン記法**による記事投稿（H2/H3見出し・太字・目次など、ツールバーから挿入可能）
- **複数画像アップロード**と画像キャプション設定（`[img1]`, `[img2]` で本文内に配置）
- **YouTube動画の埋め込み**（URL を貼るだけでファサード表示＋クリック再生）
- **Google Maps 地図の埋め込み**（地名を入力するだけで iframe 表示）
- **ハッシュタグ**によるタグ付けと絞り込み
- **ジャンル分類**（プリセット＋独自ジャンル作成）
- **全文検索**（タイトル・ハッシュタグ横断）
- **関連記事**の自動表示（ジャンル × タグ → タグ → ジャンル → 最新 の優先順位）
- **公開/非公開**の切り替え（管理者のみ非公開記事を閲覧可能）
- **スマホ対応レスポンシブデザイン**

---

## 技術スタック

| カテゴリ | 使用技術 |
|---|---|
| バックエンド | Python 3.10 / Flask 3.1 |
| ORM / DB | SQLAlchemy 2.0 / PostgreSQL |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF保護）/ Werkzeug（パスワードハッシュ）|
| マークダウン | Python-Markdown（toc, nl2br 拡張）|
| ファイル検証 | filetype（MIME タイプ判定）|
| コンテナ | Docker / Docker Compose |
| フロントエンド | HTML / CSS / Vanilla JS |

---

## ディレクトリ構成

```
.
├── app.py              # Application Factory（アプリ起動エントリポイント）
├── config.py           # 環境変数の読み込み（.env → Python変数）
├── constants.py        # デフォルトジャンル一覧などの定数
├── extensions.py       # Flask拡張機能インスタンス（db, login_manager, migrate）
├── models.py           # DBモデル定義（User, Post, Hashtag, 中間テーブル）
├── requirements.txt
├── docker-compose.yml  # ローカルPostgreSQLコンテナ設定
├── migrations/         # Alembic マイグレーションファイル
├── static/
│   ├── css/            # スタイルシート（ページ別に分割）
│   └── img/
│       ├── posts/      # アップロードされた記事画像（.gitignore対象）
│       └── thbnails/   # デフォルトサムネイル画像
├── templates/          # Jinja2 HTMLテンプレート
└── views/
    ├── auth.py         # ログイン・ログアウト
    ├── blog.py         # 一般公開ページ（一覧・詳細・ジャンル）
    └── admin.py        # 管理者ページ（投稿・編集・削除・マイページ）
```

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repo_url>
cd <repo_dir>
```

### 2. 仮想環境の作成とパッケージインストール

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数ファイルの作成

プロジェクトルートに `.env` ファイルを作成し、以下を記述します。

```env
# PostgreSQL 接続情報（docker-compose.yml と合わせる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# 管理者アカウント
ADMIN_USERNAME=your_admin_name
ADMIN_PASSWORD=<werkzeug でハッシュ化したパスワード>

# ログインページの秘密パス（例: secret-abc123 → /secret-abc123 でアクセス）
ADMIN_LOGIN_PATH=secret-abc123

# セッション・CSRF署名用の秘密鍵（本番環境では必ず設定）
SECRET_KEY=your-very-secret-key
```

#### ADMIN_PASSWORD のハッシュ生成方法

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

### 4. PostgreSQL コンテナの起動

```bash
docker compose up -d
```

### 5. データベースの初期化

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flask シェルで初回のみ実行します。

```python
flask shell

from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import config

user = User(
    username=config.ADMIN_USERNAME,
    password=config.ADMIN_PASSWORD,  # .env に書いたハッシュ済み値
)
db.session.add(user)
db.session.commit()
```

### 7. 開発サーバーの起動

```bash
python app.py
# または
flask run
```

ブラウザで `http://localhost:5000` にアクセスします。  
管理者ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` です。

---

## 主な機能の使い方

### 記事を投稿する

1. 管理者ログイン後、ヘッダーの「新規投稿」をクリック
2. タイトル・ジャンル・本文を入力し、「投稿する」をクリック

#### マークダウン記法

| 記法 | 説明 |
|---|---|
| `## 見出し` | H2見出し |
| `### 見出し` | H3見出し |
| `**テキスト**` | 太字 |
| `[toc]` | 目次を自動生成（H2/H3から） |
| `[img1]` | アップロードした1枚目の画像を挿入 |
| `[map:東京タワー]` | Google Maps を埋め込み |
| `[youtube:<URL>]` | YouTube動画を埋め込み |

### 画像をアップロードする

- 投稿フォーム下部のファイル選択から複数枚選択可能
- アップロード後、ツールバーの `[img1]` ボタンで本文の好きな位置に挿入
- 各画像にキャプション（alt テキスト）を設定できます

### ハッシュタグを設定する

- フォームの「ハッシュタグ」欄にスペース・カンマ区切りで入力
- `#` は付けても省略しても OK（例: `Flask Python ブログ開発`）

---

## セキュリティ設計

| 対策 | 詳細 |
|---|---|
| CSRF 保護 | Flask-WTF により全フォームにトークン検証を強制 |
| パスワードハッシュ | Werkzeug の `generate_password_hash` / `check_password_hash` |
| ログインページ隠蔽 | `.env` の `ADMIN_LOGIN_PATH` で URL を秘匿 |
| ブルートフォース対策 | 5回失敗で5分間セッションロックアウト |
| ファイルアップロード検証 | 拡張子チェック + `filetype` によるMIMEタイプチェック（2層防御）|
| ファイル名サニタイズ | `secure_filename` + UUID によるランダム化 |
| Open Redirect 対策 | 削除後リダイレクト先をオリジン検証 |
| アップロードサイズ制限 | 30MB 超は 413 エラー |

---

## デプロイ（本番環境）

`.env` に以下を追加します。

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/<db>
FLASK_ENV=production
SECRET_KEY=<強力なランダム文字列>
```

`DATABASE_URL` が設定されていると本番モードとみなされ、`SECRET_KEY` が未設定の場合は起動時にエラーとなります。

---

## ライセンス

このプロジェクトは個人利用を目的として開発されています。