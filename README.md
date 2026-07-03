# MIT Blog

Flask + PostgreSQL で構築された個人ブログアプリケーションです。
Markdown形式での記事執筆、ジャンル・ハッシュタグ管理、画像アップロード、地図・YouTube埋め込みなど、ブログ運営に必要な機能をひと通り備えています。

## 主な機能

### 記事管理
- Markdown形式での記事執筆（見出し・太字・箇条書き・目次[toc]に対応）
- 複数画像のアップロードとキャプション設定（`[img1]`, `[img2]`のようなタグで本文中の任意の位置に挿入可能）
- 画像未アップロード時に選べるデフォルトサムネイル（11種類）
- 記事ごとの公開／非公開設定
- 本文中へのGoogleマップ埋め込み（`[map:場所名]`）
- 本文中へのYouTube動画埋め込み（`[youtube:URL]`、サムネイルクリックで再生するファサード形式）

### 分類・検索
- ジャンル分類（デフォルトジャンル + ユーザー独自ジャンルの追加が可能）
- ハッシュタグ機能（複数タグ付け、タグ単位での絞り込み）
- トップページの検索エリアから「ジャンル×キーワード」を同時に指定して検索可能
- ジャンル×ハッシュタグの組み合わせ絞り込み
- 記事詳細ページのジャンルバッジ／ハッシュタグバッジをクリックすると、そのままジャンル・タグで絞り込んだ一覧へ遷移
- 関連記事の自動表示（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新記事、の優先順位で選出）

### 記事一覧の表示
- トップページはページ番号方式のページ送り（1ページ5件表示、下部の「‹ 1 2 3 ›」で切り替え）。ページ送り時は一覧の先頭へ自動スクロールする
- マイページは「もっと見る／表示を減らす」ボタンによる追加表示方式（学習用サンプルとして両方式を実装・維持）

### 管理者機能
- 推測されにくい隠しURLでのログイン（`.env`で任意のパスを設定）
- ブルートフォース攻撃対策（5回失敗で5分間ロックアウト）
- マイページ（投稿一覧、ニックネーム変更、使用ジャンル一覧）
- 記事の新規作成・編集・削除

### UI/UX
- レスポンシブ対応（PC／スマホ）
- `position: fixed` による常時表示のヘッダー（スクロールバウンド時も背景が露出しない）。下スクロールでスライドアウト、上スクロールで再表示
- サイト統計（総投稿数・ハッシュタグ数・最終更新日）の表示

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| バックエンド | Flask 3.1 |
| ORM | Flask-SQLAlchemy / SQLAlchemy 2.0 |
| DB | PostgreSQL 18 |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム／CSRF対策 | Flask-WTF |
| Markdown変換 | Python-Markdown（toc, nl2br拡張） |
| 画像検証 | filetype（MIMEタイプ判定） |
| インフラ | Docker Compose（PostgreSQLコンテナ） |

## ディレクトリ構成

```
.
├── app.py                 # アプリケーションファクトリ（エントリーポイント）
├── config.py               # 環境変数の読み込み
├── constants.py             # デフォルトジャンル一覧などの定数
├── extensions.py             # Flask拡張機能（db, login_manager, migrate）の初期化
├── models.py               # DBモデル（User, Post, Hashtag）
├── docker-compose.yml         # PostgreSQLコンテナ定義
├── migrations/              # Alembicマイグレーションファイル
├── static/
│   ├── css/                # ページ・機能別スタイルシート（ファイル冒頭に対象ページを明記）
│   │   ├── base.css        # 全ページ共通：固定ヘッダー・スマホ用ドロワー
│   │   ├── auth.css        # ログインページ
│   │   ├── index.css       # トップページ：記事カード・ページ送り
│   │   ├── detail.css      # 記事詳細ページ
│   │   ├── create_update.css # 投稿作成・編集ページ
│   │   ├── genre.css       # ジャンル一覧ページ
│   │   ├── hashtag.css     # ハッシュタグ関連UI（複数ページ共通）
│   │   ├── mypage.css      # マイページ
│   │   ├── load_more.css   # マイページの「もっと見る」機能
│   │   └── top_sections.css # hero/統計/検索エリア/about・howto共通レイアウト
│   └── img/
│       ├── posts/          # アップロードされた記事画像
│       └── thbnails/        # デフォルトサムネイル画像
├── templates/               # Jinja2テンプレート
└── views/
    ├── auth.py             # ログイン・ログアウト
    ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル）
    └── admin.py             # 管理者専用ページ（投稿・編集・削除・マイページ）
```

## セットアップ

### 1. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>
python -m venv venv
source venv/bin/activate   # Windowsの場合: venv\Scripts\activate
pip install -r requirements.txt
```

対応Pythonバージョン: `3.10.11`（`.python-version`参照）

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下を設定してください。

```env
# PostgreSQL接続情報（docker-compose.ymlと一致させる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# 管理者認証情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_hashed_password   # werkzeug.security.generate_password_hash() でハッシュ化した値
ADMIN_LOGIN_PATH=your-secret-login-path   # ログインページのURLパス（推測されにくい文字列を推奨）

# 本番環境のみ必須（開発環境では未設定でも動作します）
SECRET_KEY=your_secret_key
DATABASE_URL=postgresql+psycopg://...
```

### 3. データベースの起動

```bash
docker-compose up -d
```

PostgreSQLコンテナがホストの `55432` ポートで起動します。

### 4. マイグレーションの適用

```bash
flask db upgrade
```

### 5. 管理者ユーザーの作成

初回のみ、Flaskシェルなどから管理者ユーザーをDBに登録してください。

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
    password=generate_password_hash("設定したい平文パスワード"),
)
db.session.add(user)
db.session.commit()
```

### 6. アプリケーションの起動

```bash
python app.py
```

`http://localhost:5000` でアクセスできます。管理者ログインは `.env` で設定した `ADMIN_LOGIN_PATH` のURL（例: `http://localhost:5000/your-secret-login-path`）からアクセスしてください。

## セキュリティ上の工夫

- **CSRF対策**: Flask-WTFの`CSRFProtect`を全フォームに適用
- **ファイルアップロード検証**: 拡張子チェック → MIMEタイプ判定（`filetype`ライブラリでファイルの中身を確認）→ ファイル名のサニタイズ（`secure_filename`）→ UUIDによるファイル名のランダム化、の多層防御
- **アップロードサイズ制限**: リクエスト全体で30MBを上限に設定
- **ログインページの隠蔽**: URLパスを環境変数化し、既定のパスを推測されにくくする
- **ブルートフォース対策**: セッションベースでログイン失敗回数を記録し、一定回数超過で一時ロックアウト
- **Open Redirect対策**: 記事削除後のリダイレクト先が同一オリジンかどうかを検証
- **パスワードのハッシュ化**: `werkzeug.security`によるハッシュ化のみを保存し、平文比較は行わない

## ライセンス

このプロジェクトのライセンスについては、リポジトリ管理者にご確認ください。