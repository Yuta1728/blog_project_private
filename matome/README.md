# MIT Blog

Flask 製のパーソナルブログアプリケーション。マークダウン記事の投稿・編集・削除、ジャンル／ハッシュタグによる絞り込み、画像アップロード、Google Maps / YouTube の埋め込みなどに対応しています。

---

## 目次

- [MIT Blog](#mit-blog)
  - [目次](#目次)
  - [機能一覧](#機能一覧)
    - [公開ページ（誰でも閲覧可）](#公開ページ誰でも閲覧可)
    - [管理者ページ（ログイン必須）](#管理者ページログイン必須)
    - [エディタ機能（マークダウンツールバー）](#エディタ機能マークダウンツールバー)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ](#セットアップ)
    - [1. リポジトリのクローン](#1-リポジトリのクローン)
    - [2. Python 仮想環境の作成と依存関係のインストール](#2-python-仮想環境の作成と依存関係のインストール)
    - [3. `.env` ファイルの作成](#3-env-ファイルの作成)
    - [4. Docker で PostgreSQL を起動](#4-docker-で-postgresql-を起動)
  - [環境変数](#環境変数)
  - [データベースのマイグレーション](#データベースのマイグレーション)
  - [初回管理者ユーザーの作成](#初回管理者ユーザーの作成)
  - [開発サーバーの起動](#開発サーバーの起動)
  - [本番環境へのデプロイ](#本番環境へのデプロイ)
  - [セキュリティ設計](#セキュリティ設計)
  - [マークダウン記法ガイド](#マークダウン記法ガイド)

---

## 機能一覧

### 公開ページ（誰でも閲覧可）

| 機能 | 説明 |
|------|------|
| 記事一覧 | 公開記事を新着順に表示。4件ずつ「もっと見る」で追加表示 |
| キーワード検索 | タイトル・ハッシュタグをまたいで全文検索 |
| ジャンル絞り込み | カテゴリ別の記事フィルタリング |
| ハッシュタグ絞り込み | ジャンル内でさらにタグで絞り込み |
| 記事詳細 | マークダウン→HTML変換・目次・画像・地図・YouTube埋め込み |
| 関連記事 | ジャンル×タグの優先度付きで最大4件を自動表示 |
| ジャンル一覧 | カテゴリ別の階層メニュー |
| 自己紹介 / 使い方 | 静的情報ページ |

### 管理者ページ（ログイン必須）

| 機能 | 説明 |
|------|------|
| 記事投稿 | マークダウンエディタ・ツールバー・プレビュー付き |
| 記事編集 | 既存記事の全フィールドを更新 |
| 記事削除 | 確認ダイアログ付き。関連画像・孤立タグも自動削除 |
| 画像アップロード | 複数枚・キャプション付きに対応（最大30MB） |
| デフォルトサムネイル | 画像なし記事向けに11種類のプリセットを用意 |
| ハッシュタグ管理 | 記事削除・編集時に孤立タグを自動クリーンアップ |
| 公開／非公開設定 | 1クリックで切り替えるトグルボタン |
| ニックネーム変更 | マイページから表示名を随時変更 |

### エディタ機能（マークダウンツールバー）

- H2 / H3 見出し挿入
- 太字ラップ
- 目次 `[toc]` 挿入
- 箇条書きリスト（選択範囲一括変換対応）
- 地図挿入モーダル（`[map:場所名]` タグ）
- YouTube 動画挿入モーダル（`[youtube:URL]` タグ）
- アップロード画像の `[imgN]` ボタン（動的生成）
- スクロール追従（sticky）ツールバー

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| バックエンド | Python 3.10 / Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| DB | PostgreSQL 18（Docker）/ 本番は環境変数で切替 |
| マイグレーション | Flask-Migrate / Alembic |
| 認証 | Flask-Login |
| セキュリティ | Flask-WTF (CSRF) / Werkzeug / filetype |
| マークダウン | Python-Markdown（toc・nl2br 拡張）|
| フロントエンド | Vanilla JS / CSS（フレームワーク不使用）|
| その他 | python-dotenv / pytz / psycopg3 |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリケーションファクトリ
├── config.py               # 環境変数の読み込み
├── constants.py            # デフォルトジャンル一覧
├── extensions.py           # db / login_manager / migrate インスタンス
├── models.py               # User / Post / Hashtag モデル
├── requirements.txt
├── docker-compose.yml      # ローカル開発用 PostgreSQL
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 公開ページ
│   └── admin.py            # 管理者ページ
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル
└── migrations/             # Alembic マイグレーションファイル
```

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. Python 仮想環境の作成と依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. `.env` ファイルの作成

プロジェクトルートに `.env` を作成します（`.gitignore` 対象）。

```env
# PostgreSQL（docker-compose と合わせる）
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション署名キー（本番では必ずランダムな長い文字列に変更）
SECRET_KEY=your-very-secret-key

# 管理者情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=<Werkzeug でハッシュ化したパスワード>
ADMIN_LOGIN_PATH=your-secret-login-path   # 例: my-secret-login-abc123
```

`ADMIN_PASSWORD` のハッシュ値生成方法：

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

### 4. Docker で PostgreSQL を起動

```bash
docker-compose up -d
```

---

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `POSTGRES_USER` | ✅ | DB ユーザー名 |
| `POSTGRES_PASSWORD` | ✅ | DB パスワード |
| `POSTGRES_DB` | ✅ | DB 名 |
| `SECRET_KEY` | ✅ (本番) | Flask セッション署名キー |
| `ADMIN_USERNAME` | ✅ | 管理者ログイン名 |
| `ADMIN_PASSWORD` | ✅ | Werkzeug ハッシュ済みパスワード |
| `ADMIN_LOGIN_PATH` | ✅ | ログインページの秘匿パス |
| `DATABASE_URL` | 本番のみ | Heroku / Render などが自動設定する接続 URL |

---

## データベースのマイグレーション

```bash
# 初回（テーブル作成）
flask db upgrade

# モデル変更後の差分検出と適用
flask db migrate -m "変更内容のメモ"
flask db upgrade
```

---

## 初回管理者ユーザーの作成

Flask シェルで以下を実行します。

```python
from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import config

app = create_app()
with app.app_context():
    user = User(
        username=config.ADMIN_USERNAME,
        password=generate_password_hash("your_password"),
        nickname="あなたの表示名",
    )
    db.session.add(user)
    db.session.commit()
    print("管理者ユーザーを作成しました。")
```

---

## 開発サーバーの起動

```bash
python app.py
# または
flask run
```

デフォルトで `http://127.0.0.1:5000` でアクセスできます。

管理者ログインは `http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>` から行います。

---

## 本番環境へのデプロイ

Heroku / Render などの PaaS へのデプロイ時は以下の点を確認してください。

1. **環境変数の設定**：`DATABASE_URL`・`SECRET_KEY`・`ADMIN_*` を PaaS 側のダッシュボードで設定する
2. **`SECRET_KEY` は必ず強力なランダム文字列に変更する**（開発用の固定値をそのまま使用しない）
3. **`flask db upgrade` をデプロイ後に実行**してマイグレーションを適用する
4. **静的ファイルの配信**：本番では Nginx などのリバースプロキシ経由での配信を推奨

---

## セキュリティ設計

| 項目 | 対策 |
|------|------|
| CSRF | Flask-WTF による全フォームへのトークン強制 |
| 認証 | Flask-Login + Werkzeug パスワードハッシュ |
| ブルートフォース | 5回失敗で5分間ロックアウト（セッションベース） |
| ログイン URL | `.env` で秘匿化（Security through obscurity） |
| ファイルアップロード | 拡張子チェック → MIME タイプチェック（filetype）→ UUID リネーム |
| XSS | Jinja2 の自動エスケープ（`safe` フィルタは信頼できる出力にのみ使用） |
| Open Redirect | 削除後リダイレクト時に同一オリジン検証を実施 |
| パストラバーサル | `secure_filename()` でアップロードファイル名をサニタイズ |
| 容量制限 | リクエスト最大 30MB（`MAX_CONTENT_LENGTH`）|

---

## マークダウン記法ガイド

記事本文で使用できる特殊タグ：

```
[toc]               → 見出しから目次を自動生成

[img1]              → アップロード画像を1枚目の位置に挿入
[img2]              → 2枚目の位置に挿入（複数枚対応）

[map:東京タワー]    → Google Maps の埋め込み地図を挿入

[youtube:https://www.youtube.com/watch?v=xxxxx]
                    → YouTube 動画をファサード（サムネイル）付きで埋め込み
```

通常の Markdown 記法（見出し `##`、太字 `**text**`、コードブロック `` ``` `` など）はすべて使用できます。