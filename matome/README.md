# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリケーションです。マークダウン記述、画像アップロード、ハッシュタグ管理、Google Maps 埋め込みなどの機能を備えています。

---

## 目次

- [MIT Blog](#mit-blog)
  - [目次](#目次)
  - [機能一覧](#機能一覧)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ](#セットアップ)
    - [1. リポジトリのクローン](#1-リポジトリのクローン)
    - [2. 仮想環境の作成と依存パッケージのインストール](#2-仮想環境の作成と依存パッケージのインストール)
    - [3. PostgreSQL コンテナの起動](#3-postgresql-コンテナの起動)
    - [4. `.env` ファイルの作成](#4-env-ファイルの作成)
    - [5. 管理者ユーザーの作成](#5-管理者ユーザーの作成)
  - [環境変数](#環境変数)
  - [データベースマイグレーション](#データベースマイグレーション)
  - [起動方法](#起動方法)
  - [記事作成の書き方](#記事作成の書き方)
    - [見出し](#見出し)
    - [目次の自動生成](#目次の自動生成)
    - [画像の挿入](#画像の挿入)
    - [地図の埋め込み](#地図の埋め込み)
    - [ハッシュタグ](#ハッシュタグ)
  - [セキュリティ設計](#セキュリティ設計)

---

## 機能一覧

**閲覧（一般）**
- 記事一覧表示（サムネイル付き）
- ジャンル・ハッシュタグ・キーワードによる絞り込み検索
- マークダウン形式の記事本文レンダリング
- 自動目次生成（`[toc]` マーカー）
- 画像キャプション表示（`<figure>` タグ）
- Google Maps 埋め込み（`[map:場所名]` マーカー）
- 統計情報表示（総投稿数・ハッシュタグ数・最終更新日）

**管理者**
- 記事の新規作成・編集・削除
- 公開 / 非公開の切り替え
- 複数画像アップロード（最大 30MB）
- デフォルトサムネイル選択（11 種類）
- ハッシュタグ管理（スペース・カンマ区切りで複数入力）
- ニックネーム変更
- マークダウンツールバー（H2/H3 見出し・太字・目次・地図・画像挿入ボタン）

---

## 技術スタック

| 分類 | 使用技術 |
|------|---------|
| フレームワーク | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| DB | PostgreSQL 18（Docker） |
| マイグレーション | Flask-Migrate / Alembic |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF |
| マークダウン変換 | Python-Markdown（toc・nl2br 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |
| テンプレートエンジン | Jinja2 |
| フロントエンド | バニラ JS・CSS（フレームワークなし） |
| Python バージョン | 3.10.11 |

---

## ディレクトリ構成

```
.
├── app.py               # アプリケーションファクトリ（エントリポイント）
├── config.py            # 環境変数の読み込み
├── constants.py         # デフォルトジャンル一覧などの定数
├── extensions.py        # db / login_manager / migrate インスタンス
├── models.py            # SQLAlchemy モデル（User / Post / Hashtag）
├── requirements.txt
├── docker-compose.yml   # PostgreSQL コンテナ定義
├── migrations/          # Alembic マイグレーションファイル
├── views/
│   ├── auth.py          # ログイン・ログアウト
│   ├── blog.py          # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py         # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/           # Jinja2 テンプレート
└── static/
    ├── css/
    └── img/
        ├── posts/       # アップロード画像の保存先
        └── thbnails/    # デフォルトサムネイル画像
```

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. PostgreSQL コンテナの起動

```bash
docker-compose up -d
```

### 4. `.env` ファイルの作成

プロジェクトルートに `.env` を作成します（[環境変数](#環境変数) を参照）。

### 5. 管理者ユーザーの作成

Flask シェルでパスワードをハッシュ化し、管理者ユーザーを登録します。

```bash
flask shell
```

```python
from werkzeug.security import generate_password_hash
from extensions import db
from models import User

user = User(
    username="<ADMIN_USERNAME>",
    password=generate_password_hash("<your-password>"),
    nickname="MIT"
)
db.session.add(user)
db.session.commit()
```

---

## 環境変数

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定してください。

```env
# PostgreSQL（docker-compose.yml と合わせる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション署名キー（本番環境では長いランダム文字列を設定）
SECRET_KEY=your-very-secret-key

# 管理者情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=hashed_password_here
ADMIN_LOGIN_PATH=secret-login-path  # ログインページの URL パス（推測されにくい文字列を推奨）
```

> **本番環境の注意**
> `DATABASE_URL` または `FLASK_ENV=production` が設定されている場合、`SECRET_KEY` が未設定だとアプリが起動しません。

---

## データベースマイグレーション

```bash
# 初回セットアップ
flask db upgrade

# モデル変更後に差分マイグレーションファイルを生成
flask db migrate -m "変更内容の説明"

# マイグレーションを DB に適用
flask db upgrade

# ロールバック
flask db downgrade
```

---

## 起動方法

**開発環境**

```bash
flask run
# または
python app.py
```

アプリは `http://127.0.0.1:5000` で起動します。

**ログイン URL**

`.env` の `ADMIN_LOGIN_PATH` で設定したパスにアクセスします。

```
http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>
```

---

## 記事作成の書き方

記事本文はマークダウン形式で記述します。このブログ独自のマーカーも使用できます。

### 見出し

```markdown
## H2 見出し
### H3 見出し
```

### 目次の自動生成

本文内に `[toc]` と記述すると、H2・H3 見出しから目次が自動生成されます。

```markdown
[toc]

## はじめに
## 本題
### 詳細
```

### 画像の挿入

画像をアップロードすると `[img1]`、`[img2]` … のマーカーが使えます。本文中の任意の位置に挿入できます。

```markdown
本文テキスト

[img1]

続きのテキスト

[img2]
```

### 地図の埋め込み

```markdown
[map:東京スカイツリー]
[map:京都市伏見稲荷大社]
```

Google Maps の iframe が自動的に埋め込まれます。

### ハッシュタグ

スペース・カンマ区切りで複数入力できます。`#` は付けても省略しても OK です。

```
#Flask Python ブログ開発, 技術
```

---

## セキュリティ設計

| 対策 | 実装内容 |
|------|---------|
| CSRF 対策 | Flask-WTF による全フォームへの CSRF トークン強制適用 |
| パスワード管理 | Werkzeug の `generate_password_hash` / `check_password_hash` でハッシュ化 |
| ブルートフォース対策 | 5 回連続失敗で 5 分間セッションロックアウト |
| ファイル検証（多層防御） | 拡張子チェック → MIME タイプ判定（`filetype`）→ ファイル名サニタイズ（`secure_filename`）→ UUID リネーム |
| ファイルサイズ制限 | 30MB を超えるリクエストは 413 エラー |
| Open Redirect 対策 | 削除後のリダイレクト時に referer のオリジンを検証 |
| ログインページ隠蔽 | URL パスを `.env` で設定（Security through obscurity） |
| 本番環境チェック | `SECRET_KEY` 未設定時にアプリ起動を拒否 |