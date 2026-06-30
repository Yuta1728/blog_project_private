# MIT Blog

Flask + PostgreSQL で構築された、個人運用を想定したブログアプリケーションです。
管理者（単一ユーザー）が記事を投稿・編集し、訪問者は記事の閲覧・検索・ジャンルやハッシュタグでの絞り込みができます。

## 主な機能

### 公開ページ
- 記事一覧（トップページ）／キーワード検索／ジャンル絞り込み／ハッシュタグ絞り込み
- 記事詳細ページ（マークダウン本文の表示、目次の自動生成）
- 関連記事の自動表示（同ジャンル＋同タグ → 同タグ → 同ジャンル → 最新記事の順で補完）
- 「もっと見る」によるページ内の段階的な記事読み込み
- 自己紹介ページ（/about）、使い方ページ（/howto）、ジャンル一覧ページ（/genre）

### 管理者専用ページ（ログイン必須）
- 新規投稿（/create）／編集（/update）／削除（/delete）
- マークダウンエディタ（見出し・太字・箇条書き・目次・地図・YouTube埋め込みのツールバー付き）
- 画像の複数アップロード、画像ごとのキャプション設定、本文中への `[img1]` 形式での挿入
- デフォルトサムネイル（画像未アップロード時のジャンル別アイコン）の選択
- ジャンルの選択またはユーザー独自ジャンルの新規作成
- ハッシュタグ入力（スペース・カンマ区切り、リアルタイムプレビュー）
- 記事の公開／非公開切り替え
- マイページ（投稿一覧、ニックネーム変更、使用ジャンル一覧）

### 本文中の独自記法
- `[toc]` … 目次を挿入
- `[img1]`, `[img2]`, ... … アップロードした画像を順番に挿入（キャプション対応）
- `[map:場所名]` … Google Maps の埋め込み
- `[youtube:URL]` … YouTube 動画のサムネイル表示＋クリック再生（ファサード方式）

### セキュリティ対策
- CSRF トークンによるフォーム保護（Flask-WTF）
- 画像アップロードの多層検証（拡張子チェック → MIME タイプ判定 → ファイル名サニタイズ → UUID によるファイル名ランダム化）
- アップロード合計サイズ制限（30MB）
- ログインページ URL の隠蔽（`.env` でパスを指定）
- ログイン試行回数制限によるブルートフォース対策（5回失敗で5分間ロック）
- 削除処理における Open Redirect 対策（リダイレクト先のオリジン検証）

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.x |
| ORM / マイグレーション | Flask-SQLAlchemy, Flask-Migrate (Alembic) |
| 認証 | Flask-Login |
| フォーム保護 | Flask-WTF (CSRF) |
| データベース | PostgreSQL（Docker Compose で起動） |
| マークダウン変換 | Markdown（toc, nl2br 拡張） |
| 画像検証 | filetype |
| テンプレートエンジン | Jinja2 |
| フロントエンド | 素の HTML / CSS / JavaScript（フレームワーク不使用） |

## ディレクトリ構成

```
.
├── app.py                 # アプリケーションファクトリ（create_app）
├── config.py               # .env から環境変数を読み込み
├── constants.py             # デフォルトジャンル一覧
├── extensions.py            # db / login_manager / migrate のインスタンス定義
├── models.py                # User, Post, Hashtag モデル
├── docker-compose.yml        # PostgreSQL コンテナ定義
├── migrations/               # Alembic マイグレーションファイル
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一般公開ページ
│   └── admin.py             # 管理者専用ページ
├── templates/               # Jinja2 テンプレート
└── static/
    ├── css/                # 画面別スタイルシート
    └── img/                # アップロード画像・デフォルトサムネイル
```

## セットアップ

### 1. 必要環境
- Python 3.10.11
- Docker / Docker Compose（PostgreSQL 用）

### 2. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>
python -m venv venv
source venv/bin/activate  # Windows の場合は venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の値を設定してください。

```env
# PostgreSQL（docker-compose.yml と一致させる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# 管理者アカウント
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ハッシュ化済みパスワード
ADMIN_LOGIN_PATH=推測されにくいログインパス（例: secret-login-xxxx）

# Flask
SECRET_KEY=任意のランダム文字列（本番環境では必須）
```

`ADMIN_PASSWORD` は平文ではなく、Werkzeug の `generate_password_hash()` で生成したハッシュ値を使用します。

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('設定したいパスワード'))"
```

### 4. データベースの起動

```bash
docker compose up -d
```

`docker-compose.yml` ではホストの `55432` 番ポートにマッピングされています。

### 5. マイグレーションの適用

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

初回のみ、`User` テーブルに管理者レコードを手動で投入する必要があります（`username` は `.env` の `ADMIN_USERNAME`、`password` は同じくハッシュ化済みの値）。Flask シェルなどから登録してください。

```bash
flask shell
```
```python
from extensions import db
from models import User
import config

user = User(username=config.ADMIN_USERNAME, password=config.ADMIN_PASSWORD)
db.session.add(user)
db.session.commit()
```

### 7. アプリケーションの起動

```bash
python app.py
```

`http://localhost:5000` でトップページにアクセスできます。管理者ログインは `.env` で設定した `ADMIN_LOGIN_PATH` のパス（例: `http://localhost:5000/secret-login-xxxx`）からアクセスしてください。

## データベーススキーマ概要

- **User** … 管理者情報（username, password ハッシュ, nickname）
- **Post** … 記事本体（title, body, genre, 画像情報, 公開設定, 投稿・更新日時 など）
- **Hashtag** … ハッシュタグ名（一意）
- **post_hashtags** … Post と Hashtag の多対多中間テーブル

## マイグレーションの運用

モデルを変更した場合は、以下のコマンドで差分マイグレーションを生成・適用します。

```bash
flask db migrate -m "変更内容の説明"
flask db upgrade
```

## ライセンス

このリポジトリ固有のライセンス表記は設定されていません。利用条件についてはリポジトリ管理者にご確認ください。