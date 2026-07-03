# MIT Blog

Flask + PostgreSQL で構築された個人ブログアプリケーションです。
マークダウン記法での記事執筆、ジャンル・ハッシュタグによる分類、画像アップロード、Googleマップ/YouTube動画の埋め込みなど、個人ブログ運用に必要な機能を一通り備えています。

## 主な機能

### 記事管理
- マークダウン形式での記事執筆（見出し・太字・箇条書き・目次 `[toc]` に対応）
- 本文中に `[img1]` `[img2]` ... と書くだけで任意の位置に画像を挿入
- `[map:場所名]` でGoogleマップを、`[youtube:URL]` でYouTube動画（クリックで再生するファサード方式）を埋め込み
- 画像ごとにキャプションを設定可能
- 画像未アップロード時に使えるプリセットのデフォルトサムネイル（11種類）
- 公開 / 非公開の切り替え
- ジャンル分類（プリセットジャンル + 自由入力）
- ハッシュタグ機能（複数タグ付与、タグからの絞り込み）

### 一覧・閲覧
- トップページでの記事一覧表示（もっと見る／表示を減らすボタンによる段階表示）
- ジャンル別・ハッシュタグ別の絞り込み
- キーワード検索（タイトル・ハッシュタグを横断）
- 記事詳細ページでの自動目次生成
- ジャンル・ハッシュタグに基づく関連記事のレコメンド（4段階のフォールバックロジック）
- 投稿数・ハッシュタグ数・最終更新日の統計表示

### 管理者機能
- マイページ（自分の投稿一覧、ニックネーム変更）
- 記事の新規作成・編集・削除

### セキュリティ
- CSRF保護（Flask-WTF）
- ログインURLを環境変数で秘匿化（Security through obscurity）
- ログイン試行のレート制限（5回失敗で5分間ロックアウト）
- パスワードはハッシュ化して保存（平文比較を行わない）
- 画像アップロードの多層検証（拡張子チェック → MIMEタイプ実体チェック → ファイル名サニタイズ → UUIDによるファイル名ランダム化）
- アップロード合計サイズ制限（30MB）
- 記事削除後リダイレクトのOpen Redirect対策

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| フレームワーク | Flask 3.1 |
| ORM / マイグレーション | Flask-SQLAlchemy, Flask-Migrate (Alembic) |
| 認証 | Flask-Login |
| フォーム / CSRF | Flask-WTF |
| データベース | PostgreSQL 18 (Docker) |
| DBドライバ | psycopg 3 |
| マークダウン変換 | Markdown (toc, nl2br 拡張) |
| 画像検証 | filetype |
| フロントエンド | Jinja2テンプレート + Vanilla JS + CSS（フレームワーク非依存） |

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ（create_app）
├── config.py                # 環境変数の読み込み
├── constants.py              # デフォルトジャンル一覧などの定数
├── extensions.py             # db / login_manager / migrate のインスタンス
├── models.py                 # User, Post, Hashtag モデル定義
├── docker-compose.yml         # PostgreSQL コンテナ定義
├── migrations/               # Alembic マイグレーションファイル
├── views/
│   ├── auth.py              # ログイン・ログアウト
│   ├── blog.py              # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py             # 管理者専用ページ（投稿・編集・削除・マイページ）
├── templates/                # Jinja2 テンプレート
└── static/
    ├── css/
    └── img/
        ├── posts/           # アップロードされた記事画像
        └── thbnails/        # プリセットのデフォルトサムネイル
```

## セットアップ

### 前提条件
- Python 3.10.11（`.python-version` 参照）
- Docker / Docker Compose（PostgreSQLコンテナ用）

### 1. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定してください。

```env
# PostgreSQL 接続情報（docker-compose.yml と対応）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# 管理者認証情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_hashed_password   # werkzeug.security.generate_password_hash() で生成した値
ADMIN_LOGIN_PATH=your-secret-login-path  # 推測されにくいランダムな文字列を推奨

# セッション・CSRF署名用（本番環境では必須）
SECRET_KEY=your_random_secret_key
```

管理者パスワードのハッシュ値は、以下のように生成できます。

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"
```

### 3. データベースの起動

```bash
docker compose up -d
```

PostgreSQL コンテナがホストの `55432` 番ポートで起動します（`docker-compose.yml` 参照）。

### 4. マイグレーションの適用

```bash
flask db upgrade
```

### 5. 管理者ユーザーの作成

初回のみ、Flaskシェルなどから管理者ユーザーをDBに直接作成してください。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import config

user = User(
    username=config.ADMIN_USERNAME,
    password=generate_password_hash("your_password"),
    nickname="表示したい名前"
)
db.session.add(user)
db.session.commit()
```

### 6. アプリケーションの起動

```bash
python app.py
```

または

```bash
flask run
```

`http://localhost:5000` でアプリケーションにアクセスできます。
管理者ログインページは `http://localhost:5000/<ADMIN_LOGIN_PATH>` です。

## 主なルート一覧

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/` | 記事一覧（検索・ジャンル・ハッシュタグ絞り込み対応） |
| GET | `/about` | 管理者自己紹介ページ |
| GET | `/howto` | 使い方ガイド |
| GET | `/genre` | ジャンル一覧 |
| GET | `/<id>/detail` | 記事詳細 |
| GET/POST | `/<ADMIN_LOGIN_PATH>` | 管理者ログイン |
| GET | `/logout` | ログアウト |
| GET/POST | `/create` | 記事新規作成（要ログイン） |
| GET/POST | `/<id>/update` | 記事編集（要ログイン・投稿者本人のみ） |
| POST | `/<id>/delete` | 記事削除（要ログイン・投稿者本人のみ） |
| GET/POST | `/mypage` | マイページ（要ログイン） |

## データベース設計（概要）

- **User**: 管理者情報（`username`, `password`, `nickname`）
- **Post**: 記事本体（タイトル・本文・ジャンル・公開設定・画像情報・作成/更新日時など）
- **Hashtag**: ハッシュタグ（`name` を一意制約付きで管理）
- **post_hashtags**: Post と Hashtag の多対多を表す中間テーブル

詳細は `models.py` および `migrations/versions/` 以下のマイグレーション履歴を参照してください。

## ライセンス

このプロジェクトのライセンスは未定義です。利用・改変時はリポジトリ管理者にご確認ください。