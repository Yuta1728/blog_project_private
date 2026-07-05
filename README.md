# MIT Blog — Flask 個人用ブログアプリ

Flask + PostgreSQL で構築した、単一管理者運用の個人用ブログアプリケーションです。
マークダウンによる記事執筆、画像・Google マップ・YouTube の埋め込み、ジャンル×ハッシュタグによる絞り込み検索など、個人ブログに必要な機能を一通り備えています。

## 主な機能

### 閲覧者向け（一般公開ページ）

- **記事一覧（トップページ）**
  - サムネイル付き記事カード表示（1ページ5件のページ番号式ページ送り）
  - ジャンル × キーワードの複合検索（インページ検索エリア／ヘッダー検索バー）
  - ジャンル選択時はハッシュタグによるさらなる絞り込みが可能
  - 総投稿数・ハッシュタグ数・最終更新日のサイト統計表示
- **記事詳細ページ**
  - マークダウン本文のHTML表示（`[toc]` による目次の自動生成対応）
  - 画像＋キャプション、Google マップ（`[map:場所名]`）、YouTube（`[youtube:URL]`）の埋め込み
  - YouTube はサムネイルをタップして再生する「ファサード」形式（初期ロード軽量化）
  - 関連記事を最大4件表示（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新記事 の段階的フォールバック）
- **ジャンル一覧ページ**（カテゴリ別アコーディオン表示）
- **自己紹介ページ／使い方ページ**
- レスポンシブ対応（スマホ用ドロワーメニュー、スクロール連動の固定ヘッダー）

### 管理者向け（要ログイン）

- **記事の投稿・編集・削除**
  - マークダウン編集ツールバー（H2/H3見出し・太字・目次・箇条書き・地図・YouTube・画像挿入）
  - 複数画像アップロード（一括／1枚ずつ追加、プレビュー・キャプション編集・個別削除）
  - デフォルトサムネイルの選択（画像未アップロード時）
  - 公開／非公開のトグル切り替え（非公開記事は管理者のみ閲覧可）
  - ハッシュタグ入力（スペース・カンマ区切り、リアルタイムプレビュー付き）
- **マイページ**（投稿一覧・使用ジャンル一覧・ニックネーム変更）

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1 |
| ORM / マイグレーション | Flask-SQLAlchemy（SQLAlchemy 2.0）/ Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF（CSRFProtect） |
| データベース | PostgreSQL 18（Docker Compose で起動） |
| マークダウン変換 | Markdown（toc / nl2br 拡張） |
| フロントエンド | Jinja2 テンプレート + 素の CSS / JavaScript（フレームワーク不使用） |

アプリ本体は Application Factory パターン（`create_app()`）+ Blueprint 構成で、循環インポートを避けるため拡張機能インスタンスは `extensions.py` に分離しています。

## ディレクトリ構成

```
.
├── app.py                # アプリケーションファクトリ（エントリーポイント）
├── config.py             # .env 読み込み・環境変数の提供
├── constants.py          # デフォルトジャンルなどの定数
├── extensions.py         # db / login_manager / migrate インスタンス
├── models.py             # ORM モデル（User / Post / Hashtag / 中間テーブル）
├── docker-compose.yml    # PostgreSQL コンテナ定義
├── requirements.txt
├── migrations/           # Alembic マイグレーション
├── views/
│   ├── auth.py           # ログイン・ログアウト（秘密URL＋ゲートキー）
│   ├── blog.py           # 一般公開ページ（一覧・詳細・ジャンル等）
│   └── admin.py          # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/            # Jinja2 テンプレート
└── static/
    ├── css/              # ページ・機能ごとに分割した CSS
    └── img/
        ├── posts/        # アップロードされた記事画像
        └── thbnails/     # デフォルトサムネイル画像
```

## データベース設計

| テーブル | 内容 |
| --- | --- |
| `user` | 管理者情報（username / ハッシュ化パスワード / nickname） |
| `post` | 記事（タイトル・本文・ジャンル・画像名・キャプション・公開設定・投稿/更新日時） |
| `hashtag` | ハッシュタグ（name は一意制約付き） |
| `post_hashtags` | Post ↔ Hashtag の多対多中間テーブル |

- 画像は `img_name` にカンマ区切り、キャプションは `img_captions` にタブ区切りで保存し、順番で対応付けます。
- `updated_at` は nullable で、「一度も更新されていない記事」を NULL で表現します。
- ハッシュタグは `lazy='selectin'` で一括ロードし、一覧表示時の N+1 問題を回避しています。
- どの記事にも紐付かなくなったタグは、記事の編集・削除時に自動的に削除されます（孤立タグ掃除）。

## セットアップ

### 1. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. 環境変数（.env）の作成

プロジェクトルートに `.env` を作成します（`.gitignore` 済み）。

```dotenv
# PostgreSQL 接続情報（docker-compose と共有）
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=blogdb

# Flask セッション署名キー（本番では必須）
SECRET_KEY=your-secret-key

# 管理者認証
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<werkzeug でハッシュ化した文字列>

# ログインページの秘密パス（例: /secret-login-abc123 でアクセス）
ADMIN_LOGIN_PATH=secret-login-abc123

# ログインページ表示用の合言葉（ゲートキー）
ADMIN_GATE_KEY=<長いランダム文字列>
```

ランダム文字列・パスワードハッシュの生成例:

```bash
# ゲートキー / SECRET_KEY の生成
python -c "import secrets; print(secrets.token_urlsafe(32))"

# パスワードハッシュの生成
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('平文パスワード'))"
```

> **注意:** `ADMIN_LOGIN_PATH` と `ADMIN_GATE_KEY` が未設定の場合、アプリはフェイルクローズ設計により起動拒否または常時 404 となります。

### 3. データベースの起動とマイグレーション

```bash
# PostgreSQL コンテナを起動（ホスト側ポート 55432）
docker compose up -d

# スキーマを適用
flask db upgrade
```

### 4. 管理者ユーザーの登録

`user` テーブルに 1 件、管理者レコードを登録します（Flask shell の例）:

```bash
flask shell
```

```python
from extensions import db
from models import User
import os

user = User(username=os.getenv("ADMIN_USERNAME"),
            password=os.getenv("ADMIN_PASSWORD"))  # ハッシュ化済み文字列
db.session.add(user)
db.session.commit()
```

### 5. アプリの起動

```bash
python app.py
# → http://127.0.0.1:5000
```

管理者ログインは、初回のみ合言葉付きの URL でアクセスします:

```
http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

以降 90 日間はゲート Cookie により `?key=` なしの秘密 URL でアクセスできます。

## 本文で使える記法

| 記法 | 効果 |
| --- | --- |
| `## 見出し` / `### 見出し` | H2 / H3 見出し |
| `**太字**` | 太字 |
| `[toc]` | その位置に目次を挿入（未使用時は記事先頭に自動生成） |
| `[img1]` `[img2]` … | アップロード画像を本文中に埋め込み（キャプション付き `<figure>` 対応） |
| `[map:東京スカイツリー]` | Google マップの埋め込み |
| `[youtube:URL または動画ID]` | YouTube 動画の埋め込み（タップで再生） |

いずれも投稿・編集画面のツールバーからワンクリックで挿入できます（地図・YouTube はプレビュー付きモーダル）。

## セキュリティ設計

管理画面への到達には「①秘密URL → ②ゲートキー → ③ユーザー名 → ④パスワード」の 4 要素すべてが必要な多層防御になっています。

- **ログインページの隠蔽**: URL を環境変数で秘匿し、さらにゲートキー（合言葉→Cookie 発行）を持たない訪問者には 404 を返してページの存在自体を隠す。未ログインで管理者ページへアクセスした場合もリダイレクトせず 404 を返す（`unauthorized_handler`）。
- **ブルートフォース対策**: ログイン 5 回連続失敗で 5 分間のセッションロックアウト。
- **パスワード管理**: Werkzeug によるハッシュ化保存（平文非保持）。認証失敗時はユーザー名/パスワードのどちらが誤りかを明かさない。
- **CSRF 対策**: CSRFProtect により全変更系リクエストでトークン検証を強制。
- **ファイルアップロードの多層検証**: 拡張子ホワイトリスト → `filetype` によるマジックナンバー検証（偽装検出）→ `secure_filename` によるサニタイズ → UUID によるファイル名ランダム化 → 30MB のリクエストサイズ制限。
- **Open Redirect 対策**: 削除後のリダイレクトで referer の同一オリジンを検証。
- **リバースプロキシ対応**: `ProxyFix` により PaaS（Render / Heroku 等）配下でも HTTPS 判定・Secure Cookie が正しく機能。
- **フェイルクローズ**: `SECRET_KEY`（本番）・`ADMIN_LOGIN_PATH`・`ADMIN_GATE_KEY` の設定漏れ時は起動拒否または常時 404 で安全側に倒す。

## 本番デプロイ時の補足

- `DATABASE_URL` 環境変数を設定すると、ローカル用接続 URL の代わりにそれが使用されます（PaaS の自動設定を想定）。
- 本番では `debug=True` での起動や `flask run` の開発サーバーは使用せず、Gunicorn 等の WSGI サーバーを利用してください。
- セッションベースのロックアウトはブラウザ変更で回避可能なため、より強固にする場合は Flask-Limiter + Redis による IP ベース制限の導入を推奨します（`views/auth.py` のコメント参照）。

## ライセンス

個人学習・個人利用を目的としたプロジェクトです。