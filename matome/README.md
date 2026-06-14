# 個人ブログアプリ

Flask + PostgreSQL で構築した個人向けブログシステムです。管理者が記事を投稿・管理し、一般訪問者が閲覧できるシンプルな構成になっています。

---

## 目次

- [個人ブログアプリ](#個人ブログアプリ)
  - [目次](#目次)
  - [機能一覧](#機能一覧)
    - [一般訪問者向け](#一般訪問者向け)
    - [管理者向け](#管理者向け)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [環境構築](#環境構築)
    - [前提条件](#前提条件)
    - [手順](#手順)
  - [環境変数の設定](#環境変数の設定)
  - [データベースのセットアップ](#データベースのセットアップ)
  - [起動方法](#起動方法)
  - [使い方](#使い方)
    - [記事の投稿](#記事の投稿)
    - [Markdown 記法](#markdown-記法)
    - [ハッシュタグの入力](#ハッシュタグの入力)
  - [セキュリティについて](#セキュリティについて)

---

## 機能一覧

### 一般訪問者向け
- 記事一覧の閲覧（公開記事のみ）
- キーワード検索
- ジャンルによる絞り込み
- ハッシュタグによる絞り込み
- 記事詳細の閲覧（Markdown レンダリング / 目次自動生成）

### 管理者向け
- 秘密URLによるログイン / ログアウト
- 記事の新規投稿・編集・削除
- 公開 / 非公開の切り替え
- ジャンルの選択・新規作成
- ハッシュタグの付与（複数可）
- 画像の複数アップロード（`[img1]` 形式で本文に埋め込み）
- デフォルトサムネイル画像の選択（11種類）
- ニックネームの変更

---

## 技術スタック

| カテゴリ | 使用技術 |
|---|---|
| バックエンド | Python 3 / Flask 3.1 |
| データベース | PostgreSQL（Docker）|
| ORM | Flask-SQLAlchemy 3.1 / Alembic（Flask-Migrate） |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF保護）/ Werkzeug（パスワードハッシュ）|
| Markdown | Python-Markdown（toc・nl2br 拡張） |
| ファイル検証 | filetype（マジックナンバー検証） |
| フロントエンド | Jinja2 テンプレート / 素の CSS（レスポンシブ対応） |
| コンテナ | Docker / Docker Compose |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── extensions.py           # db / login_manager / migrate の初期化
├── models.py               # User / Post / Hashtag モデル定義
├── requirements.txt
├── docker-compose.yml      # PostgreSQL コンテナ定義
├── init/                   # DB 初期化 SQL（初回起動時に自動実行）
│   ├── 01_login.sql        # 管理者ユーザーの作成
│   └── 02_post.sql         # サンプルデータ（任意）
├── migrations/             # Alembic マイグレーションファイル
├── static/
│   ├── css/                # スタイルシート（ページ別）
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル画像（11種＋system-default）
├── templates/              # Jinja2 テンプレート
│   ├── base.html
│   ├── index.html
│   ├── detail.html
│   ├── create.html
│   ├── update.html
│   ├── mypage.html
│   ├── genre.html
│   └── login.html
└── views/
    ├── auth.py             # ログイン / ログアウト
    ├── blog.py             # 記事一覧 / 詳細 / ジャンル一覧
    └── admin.py            # 投稿 / 編集 / 削除 / マイページ
```

---

## 環境構築

### 前提条件

- Python 3.11 以上
- Docker / Docker Compose
- pip

### 手順

```bash
# 1. リポジトリのクローン
git clone <repository-url>
cd <repository-dir>

# 2. 仮想環境の作成・有効化
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 依存ライブラリのインストール
pip install -r requirements.txt

# 4. PostgreSQL コンテナの起動
docker compose up -d
```

---

## 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定してください。

```env
# PostgreSQL 接続情報
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション用シークレットキー（本番環境では必ず設定）
SECRET_KEY=your-strong-secret-key

# 管理者アカウント情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password   # ハッシュ化済みパスワードを init/01_login.sql に記載

# ログインページの秘密パス（例: "admin-login-abc123"）
ADMIN_LOGIN_PATH=your-secret-login-path
```

> **注意**: `ADMIN_PASSWORD` は Werkzeug の `generate_password_hash()` でハッシュ化した値を `init/01_login.sql` に記載する必要があります。

---

## データベースのセットアップ

```bash
# マイグレーションの適用
flask db upgrade
```

PostgreSQL コンテナの初回起動時に `init/` ディレクトリ内の SQL ファイルが自動実行され、管理者ユーザーが作成されます。

---

## 起動方法

```bash
# 開発サーバーの起動
python app.py
```

ブラウザで `http://localhost:5000` にアクセスしてください。

ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` から行います。

---

## 使い方

### 記事の投稿

1. ログイン後、「新規投稿」から投稿画面へ移動
2. タイトル・本文（Markdown）・ジャンル・ハッシュタグ・画像を入力
3. 公開 / 非公開を切り替えて「投稿する」をクリック

### Markdown 記法

| 記法 | 説明 |
|---|---|
| `## 見出し` | 大見出し（目次に表示） |
| `### 見出し` | 中見出し（目次に表示） |
| `[toc]` | 目次の挿入位置を指定（省略時は本文冒頭に自動挿入） |
| `[img1]` `[img2]` … | アップロード画像の埋め込み位置を指定 |
| `**テキスト**` | 太字 |

### ハッシュタグの入力

スペース・カンマ・読点で区切って複数入力できます。`#` は付けても省略しても構いません。

```
例: #Flask Python ブログ開発
```

---

## セキュリティについて

本アプリでは以下のセキュリティ対策を実施しています。

- **CSRF 保護**: Flask-WTF による全フォームへの CSRF トークン付与
- **秘密 URL**: ログインページを推測困難なパスに設定
- **パスワードハッシュ**: Werkzeug の `check_password_hash` による検証
- **ファイルアップロード検証**:
  - 拡張子ホワイトリスト（PNG / JPG / GIF / WebP のみ）
  - `filetype` ライブラリによるマジックナンバー検証（拡張子偽装の防止）
  - ファイルサイズ上限 30MB
  - `secure_filename` によるファイル名サニタイズ
- **本番環境チェック**: `SECRET_KEY` が未設定の場合、本番環境では起動を拒否