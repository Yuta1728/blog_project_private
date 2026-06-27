# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリケーションです。
記事の投稿・編集・削除、ジャンル分類、ハッシュタグ管理、画像アップロードなどの機能を備えています。

---

## 📋 目次

- [機能一覧](#機能一覧)
- [技術スタック](#技術スタック)
- [ディレクトリ構成](#ディレクトリ構成)
- [セットアップ手順](#セットアップ手順)
- [環境変数の設定](#環境変数の設定)
- [データベースのマイグレーション](#データベースのマイグレーション)
- [記事の書き方](#記事の書き方)
- [セキュリティ設計](#セキュリティ設計)

---

## 機能一覧

### 一般公開ページ

- 記事一覧（最新順）・キーワード検索・ジャンル絞り込み・ハッシュタグ絞り込み
- 記事詳細表示（マークダウンレンダリング・目次自動生成）
- Google マップ埋め込み（`[map:場所名]` 記法）
- YouTube 動画埋め込み（`[youtube:URL]` 記法、ファサード付き）
- 関連記事の自動表示（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新 の優先順）
- ジャンル一覧ページ・自己紹介ページ・使い方ページ

### 管理者ページ（要ログイン）

- 記事の新規投稿・編集・削除
- 複数画像アップロード（各画像にキャプション設定可）
- デフォルトサムネイル選択（画像未アップロード時）
- ジャンル選択（プリセット / 新規作成）
- ハッシュタグ管理（付与・変更・孤立タグの自動削除）
- 公開 / 非公開の切り替え
- マークダウンツールバー（見出し・太字・目次・リスト・地図・YouTube の挿入ボタン）
- マイページ（投稿一覧・ニックネーム変更）

---

## 技術スタック

| 分類 | 採用技術 |
|------|----------|
| 言語 | Python 3.10 |
| Web フレームワーク | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| DB | PostgreSQL 18（Docker） |
| マイグレーション | Flask-Migrate / Alembic |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF |
| マークダウン変換 | Markdown（Python-Markdown） |
| ファイル検証 | filetype |
| タイムゾーン | pytz |
| インフラ | Docker Compose（ローカル開発）|

---

## ディレクトリ構成

```
.
├── app.py               # アプリケーションファクトリ（エントリーポイント）
├── config.py            # 環境変数の読み込み
├── constants.py         # デフォルトジャンル一覧などの定数
├── extensions.py        # Flask 拡張機能のインスタンス定義
├── models.py            # DB モデル（User / Post / Hashtag）
├── requirements.txt
├── docker-compose.yml   # PostgreSQL コンテナ定義
├── migrations/          # Alembic マイグレーションファイル
├── views/
│   ├── auth.py          # ログイン / ログアウト
│   ├── blog.py          # 一般公開ページ
│   └── admin.py         # 管理者専用ページ
├── templates/           # Jinja2 テンプレート
└── static/
    ├── css/             # スタイルシート
    └── img/
        ├── posts/       # アップロード画像の保存先
        └── thbnails/    # デフォルトサムネイル画像
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <リポジトリURL>
cd <プロジェクトディレクトリ>
```

### 2. 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env` ファイルを作成してください（[環境変数の設定](#環境変数の設定) を参照）。

### 4. PostgreSQL コンテナの起動

```bash
docker compose up -d
```

### 5. DB の初期化とマイグレーション

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flask シェルから初回ユーザーを登録します。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

user = User(
    username="あなたのユーザー名",
    password=generate_password_hash("あなたのパスワード"),
    nickname="表示名"
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

ブラウザで `http://localhost:5000` にアクセスして確認してください。

---

## 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定してください。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your_secret_key

# 管理者認証
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=hashed_password   # generate_password_hash() で生成した値
ADMIN_LOGIN_PATH=secret-login-path  # 推測されにくいランダムな文字列
```

> **`ADMIN_LOGIN_PATH`** はログインページの URL パスになります。  
> `/secret-login-path` のような推測されにくい文字列にすることで、ログインページの存在自体を隠蔽できます。

`.env` は `.gitignore` に含まれており、リポジトリにはコミットされません。

---

## データベースのマイグレーション

モデルを変更した際は以下の手順でマイグレーションを適用します。

```bash
# 差分を検出してマイグレーションファイルを生成
flask db migrate -m "変更内容の説明"

# DB に反映
flask db upgrade
```

ロールバックする場合：

```bash
flask db downgrade
```

---

## 記事の書き方

本文はマークダウン形式で記述します。以下の独自記法も利用できます。

### 画像の埋め込み

記事投稿時にアップロードした画像を本文中に配置します。

```
[img1]   # 1枚目の画像を表示
[img2]   # 2枚目の画像を表示
```

### 目次の自動生成

```
[toc]
```

`## 見出し` と `### 見出し` をもとに目次を自動生成します。

### Google マップの埋め込み

```
[map:東京スカイツリー]
[map:京都市伏見稲荷大社]
```

### YouTube 動画の埋め込み

```
[youtube:https://www.youtube.com/watch?v=XXXXXXXXXX]
[youtube:XXXXXXXXXX]  # 動画 ID だけでも可
```

サムネイルをクリックしたときに動画が再生されるファサード方式を採用しており、ページ読み込み時のパフォーマンスを損ないません。

---

## セキュリティ設計

### 認証・アクセス制御

- ログインページの URL を環境変数で隠蔽（`ADMIN_LOGIN_PATH`）
- 連続ログイン失敗時のセッションロックアウト（5回失敗で5分間ロック）
- パスワードは Werkzeug の `generate_password_hash` でハッシュ化して保存

### CSRF 対策

- Flask-WTF の `CSRFProtect` により、全フォームに CSRF トークン検証を強制

### ファイルアップロード

- 拡張子ホワイトリスト（PNG / JPG / GIF / WebP のみ）
- `filetype` ライブラリによる MIME タイプ検証（拡張子偽装の検出）
- `secure_filename()` によるファイル名のサニタイズ
- UUID によるファイル名のランダム化（URL 推測防止）
- アップロードサイズ上限: 30MB

### リダイレクト

- 記事削除後のリダイレクトで Open Redirect 対策（同一オリジンのみ許可）