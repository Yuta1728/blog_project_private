# MIT Blog

Flask 製のシンプルな個人ブログアプリケーションです。マークダウン記法での記事投稿、ジャンル・ハッシュタグ管理、画像アップロード、Google マップ埋め込み、YouTube 動画埋め込みなどの機能を備えています。

---

## 目次

1. [機能一覧](#機能一覧)
2. [技術スタック](#技術スタック)
3. [ディレクトリ構成](#ディレクトリ構成)
4. [セットアップ手順](#セットアップ手順)
5. [環境変数](#環境変数)
6. [データベースマイグレーション](#データベースマイグレーション)
7. [機能詳細](#機能詳細)
8. [セキュリティ設計](#セキュリティ設計)

---

## 機能一覧

### 一般ユーザー向け
- 記事一覧・詳細の閲覧
- ジャンル別絞り込み
- ハッシュタグ別絞り込み
- キーワード検索（タイトル・ハッシュタグ横断）
- 関連記事の表示（同ジャンル / 同タグ）
- 自己紹介・使い方ページの閲覧

### 管理者向け
- 管理者ログイン（秘密 URL + ブルートフォース対策）
- 記事の新規投稿・編集・削除
- マークダウン記法での本文入力（ツールバー付き）
- 複数画像のアップロード・プレビュー（各画像にキャプション設定可）
- デフォルトサムネイル画像の選択
- 公開 / 非公開の切り替え
- ジャンルの選択 / 新規作成
- ハッシュタグの設定（複数）
- Google マップの本文への埋め込み
- YouTube 動画の本文への埋め込み（ファサードパターンで遅延読み込み）
- ニックネームの変更
- マイページでの投稿一覧管理
- 目次（TOC）の自動生成

---

## 技術スタック

| カテゴリ | ライブラリ / ツール |
|---|---|
| Web フレームワーク | Flask 3.1.3 |
| ORM | Flask-SQLAlchemy 3.1.1 / SQLAlchemy 2.0.50 |
| DB マイグレーション | Flask-Migrate 4.1.0 / Alembic 1.16.5 |
| 認証 | Flask-Login 0.6.3 |
| CSRF 対策 | Flask-WTF 1.2.2 |
| パスワードハッシュ | Werkzeug 3.1.8 |
| マークダウン変換 | Markdown 3.9 |
| 画像 MIME チェック | filetype 1.2.0 |
| タイムゾーン | pytz 2026.2 |
| DB | PostgreSQL（Docker で起動） |
| DB ドライバ | psycopg 3.2.13 |

---

## ディレクトリ構成

```
.
├── app.py                  # Application Factory（エントリーポイント）
├── config.py               # 環境変数の読み込み
├── constants.py            # 定数（DEFAULT_GENRES など）
├── extensions.py           # 拡張機能インスタンス（db / login_manager / migrate）
├── models.py               # DB モデル（User / Post / Hashtag / post_hashtags）
├── requirements.txt
├── docker-compose.yml      # PostgreSQL コンテナ設定
├── migrations/             # Alembic マイグレーションファイル
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
└── static/
    ├── css/                # スタイルシート
    └── img/
        ├── posts/          # アップロードされた記事画像
        └── thbnails/       # デフォルトサムネイル画像
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <リポジトリURL>
cd <プロジェクトディレクトリ>
```

### 2. 仮想環境の作成と依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数ファイルの作成

プロジェクトルートに `.env` ファイルを作成してください（`.gitignore` に追加済みなのでリポジトリには含まれません）。

```env
# PostgreSQL 接続情報
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション署名キー（本番環境は必ずランダムな文字列にすること）
SECRET_KEY=your-secret-key

# 管理者認証情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=<Werkzeug generate_password_hash() で生成したハッシュ値>
ADMIN_LOGIN_PATH=your-secret-login-path   # 例: secret-abc123

# ※本番環境では DATABASE_URL も設定する（Render / Heroku 等が自動設定）
```

> **管理者パスワードのハッシュ生成方法**
>
> ```python
> from werkzeug.security import generate_password_hash
> print(generate_password_hash("設定したいパスワード"))
> ```

### 4. Docker で PostgreSQL を起動

```bash
docker-compose up -d
```

### 5. データベースの初期化とマイグレーション

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flask シェルから管理者を 1 件作成します。

```python
flask shell
>>> from extensions import db
>>> from models import User
>>> from werkzeug.security import generate_password_hash
>>> import os
>>> user = User(
...     username=os.getenv("ADMIN_USERNAME"),
...     password=os.getenv("ADMIN_PASSWORD"),
...     nickname="MIT"
... )
>>> db.session.add(user)
>>> db.session.commit()
```

### 7. 開発サーバーの起動

```bash
python app.py
# または
flask run
```

ブラウザで `http://localhost:5000` を開くとトップページが表示されます。  
管理者ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` からアクセスしてください。

---

## 環境変数

| 変数名 | 説明 | 必須 |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL ユーザー名 | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL パスワード | ✅ |
| `POSTGRES_DB` | データベース名 | ✅ |
| `SECRET_KEY` | Flask セッション署名キー | 本番のみ必須 |
| `ADMIN_USERNAME` | 管理者ユーザー名 | ✅ |
| `ADMIN_PASSWORD` | 管理者パスワード（Werkzeug ハッシュ済み） | ✅ |
| `ADMIN_LOGIN_PATH` | ログインページの URL パス（推測されにくい文字列を推奨） | ✅ |
| `DATABASE_URL` | 本番 DB の接続 URL（Render / Heroku 等が自動設定） | 本番のみ |

---

## データベースマイグレーション

モデルを変更したときの手順です。

```bash
# 差分を検出してマイグレーションファイルを生成
flask db migrate -m "変更内容の説明"

# DB に変更を適用
flask db upgrade

# 1つ前の状態に戻す
flask db downgrade
```

マイグレーション履歴（`migrations/versions/`）：

| リビジョン | 内容 |
|---|---|
| `f8bd789a6d74` | 初期リビジョン（`is_published` NOT NULL 化） |
| `42dc0996903d` | `post.default_thumb` カラム追加 |
| `add_hashtag_tables` | `hashtag` / `post_hashtags` テーブル追加 |
| `add_img_captions` | `post.img_captions` カラム追加 |
| `make_updated_at_nullable` | `post.updated_at` を nullable に変更 |

---

## 機能詳細

### マークダウン記法

本文はマークダウン形式で記述します。ツールバーからボタン操作でタグを挿入することもできます。

| 記法 | 説明 |
|---|---|
| `## 見出し` | H2 見出し |
| `### 見出し` | H3 見出し |
| `**太字**` | 太字 |
| `[toc]` | その位置に目次を挿入 |
| `[img1]` | アップロードした 1 枚目の画像を挿入 |
| `[map:場所名]` | Google マップを埋め込み |
| `[youtube:URL]` | YouTube 動画を埋め込み（クリックで再生） |

### 画像アップロード

- 対応形式：PNG / JPG / JPEG / GIF / WebP
- 最大ファイルサイズ：合計 30MB
- 複数枚同時アップロード可（`[img1]`, `[img2]` … で本文中に配置）
- 各画像にキャプション（説明文）を設定可能
- 画像をアップロードしない場合はデフォルトサムネイル（11 種類）から選択可能

### ハッシュタグ

- スペース・カンマ・読点で区切って複数入力可
- `#` は付けても省略しても OK（例：`#Flask Python, ブログ`）
- ジャンル選択中はハッシュタグフィルターバーが表示され、タグで絞り込める
- 使用記事がなくなったタグは自動的に DB から削除（孤立タグの自動クリーンアップ）

---

## セキュリティ設計

| 対策 | 実装箇所 |
|---|---|
| CSRF トークン | Flask-WTF による全フォームへの自動適用 |
| パスワードハッシュ | Werkzeug `generate_password_hash` / `check_password_hash` |
| ブルートフォース対策 | 5 回失敗で 5 分間ロックアウト（セッションベース） |
| ログイン URL 隠蔽 | `ADMIN_LOGIN_PATH` で推測困難な URL を設定 |
| ファイル検証（2 層） | 拡張子チェック + filetype による MIME タイプ検証 |
| ファイル名サニタイズ | `werkzeug.utils.secure_filename` + UUID でランダム化 |
| アップロードサイズ制限 | `MAX_CONTENT_LENGTH = 30MB` |
| Open Redirect 対策 | 削除後リダイレクト時に同一オリジン検証 |
| 本番 SECRET_KEY 強制 | `DATABASE_URL` または `FLASK_ENV=production` が設定されている場合、未設定なら起動拒否 |