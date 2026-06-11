# MY Blog

Flask + PostgreSQL で構築した個人向けブログアプリケーションです。Markdown 記述・画像埋め込み・ジャンル管理・公開/非公開設定などを備えています。

---

## 機能一覧

- **記事の投稿・編集・削除** — タイトル・本文・ジャンル・サムネイル画像（複数枚）を管理
- **Markdown 対応** — `##` 大見出し・`###` 中見出し・`**太字**` に対応。自動目次（TOC）生成機能あり
- **画像埋め込み** — 本文中に `[img1]` と記述することで任意の位置に画像を挿入
- **デフォルトサムネイル** — 画像をアップロードしない場合、11 種類のプリセット画像から選択可能
- **ジャンル管理** — 26 種類のデフォルトジャンル＋ユーザー独自ジャンルの作成に対応
- **公開/非公開設定** — 投稿ごとに全体公開・非公開をトグルボタンで切り替え
- **タイトル検索・ジャンル絞り込み** — トップページ・マイページ両方で対応（ヘッダー常設の検索バー付き）
- **マイページ** — 自分の投稿一覧・ジャンル一覧・ニックネーム変更
- **管理者専用ログイン** — 秘密の URL によるアクセス制限
- **レスポンシブデザイン** — PC・スマートフォン両対応（ハンバーガーメニュー付き）

---

## 技術スタック

| カテゴリ | 使用技術 |
| --- | --- |
| バックエンド | Python / Flask 3.1 |
| ORM・マイグレーション | Flask-SQLAlchemy 3.1 / Flask-Migrate 4.1 (Alembic) |
| 認証 | Flask-Login 0.6 |
| データベース | PostgreSQL（Docker コンテナ） |
| テンプレートエンジン | Jinja2 |
| Markdown | Python-Markdown 3.9（`toc`・`nl2br` 拡張） |
| フロントエンド | HTML / CSS（バニラ） |
| 環境変数管理 | python-dotenv |

---

## ディレクトリ構成

```
matome/
├── app.py                  # アプリケーションファクトリ（create_app）
├── config.py               # 環境変数の読み込み
├── extensions.py           # Flask 拡張機能の初期化（db / login_manager / migrate）
├── models.py               # DB モデル（User, Post）
├── requirements.txt        # 依存パッケージ一覧
├── docker-compose.yml      # PostgreSQL コンテナ設定
├── init/
│   ├── 01_login.sql        # user テーブル定義（参考用）
│   └── 02_post.sql         # post テーブル定義（参考用）
├── migrations/             # Alembic マイグレーションファイル群
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 記事一覧・詳細・ジャンル一覧（公開側）
│   └── admin.py            # 投稿・編集・削除・マイページ（認証必須）
├── templates/              # Jinja2 テンプレート
│   ├── base.html           # 共通レイアウト（ヘッダー・フラッシュメッセージ）
│   ├── index.html          # トップ（記事一覧）
│   ├── detail.html         # 記事詳細
│   ├── create.html         # 新規投稿フォーム
│   ├── update.html         # 記事編集フォーム
│   ├── mypage.html         # マイページ
│   ├── genre.html          # ジャンル一覧
│   └── login.html          # 管理者ログイン
└── static/
    ├── css/                # ページごとのスタイルシート
    └── img/                # アップロード画像・デフォルトサムネイル画像の保存先
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd matome
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定します。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your_secret_key

# 管理者設定
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password_hash   # Werkzeug でハッシュ化したもの
ADMIN_LOGIN_PATH=your_secret_login_path   # 例: my-secret-login
```

> **注意:** `ADMIN_PASSWORD` は平文ではなく、Werkzeug の `generate_password_hash()` で生成したハッシュ値を設定してください。

### 3. Docker で PostgreSQL を起動

```bash
docker-compose up -d
```

ポート `54321` でローカルに PostgreSQL が起動します。

### 4. Python 仮想環境の作成と依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. データベースのマイグレーション

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

Flask シェルで管理者アカウントを登録します。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

user = User(
    username='your_admin_username',
    password=generate_password_hash('your_password')
)
db.session.add(user)
db.session.commit()
```

### 7. アプリケーションの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスします。

---

## 使い方

### ログイン

`http://localhost:5000/<ADMIN_LOGIN_PATH>` にアクセスしてログインします。URL は `.env` の `ADMIN_LOGIN_PATH` で設定した値です。

### 記事の投稿

ヘッダーの「新規投稿」から記事を作成できます。

**Markdown 記法のサポート:**

| 記法 | 説明 |
| --- | --- |
| `## 見出し` | 大見出し（目次に自動追加） |
| `### 見出し` | 中見出し（目次に自動追加） |
| `**テキスト**` | 太字 |
| `[toc]` | 任意の位置に目次を挿入（未記入の場合は本文先頭に自動挿入） |
| `[img1]` | 1 枚目の添付画像を挿入 |
| `[img2]` | 2 枚目の添付画像を挿入 |

### サムネイル画像

画像をアップロードした場合は先頭の 1 枚が一覧のサムネイルになります。アップロードしない場合は、趣味・旅行・スポーツ・アニメ・ゲームなど 11 種類のプリセット画像から選択できます。いずれも設定しない場合はシステム共通のデフォルト画像が表示されます。

### ジャンル

投稿時に既存のジャンルから選択するか、新規ジャンルを作成できます。ヘッダーの「ジャンル一覧」からカテゴリ別（ライフスタイル・社会/経済・技術/勉強・スポーツ・娯楽・仕事）に記事を絞り込めます。

### 公開設定

投稿・編集フォームのトグルボタンで「全体公開 🔓」と「非公開 🔒」を切り替えられます。非公開の記事は管理者本人のみ閲覧できます。

---

## データモデル

### User

| カラム | 型 | 説明 |
| --- | --- | --- |
| id | Integer | 主キー |
| username | String(30) | ログインユーザー名（ユニーク） |
| password | String(200) | ハッシュ化パスワード |
| nickname | String(60) | 表示名（任意） |

### Post

| カラム | 型 | 説明 |
| --- | --- | --- |
| id | Integer | 主キー |
| title | TEXT | 記事タイトル |
| body | TEXT | 本文（Markdown） |
| genre | String(100) | ジャンル（デフォルト: 未分類） |
| created_at | DateTime | 投稿日時（Asia/Tokyo） |
| updated_at | DateTime | 更新日時（Asia/Tokyo） |
| user_id | Integer | 投稿者 ID（外部キー → user.id） |
| img_name | String(100) | 画像ファイル名（カンマ区切り、任意） |
| default_thumb | String(100) | プリセットサムネイル画像名（任意） |
| is_published | Boolean | 公開フラグ（デフォルト: True） |

---

## ライセンス

このプロジェクトは個人用途のブログアプリケーションです。