# MIT Blog

Flask + PostgreSQL で構築した個人用ブログアプリケーションです。

---

## 主な機能

- **記事の投稿・編集・削除**（ログイン後のみ）
- **Markdown記法**で本文を書ける（H2/H3見出し・太字・目次 `[toc]`）
- **画像の複数アップロード**（本文中に `[img1]`, `[img2]` で埋め込み）
- **画像キャプション**の設定
- **Google マップ埋め込み**（ツールバーの地図ボタン、または `[map:場所名]` 記法）
- **ハッシュタグ**（投稿への付与・タグによる絞り込み）
- **ジャンル管理**（既定ジャンル＋独自ジャンル作成）
- **公開 / 非公開**切り替え
- **デフォルトサムネイル選択**（11種類のプリセット画像）
- **キーワード検索**（タイトル・ハッシュタグを横断検索）
- **「もっと見る」ボタン**による記事の段階的表示
- **ニックネーム変更**（マイページ）
- **レスポンシブ対応**（PC・スマホ・タブレット）

---

## 技術スタック

| 種別 | 採用技術 |
|------|----------|
| 言語 | Python 3.10 |
| Webフレームワーク | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| DB | PostgreSQL 18（Docker） |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF保護） |
| Markdown変換 | Python-Markdown（toc・nl2br 拡張） |
| ファイル検証 | filetype（マジックナンバー検証） |
| テンプレートエンジン | Jinja2 |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── extensions.py           # Flask拡張の初期化（db, login_manager, migrate）
├── models.py               # DBモデル（User, Post, Hashtag）
├── requirements.txt
├── docker-compose.yml      # PostgreSQL コンテナ設定
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 記事一覧・詳細・ジャンル一覧
│   └── admin.py            # 記事作成・編集・削除・マイページ
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # スタイルシート
│   └── img/
│       ├── posts/          # アップロードされた画像（自動生成）
│       └── thbnails/       # デフォルトサムネイル画像
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
git clone <リポジトリURL>
cd <プロジェクトフォルダ>
```

### 2. 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下を記載します。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your_secret_key

# 管理者情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_hashed_password
ADMIN_LOGIN_PATH=your_secret_login_path
```

> `ADMIN_PASSWORD` には Werkzeug の `generate_password_hash()` で生成したハッシュ値を設定してください。

### 4. PostgreSQL コンテナの起動

```bash
docker compose up -d
```

ポート `54321`（ホスト）→ `5432`（コンテナ）でアクセスできます。

### 5. データベースのマイグレーション

```bash
flask db upgrade
```

### 6. 開発サーバーの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` を開きます。

---

## ログイン

管理者ログインページのURLは `.env` の `ADMIN_LOGIN_PATH` に設定した値になります。

```
http://localhost:5000/<ADMIN_LOGIN_PATH>
```

セキュリティのため、ログインページのURLは公開しない設計になっています。

---

## 記事の書き方

### Markdown記法

本文はMarkdown形式で記述できます。

```
## 見出し2
### 見出し3

**太字テキスト**

[toc]  ← この位置に目次が自動生成されます
```

### 画像の埋め込み

複数枚の画像をアップロードすると、本文中の任意の位置に配置できます。

```
ここに文章を書く。

[img1]

続きの文章を書く。

[img2]
```

### Google マップの埋め込み

ツールバーの「🗺️ 地図」ボタン、または直接 `[map:場所名]` と記述します。

```
[map:東京スカイツリー]
```

---

## セキュリティ対策

- **CSRF保護**：Flask-WTF によりすべてのフォームに適用
- **ファイルアップロード検証**：拡張子ホワイトリスト＋ `filetype` によるマジックナンバー検証（画像偽装ブロック）
- **ファイルサイズ制限**：最大 30MB
- **ファイル名サニタイズ**：`werkzeug.utils.secure_filename` と UUID によるリネーム
- **ログインURL秘匿**：環境変数でURLを設定
- **本番環境の SECRET_KEY 必須チェック**：未設定時は起動を拒否

---

## 環境変数一覧

| 変数名 | 説明 |
|--------|------|
| `POSTGRES_USER` | PostgreSQL ユーザー名 |
| `POSTGRES_PASSWORD` | PostgreSQL パスワード |
| `POSTGRES_DB` | PostgreSQL データベース名 |
| `SECRET_KEY` | Flask セッション暗号化キー（本番環境では必須） |
| `ADMIN_USERNAME` | 管理者ユーザー名 |
| `ADMIN_PASSWORD` | 管理者パスワード（ハッシュ値） |
| `ADMIN_LOGIN_PATH` | ログインページのURLパス（秘密のパス） |
| `DATABASE_URL` | 本番DB接続URL（設定時に本番モードと判定） |
| `FLASK_ENV` | `production` に設定すると本番モード |