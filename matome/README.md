# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリケーションです。マークダウン記法による記事執筆、画像・地図・YouTube 動画の埋め込み、ジャンル／ハッシュタグによる絞り込みなどの機能を備えています。

---

## 目次

- [MIT Blog](#mit-blog)
  - [目次](#目次)
  - [機能一覧](#機能一覧)
    - [一般公開ページ](#一般公開ページ)
    - [管理者専用ページ（ログイン必須）](#管理者専用ページログイン必須)
  - [技術スタック](#技術スタック)
  - [プロジェクト構成](#プロジェクト構成)
  - [セットアップ](#セットアップ)
    - [前提条件](#前提条件)
    - [手順](#手順)
  - [環境変数](#環境変数)
  - [データベースのマイグレーション](#データベースのマイグレーション)
  - [起動方法](#起動方法)
  - [記事の書き方（マークダウン拡張記法）](#記事の書き方マークダウン拡張記法)
    - [目次の挿入](#目次の挿入)
    - [画像の埋め込み](#画像の埋め込み)
    - [地図の埋め込み](#地図の埋め込み)
    - [YouTube 動画の埋め込み](#youtube-動画の埋め込み)
  - [セキュリティ設計](#セキュリティ設計)

---

## 機能一覧

### 一般公開ページ
- 記事一覧（最新順）・ジャンル絞り込み・キーワード検索
- ハッシュタグによる絞り込み
- 記事詳細ページ（マークダウン表示・目次・画像・地図・YouTube 埋め込み）
- ジャンル一覧ページ
- 自己紹介ページ・使い方ページ
- ブログ統計（総投稿数・ハッシュタグ数・最終更新日）

### 管理者専用ページ（ログイン必須）
- 記事の新規投稿・編集・削除
- 公開 / 非公開の切り替え
- 画像のアップロード（複数枚対応、キャプション付き）
- デフォルトサムネイルの選択
- ハッシュタグの付与
- マークダウンツールバー（見出し・太字・目次・地図・YouTube）
- マイページ（投稿一覧・ニックネーム変更）

---

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| バックエンド | Python 3.10 / Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| データベース | PostgreSQL 18（Docker）|
| マイグレーション | Flask-Migrate / Alembic |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF（CSRF 保護）/ Werkzeug |
| マークダウン | Python-Markdown（toc・nl2br 拡張）|
| ファイル検証 | filetype |
| フロントエンド | Vanilla JS / CSS（レスポンシブ対応）|
| コンテナ | Docker / Docker Compose |

---

## プロジェクト構成

```
.
├── app.py              # Application Factory（エントリーポイント）
├── config.py           # 環境変数の読み込み
├── constants.py        # デフォルトジャンル定数
├── extensions.py       # db / login_manager / migrate のインスタンス
├── models.py           # ORM モデル（User, Post, Hashtag）
├── views/
│   ├── auth.py         # ログイン・ログアウト
│   ├── blog.py         # 一般公開ページ
│   └── admin.py        # 管理者専用ページ
├── templates/          # Jinja2 テンプレート
├── static/
│   ├── css/            # スタイルシート
│   └── img/
│       ├── posts/      # アップロード画像の保存先
│       └── thbnails/   # デフォルトサムネイル画像
├── migrations/         # Alembic マイグレーションファイル
├── docker-compose.yml
└── requirements.txt
```

---

## セットアップ

### 前提条件

- Python 3.10+
- Docker / Docker Compose

### 手順

**1. リポジトリをクローン**

```bash
git clone <repository-url>
cd <repository-directory>
```

**2. 仮想環境の作成と依存パッケージのインストール**

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. `.env` ファイルを作成**

プロジェクトルートに `.env` を作成し、後述の[環境変数](#環境変数)を設定します。

**4. PostgreSQL コンテナを起動**

```bash
docker compose up -d
```

**5. データベースのマイグレーション**

```bash
flask db upgrade
```

**6. 管理者ユーザーの作成**

Flask シェルで初回のみ実行します。

```python
flask shell

from extensions import db
from werkzeug.security import generate_password_hash
from models import User
import config

user = User(
    username=config.ADMIN_USERNAME,
    password=generate_password_hash(config.ADMIN_PASSWORD),
    nickname='あなたのニックネーム'
)
db.session.add(user)
db.session.commit()
```

---

## 環境変数

`.env` ファイルに以下を記載してください。`.gitignore` により Git 管理対象外になっています。

```env
# PostgreSQL 接続情報（docker-compose.yml と合わせる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# 管理者認証情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password   # Werkzeug でハッシュ化して DB に保存する

# ログインページの URL パス（推測されにくいランダム文字列を推奨）
ADMIN_LOGIN_PATH=your-secret-login-path

# セッション署名キー（本番環境では必須）
SECRET_KEY=your-very-secret-key

# 本番環境のデータベース URL（Heroku / Render などの PaaS が自動設定）
# DATABASE_URL=postgresql+psycopg://...
```

---

## データベースのマイグレーション

```bash
# マイグレーションファイルの生成
flask db migrate -m "変更内容の説明"

# マイグレーションの適用
flask db upgrade

# ひとつ前の状態に戻す
flask db downgrade
```

---

## 起動方法

**開発環境**

```bash
python app.py
# または
flask run
```

ブラウザで `http://localhost:5000` にアクセスしてください。

管理者ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` からアクセスします。

**本番環境**

`DATABASE_URL` と `SECRET_KEY` を環境変数に設定し、Gunicorn などの WSGI サーバーで起動してください。

```bash
gunicorn "app:create_app()"
```

---

## 記事の書き方（マークダウン拡張記法）

通常のマークダウン記法に加えて、以下の独自タグが使えます。

### 目次の挿入

```
[toc]
```

本文中の `##`（H2）・`###`（H3）見出しから目次を自動生成します。

### 画像の埋め込み

アップロードした画像を本文内の任意の位置に挿入できます。

```
[img1]    # 1枚目の画像
[img2]    # 2枚目の画像
```

### 地図の埋め込み

ツールバーの「🗺️ 地図」ボタン、または直接記法で Google Maps を埋め込めます。

```
[map:東京スカイツリー]
[map:京都市伏見稲荷大社]
```

### YouTube 動画の埋め込み

URL または動画 ID を指定します。クリックするまで読み込みを遅延させるため、ページの表示速度に影響しません。

```
[youtube:https://www.youtube.com/watch?v=VIDEO_ID]
[youtube:VIDEO_ID]
```

---

## セキュリティ設計

| 項目 | 対策 |
|---|---|
| CSRF 攻撃 | Flask-WTF によりすべての POST リクエストにトークン検証を強制 |
| 画像偽装 | 拡張子チェック（第1層）＋ filetype による MIME 判定（第2層）の多層防御 |
| パストラバーサル | `secure_filename()` でアップロードファイル名をサニタイズ |
| ファイル名推測 | UUID でアップロードファイル名をランダム化 |
| DoS（大容量ファイル） | 30MB の容量制限（`MAX_CONTENT_LENGTH`）|
| ブルートフォース | ログイン失敗 5 回でセッションロックアウト（5 分間）|
| ログイン URL の隠蔽 | `.env` で設定したランダムパスにのみログインページを設置 |
| Open Redirect | 削除後のリダイレクト先をオリジン一致チェックで検証 |
| 平文パスワード保存 | Werkzeug の `generate_password_hash` / `check_password_hash` を使用 |