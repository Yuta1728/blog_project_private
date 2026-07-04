# MIT Blog — 個人用ブログアプリ

Flask + PostgreSQL で構築した、単一管理者向けの個人ブログアプリケーションです。
マークダウンによる記事執筆、画像・Google マップ・YouTube の埋め込み、ジャンル×ハッシュタグによる柔軟な記事検索に対応しています。

## 主な機能

### 閲覧者向け

- **記事一覧・詳細表示**（マークダウン → HTML 変換、目次 `[toc]` 自動生成）
- **キーワード × ジャンル × ハッシュタグの組み合わせ検索**
  - ヘッダー検索バー／トップページ内検索エリアの 2 系統
  - ジャンル選択中は、そのジャンル内で使用中のタグによる絞り込みバーを表示
- **リッチな記事表現**
  - 本文中への画像埋め込み（`[img1]` 形式、キャプション対応）
  - Google マップ埋め込み（`[map:場所名]`）
  - YouTube 埋め込み（`[youtube:URL]`、サムネイルのファサード表示でクリック時のみ再生 iframe をロード）
- **関連記事の自動表示**（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新記事の 4 段階フォールバックで最大 4 件）
- **サイト統計**（総投稿数・ハッシュタグ数・最終更新日）
- **レスポンシブ対応**（スマホ用ドロワーナビ、スクロール連動の固定ヘッダー）

### 管理者向け

- **秘密の URL からのログイン**（ログインパスを環境変数で隠蔽）
- **ブルートフォース対策**（5 回連続失敗で 5 分間のセッションロックアウト）
- **記事の投稿・編集・削除**
  - マークダウンツールバー（見出し / 太字 / 目次 / リスト / 地図 / YouTube / 画像タグ挿入）
  - 複数画像アップロード（一括・1 枚ずつ追加、プレビュー、キャプション編集、個別削除）
  - 公開／非公開のトグル切り替え（非公開記事は管理者のみ閲覧可能）
  - デフォルトサムネイルの選択（画像なし記事用に 11 種類のプリセット）
- **ジャンル管理**（プリセット 26 種 + 自由な新規ジャンル作成）
- **ハッシュタグ管理**（スペース・カンマ区切りで複数入力、孤立タグの自動削除）
- **マイページ**（自分の投稿一覧、使用ジャンル一覧、ニックネーム変更）

## 技術スタック

| 分類 | 技術 |
| --- | --- |
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1 |
| ORM / マイグレーション | Flask-SQLAlchemy 3.1 (SQLAlchemy 2.0) / Flask-Migrate (Alembic) |
| 認証 | Flask-Login |
| CSRF 保護 | Flask-WTF (CSRFProtect) |
| データベース | PostgreSQL 18 (Docker) / psycopg 3 |
| マークダウン変換 | Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |
| フロントエンド | Jinja2 テンプレート + バニラ JS + 自作 CSS（Coastal Dawn テーマ） |

## ディレクトリ構成

```
.
├── app.py                 # Application Factory（アプリ生成・設定・Blueprint 登録）
├── config.py              # .env の読み込みと設定値の提供
├── constants.py           # デフォルトジャンル一覧などの定数
├── extensions.py          # db / login_manager / migrate インスタンス（循環インポート回避）
├── models.py              # ORM モデル（User / Post / Hashtag / post_hashtags）
├── docker-compose.yml     # PostgreSQL コンテナ定義
├── requirements.txt
├── migrations/            # Alembic マイグレーション
├── views/
│   ├── auth.py            # ログイン・ログアウト（秘密 URL、ロックアウト）
│   ├── blog.py            # 公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py           # 管理ページ（投稿・編集・削除・マイページ）
├── templates/             # Jinja2 テンプレート
└── static/
    ├── css/               # ページ別 CSS
    └── img/
        ├── posts/         # アップロード画像（UUID ファイル名）
        └── thbnails/      # デフォルトサムネイル
```

## データベース設計

| テーブル | 説明 |
| --- | --- |
| `user` | 管理者情報（username / ハッシュ化パスワード / nickname） |
| `post` | 記事（タイトル・本文・ジャンル・画像・キャプション・公開設定・日時） |
| `hashtag` | ハッシュタグ（name は一意） |
| `post_hashtags` | Post ↔ Hashtag の多対多中間テーブル |

- `Post.updated_at` は **nullable** で、一度も編集されていない記事は NULL（更新日時の誤表示を防止）
- `Post.hashtags` は `lazy='selectin'` により一覧表示時の N+1 問題を回避
- どの記事にも紐付かなくなったハッシュタグは、記事の編集・削除時に自動でクリーンアップ

## セットアップ

### 1. 前提

- Python 3.10.11
- Docker / Docker Compose

### 2. リポジトリの取得と依存インストール

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数（.env）の作成

プロジェクトルートに `.env` を作成します（`.gitignore` 済み）。

```dotenv
# PostgreSQL（docker-compose と共有）
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=blogdb

# Flask セッション・CSRF 署名用（本番では必ずランダムな値を設定）
SECRET_KEY=your-random-secret-key

# 管理者認証
ADMIN_USERNAME=your-admin-name
ADMIN_PASSWORD=<werkzeugでハッシュ化した値>   # ※下記参照
ADMIN_LOGIN_PATH=secret-login-abc123          # ログインページの秘密パス
```

`ADMIN_PASSWORD` はハッシュ化した値を保存します。生成例:

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('平文パスワード'))"
```

### 4. データベースの起動とマイグレーション

```bash
# PostgreSQL コンテナを起動（ホスト側ポート 55432）
docker compose up -d

# テーブルを作成
flask db upgrade
```

### 5. 管理者ユーザーの登録

Flask シェルから初回のみ登録します。

```bash
flask shell
```

```python
from extensions import db
from models import User
import os

user = User(
    username=os.getenv("ADMIN_USERNAME"),
    password=os.getenv("ADMIN_PASSWORD"),   # ハッシュ化済みの値
)
db.session.add(user)
db.session.commit()
```

### 6. 起動

```bash
python app.py
```

- トップページ: `http://localhost:5000/`
- 管理者ログイン: `http://localhost:5000/<ADMIN_LOGIN_PATH>`

## 記事本文で使える記法

| 記法 | 効果 |
| --- | --- |
| `## 見出し` / `### 見出し` | H2 / H3 見出し（目次の対象） |
| `**太字**` | 太字 |
| `[toc]` | その位置に目次を挿入（未記載の場合は先頭に自動表示） |
| `[img1]` `[img2]` … | アップロードした画像を順番に埋め込み |
| `[map:東京スカイツリー]` | Google マップの埋め込み |
| `[youtube:URL または動画ID]` | YouTube 動画の埋め込み（watch / youtu.be / shorts / embed 形式に対応） |

これらは投稿・編集画面のツールバーからワンクリックで挿入できます。

## セキュリティ対策

- **CSRF 保護**: Flask-WTF の CSRFProtect を全フォームに適用
- **パスワード**: Werkzeug によるハッシュ化保存・照合（平文比較なし）
- **ログイン保護**: 秘密 URL + 連続失敗時のロックアウト + 失敗理由を明かさないエラーメッセージ
- **ファイルアップロードの多層防御**
  1. 拡張子ホワイトリスト（png / jpg / jpeg / gif / webp）
  2. マジックナンバーによる MIME タイプ検証（拡張子偽装の検出）
  3. `secure_filename()` によるパストラバーサル対策
  4. UUID によるファイル名ランダム化
  5. リクエストサイズ 30MB 制限（DoS 対策）
- **Open Redirect 対策**: リダイレクト先の referer を同一オリジン検証
- **本番環境ガード**: 本番判定時に `SECRET_KEY` 未設定なら起動を拒否

## デプロイ（本番環境）

本番では PaaS（Render / Heroku など）が提供する `DATABASE_URL` を自動で使用します。以下の環境変数を設定してください。

| 変数 | 説明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 接続 URL（設定されると本番環境と判定） |
| `SECRET_KEY` | ランダムな秘密鍵（未設定だと起動エラー） |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_LOGIN_PATH` | 管理者認証情報 |

> **注意**: 本番では `debug=True` を使わず、Gunicorn などの WSGI サーバーでの起動を推奨します。
> 例: `gunicorn "app:create_app()"`

## ライセンス

個人利用を目的としたプロジェクトです。