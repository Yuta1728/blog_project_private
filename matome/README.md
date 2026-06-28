# MIT Blog

Flask と PostgreSQL で構築した個人ブログアプリケーションです。  
マークダウン記法による記事投稿・編集・画像アップロード・ハッシュタグ管理などを備えています。

---

## 目次

- [MIT Blog](#mit-blog)
  - [目次](#目次)
  - [機能概要](#機能概要)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ](#セットアップ)
    - [前提条件](#前提条件)
    - [手順](#手順)
  - [環境変数](#環境変数)
  - [マイグレーション](#マイグレーション)
  - [開発サーバーの起動](#開発サーバーの起動)
  - [主要機能の詳細](#主要機能の詳細)
    - [マークダウン記法](#マークダウン記法)
    - [画像アップロード](#画像アップロード)
    - [ジャンル・ハッシュタグ](#ジャンルハッシュタグ)
    - [関連記事](#関連記事)
  - [セキュリティ設計](#セキュリティ設計)
  - [ライセンス](#ライセンス)

---

## 機能概要

| カテゴリ | 機能 |
|---|---|
| 記事管理 | 新規投稿・編集・削除・公開/非公開切替 |
| 記事表示 | マークダウンレンダリング・目次自動生成 |
| メディア | 画像アップロード（複数枚）・キャプション付与・デフォルトサムネイル選択 |
| 埋め込み | Google Maps・YouTube 動画のワンタップ挿入 |
| 分類 | ジャンル・ハッシュタグによる絞り込み検索 |
| 関連記事 | ジャンル・タグの一致度に応じた自動表示 |
| 管理者 | ニックネーム変更・マイページ・ブルートフォース対策付きログイン |
| UI/UX | レスポンシブデザイン・スクロール連動ヘッダー・ドロワーメニュー |

---

## 技術スタック

- **バックエンド**: Python 3.10 / Flask 3.1
- **ORM**: Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0
- **DB**: PostgreSQL 18（Docker）
- **マイグレーション**: Flask-Migrate（Alembic）
- **認証**: Flask-Login
- **CSRF 保護**: Flask-WTF
- **マークダウン変換**: Markdown（`toc` / `nl2br` 拡張）
- **ファイル検証**: filetype（MIME タイプ判定）
- **フロントエンド**: Vanilla JS / CSS（フレームワーク不使用）

---

## ディレクトリ構成

```
.
├── app.py                  # Application Factory（エントリポイント）
├── config.py               # 環境変数の読み込み
├── constants.py            # デフォルトジャンル一覧
├── extensions.py           # db / login_manager / migrate インスタンス
├── models.py               # User / Post / Hashtag モデル定義
├── requirements.txt
├── docker-compose.yml
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # ページ別 CSS
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル画像
└── migrations/             # Alembic マイグレーションファイル
```

---

## セットアップ

### 前提条件

- Python 3.10+
- Docker / Docker Compose

### 手順

```bash
# 1. リポジトリをクローン
git clone <repo-url>
cd <repo-dir>

# 2. 仮想環境の作成・有効化
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 依存パッケージのインストール
pip install -r requirements.txt

# 4. 環境変数ファイルの作成（後述の「環境変数」を参照）
cp .env.example .env  # または手動で作成

# 5. PostgreSQL を Docker で起動
docker compose up -d

# 6. DB マイグレーション実行
flask db upgrade

# 7. 管理者ユーザーの初期登録（初回のみ）
flask shell
>>> from extensions import db
>>> from models import User
>>> from werkzeug.security import generate_password_hash
>>> u = User(username='your_admin_name', password=generate_password_hash('your_password'))
>>> db.session.add(u)
>>> db.session.commit()
```

---

## 環境変数

プロジェクトルートに `.env` ファイルを作成し、以下の値を設定してください。

```env
# PostgreSQL 接続情報（docker-compose.yml と合わせる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション署名キー（本番環境では必ずランダムな長い文字列に変更）
SECRET_KEY=your-secret-key

# 管理者認証情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=hashed_password_here  # generate_password_hash() で生成した値

# ログインページの秘密パス（例: abc123xyz → /abc123xyz でアクセス）
ADMIN_LOGIN_PATH=your-secret-login-path
```

> **Note**: `.env` は `.gitignore` に登録済みです。リポジトリにコミットしないでください。

---

## マイグレーション

```bash
# モデル変更後に差分ファイルを生成
flask db migrate -m "変更内容の説明"

# DB に適用
flask db upgrade

# ひとつ前の状態に戻す
flask db downgrade
```

---

## 開発サーバーの起動

```bash
# flask コマンドで起動（推奨）
flask run --debug

# または直接実行
python app.py
```

ブラウザで `http://127.0.0.1:5000` を開くとトップページが表示されます。  
管理者ログインは `http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>` からアクセスしてください。

---

## 主要機能の詳細

### マークダウン記法

本文はマークダウン形式で記述します。ツールバーから以下を挿入できます。

| 記法 / タグ | 説明 |
|---|---|
| `## 見出し` | H2 見出し |
| `### 見出し` | H3 見出し |
| `**太字**` | 太字テキスト |
| `[toc]` | 自動生成の目次を挿入 |
| `[img1]` | アップロード画像の埋め込み |
| `[map:場所名]` | Google Maps の埋め込み |
| `[youtube:URL]` | YouTube 動画の埋め込み |
| `● 箇条書き` | リスト挿入ボタンで自動付与 |

### 画像アップロード

- PNG / JPG / GIF / WebP に対応
- 最大 30MB（リクエスト全体）
- 複数ファイルを同時選択可能
- アップロード順に `[img1]`, `[img2]` … と対応
- 各画像にキャプションを設定すると `<figure>` タグで出力

### ジャンル・ハッシュタグ

- ジャンルはプリセット（`constants.py`）から選択、または自由入力で追加可能
- ハッシュタグはスペース・カンマ区切りで複数入力
- `#` の付け外しはどちらでも認識

### 関連記事

詳細ページ下部に最大 4 件の関連記事を自動表示します。  
表示優先度は「同ジャンル × 同タグ」→「同タグ」→「同ジャンル」→「最新記事」の順です。

---

## セキュリティ設計

| 対策 | 実装箇所 |
|---|---|
| CSRF トークン | Flask-WTF（全 POST フォームに適用） |
| パスワードハッシュ化 | Werkzeug `generate_password_hash` / `check_password_hash` |
| ログイン試行制限 | 5 回失敗で 5 分間ロックアウト（セッションベース） |
| ログイン URL 隠蔽 | `ADMIN_LOGIN_PATH` 環境変数で秘密のパスを設定 |
| ファイル検証（多層防御） | 拡張子チェック → MIME タイプ判定（`filetype`）→ ファイル名サニタイズ（`secure_filename`）→ UUID リネーム |
| Open Redirect 対策 | 削除後リダイレクト時にオリジン一致を検証 |
| ファイルサイズ制限 | `MAX_CONTENT_LENGTH = 30MB`（超過時 413 エラー） |
| 本番 SECRET_KEY 強制 | `DATABASE_URL` が設定された環境では未設定時に起動拒否 |

---

## ライセンス

このプロジェクトは個人学習・ポートフォリオ目的で作成されています。