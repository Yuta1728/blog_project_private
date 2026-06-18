# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリです。マークダウン記述、ハッシュタグ管理、画像アップロード、地図埋め込みなど、個人ブログに必要な機能を一通り備えています。

---

## 技術スタック

| カテゴリ | 使用技術 |
|---|---|
| バックエンド | Python 3.10 / Flask 3.1 |
| ORM / マイグレーション | Flask-SQLAlchemy / Flask-Migrate (Alembic) |
| データベース | PostgreSQL 18（Docker） |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF (CSRF保護) / filetype (マジックナンバー検証) |
| マークダウン | Python-Markdown（toc・nl2br 拡張） |
| フロントエンド | Vanilla JS / CSS（フレームワークなし） |

---

## 機能一覧

**記事管理**
- 記事の作成・編集・削除
- マークダウン記述（H2/H3見出し・太字・目次 `[toc]` をツールバーから挿入）
- 公開 / 非公開の切り替え
- ジャンル分類（既定ジャンル選択 or 新規作成）
- ハッシュタグ（複数タグ、スペース/カンマ区切り入力）

**画像**
- 複数画像アップロード（最大 30MB）
- 本文中への `[img1]` `[img2]` … 形式での配置
- 画像ごとのキャプション設定
- デフォルトサムネイル選択（11種）
- 拡張子 + マジックナンバーによる二重検証

**地図**
- ツールバーから地図挿入モーダルを開き、`[map:場所名]` タグを本文に挿入
- 詳細ページで Google Maps iFrame として表示

**検索・絞り込み**
- キーワード検索（タイトル・ハッシュタグ横断）
- ジャンル一覧ページからのカテゴリ絞り込み
- ジャンル内ハッシュタグバーによるさらなる絞り込み

**管理者機能**
- 秘密 URL によるログインページ（URL は環境変数で設定）
- ニックネーム変更
- マイページ（自分の投稿一覧・ジャンル一覧）

**UI / UX**
- レスポンシブ対応（PC / スマホ）
- スマホ用ハンバーガーメニュー（ドロワー）
- 「もっと見る / 表示を減らす」による段階表示
- 目次（TOC）自動生成・スクロールリンク

---

## セットアップ

### 前提条件

- Python 3.10
- Docker / Docker Compose

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. 環境変数の設定

`.env` ファイルをプロジェクトルートに作成し、以下の変数を設定します。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your-secret-key

# 管理者アカウント
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password_hash   # Werkzeug でハッシュ化した値

# ログイン URL（秘密のパス）
ADMIN_LOGIN_PATH=your-secret-login-path
```

> **注意** `ADMIN_PASSWORD` は平文ではなく Werkzeug の `generate_password_hash()` でハッシュ化した値を設定してください。

### 3. データベースの起動（Docker）

```bash
docker compose up -d
```

### 4. Python 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. データベースのマイグレーション

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

`init/01_login.sql` を参照し、`user` テーブルに管理者アカウントを INSERT してください。パスワードは Werkzeug でハッシュ化した値を使用します。

### 7. アプリの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスして動作を確認してください。

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── extensions.py           # Flask 拡張機能（db, login_manager, migrate）
├── models.py               # SQLAlchemy モデル（User, Post, Hashtag）
├── requirements.txt
├── docker-compose.yml
├── views/
│   ├── auth.py             # ログイン / ログアウト
│   ├── blog.py             # 一般閲覧ルート（トップ・詳細・ジャンル）
│   └── admin.py            # 管理者ルート（作成・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル
├── migrations/             # Alembic マイグレーションファイル
└── init/                   # Docker 初期化 SQL
```

---

## セキュリティ対策

- **CSRF保護** — Flask-WTF によりすべてのフォームを保護
- **画像検証** — 拡張子ホワイトリスト（PNG / JPG / GIF / WebP）+ `filetype` ライブラリによるマジックナンバー検証
- **ファイルサイズ制限** — 30MB 超のリクエストを 413 エラーとしてブロック
- **ファイル名サニタイズ** — `werkzeug.utils.secure_filename` + UUID でリネーム
- **秘密 URL ログイン** — 管理者ログインページの URL を環境変数で隠蔽
- **本番環境の SECRET_KEY 未設定時は起動拒否**

---

## 本番環境へのデプロイ

本番環境では以下の環境変数を必ず設定してください。

| 変数名 | 説明 |
|---|---|
| `SECRET_KEY` | 強力なランダム文字列（未設定の場合は起動拒否） |
| `DATABASE_URL` | 接続先 PostgreSQL の URL |
| `FLASK_ENV` | `production` |

`DATABASE_URL` が設定されている場合、アプリは自動的に本番モードとして動作します。

---

## ライセンス

このプロジェクトは個人利用を目的として作成されています。