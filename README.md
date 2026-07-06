# MIT Blog - 個人用ブログアプリ

Flask + PostgreSQL で構築した、単一管理者向けの個人ブログアプリケーションです。
Markdown での記事執筆、画像・地図・YouTube の埋め込み、ジャンル×ハッシュタグによる記事の絞り込みなどに対応しています。

## 主な機能

### 閲覧者向け（一般公開）

- **記事一覧（トップページ）**
  - サムネイル付き記事カード表示
  - ページ番号によるページ送り（1ページ4件、JSによるクライアントサイド切替）
  - サイト統計（総投稿数・ハッシュタグ数・最終更新日）の表示
- **検索・絞り込み**
  - キーワード検索（タイトル・ハッシュタグを対象、ヘッダー検索バー / インページ検索エリアの両方から可能）
  - ジャンル絞り込み（アコーディオン形式のジャンル一覧ページあり）
  - ジャンル選択中はハッシュタグによる追加絞り込みが可能（ジャンル×タグの二段階絞り込み）
- **記事詳細ページ**
  - Markdown → HTML 変換表示（`nl2br` / `toc` 拡張対応）
  - `[toc]` マーカーによる目次の自動生成
  - `[imgN]` タグによる本文中への画像＋キャプション埋め込み
  - `[map:場所名]` タグによる Google マップ埋め込み
  - `[youtube:URL]` タグによる YouTube 動画埋め込み（サムネイルをタップして再生する「ファサード」形式で軽量化）
  - 関連記事の自動表示（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新記事、の優先順位で最大4件）
- **静的ページ**：自己紹介（/about）、使い方（/howto）

### 管理者向け（要ログイン）

- **記事の投稿・編集・削除**
  - Markdown 編集ツールバー（H2/H3見出し・太字・目次・箇条書き・地図・YouTube・画像タグ挿入）
  - 複数画像アップロード（一括選択 / 1枚ずつ追加、プレビュー・削除・キャプション入力対応）
  - デフォルトサムネイル選択（画像なし記事用に11種のプリセット）
  - 公開 / 非公開の切り替え（非公開記事は管理者のみ閲覧可能）
  - ジャンル選択（プリセット + 独自ジャンルの新規作成）
  - ハッシュタグ入力（スペース・カンマ区切り、リアルタイムプレビュー付き）
- **マイページ**
  - 投稿一覧（「もっと見る / 表示を減らす」方式）
  - ニックネーム変更
  - 使用ジャンル一覧の表示

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1 |
| ORM / DB | SQLAlchemy 2.0（Flask-SQLAlchemy）/ PostgreSQL 18 |
| マイグレーション | Alembic（Flask-Migrate） |
| 認証 | Flask-Login |
| CSRF 保護 | Flask-WTF（CSRFProtect） |
| Markdown 変換 | Python-Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |
| 開発環境 | Docker Compose（PostgreSQL コンテナ） |
| フロントエンド | Jinja2 テンプレート + バニラ JS + 独自 CSS（Coastal Dawn テーマ） |

## プロジェクト構成

```
.
├── app.py                 # アプリのエントリーポイント（Application Factory パターン）
├── config.py              # .env の読み込みと設定値の提供
├── constants.py           # デフォルトジャンルなどの定数
├── extensions.py          # db / login_manager / migrate のインスタンス定義（循環インポート回避）
├── models.py              # ORM モデル（User / Post / Hashtag / post_hashtags 中間テーブル）
├── docker-compose.yml     # ローカル開発用 PostgreSQL
├── requirements.txt
├── migrations/            # Alembic マイグレーション
├── views/
│   ├── auth.py            # ログイン / ログアウト（秘密URL + ゲートキー方式）
│   ├── blog.py            # 一般公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py           # 管理者専用ページ（投稿・編集・削除・マイページ）
├── templates/             # Jinja2 テンプレート
└── static/
    ├── css/               # ページ・機能別に分割した CSS
    └── img/
        ├── posts/         # アップロード画像（UUID ファイル名で保存）
        └── thbnails/      # デフォルトサムネイル
```

## セットアップ

### 1. リポジトリの取得と仮想環境

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

プロジェクトルートに `.env` を作成します（`.gitignore` 登録済み）。

```dotenv
# --- PostgreSQL ---
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# --- Flask ---
SECRET_KEY=<ランダムな長い文字列>
FLASK_DEBUG=1                      # ローカル開発時のみ

# --- 管理者認証 ---
ADMIN_USERNAME=<管理者ユーザー名>
ADMIN_PASSWORD=<ハッシュ化済みパスワード>
ADMIN_LOGIN_PATH=<推測されにくいランダム文字列>   # 例: secret-login-abc123
ADMIN_GATE_KEY=<ランダムな長い文字列>              # ログインページ表示の合言葉
```

ランダム文字列の生成例:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

パスワードハッシュの生成例:

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('平文パスワード'))"
```

> **注意**: `ADMIN_LOGIN_PATH` と `ADMIN_GATE_KEY` は未設定のまま起動するとエラー / 404（フェイルクローズ）になります。必ず設定してください。

### 3. データベースの起動とマイグレーション

```bash
# PostgreSQL コンテナを起動（ホスト側ポート 15432）
docker compose up -d

# スキーマを適用
flask db upgrade
```

### 4. 管理者ユーザーの登録

`user` テーブルに管理者レコードを 1 件作成します（Flask シェルの例）:

```bash
flask shell
```

```python
from extensions import db
from models import User
import os
u = User(username=os.getenv("ADMIN_USERNAME"), password=os.getenv("ADMIN_PASSWORD"))
db.session.add(u)
db.session.commit()
```

### 5. アプリの起動

```bash
python app.py
# → http://127.0.0.1:5000
```

### 管理画面へのログイン

初回は「合言葉付きの秘密 URL」にアクセスします:

```
http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

初回アクセスでゲート Cookie（90日有効）が発行され、以降は `?key=` なしの秘密 URL でログインページを開けます。合言葉も Cookie も持たない訪問者には 404 を返し、ログインページの存在自体を隠します。

## セキュリティ対策

本アプリでは以下の多層防御を実装しています。

- **認証まわり**
  - 秘密のログイン URL（`ADMIN_LOGIN_PATH`）+ ゲートキー Cookie 方式の二段構え
  - 未ログインで管理ページにアクセスした場合は 404 を返し、ページの存在を隠蔽（`login_view` を設定しない設計）
  - ログイン連続失敗によるロックアウト（5回失敗で5分間）
  - パスワードはハッシュ化して保存（`werkzeug.security`）
  - `ADMIN_LOGIN_PATH` / `ADMIN_GATE_KEY` 未設定時は起動拒否 / 常時 404（フェイルクローズ）
- **リクエスト / セッション**
  - 全フォームへの CSRF トークン強制（Flask-WTF）
  - セッション Cookie の `HttpOnly` / `SameSite=Lax` / 本番時 `Secure` を明示設定
  - ProxyFix によるリバースプロキシ（Render / Heroku 等）配下での HTTPS 判定補正
  - セキュリティヘッダー付与（`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy`）
  - 削除後リダイレクトの同一オリジン検証（Open Redirect 対策）
- **ファイルアップロード**
  - 拡張子ホワイトリスト（PNG / JPG / GIF / WebP）
  - `filetype` によるマジックナンバー検証（拡張子偽装の検出）
  - UUID によるファイル名の完全ランダム化（パストラバーサル・URL 推測防止）
  - リクエストサイズ 30MB 制限（413 エラーハンドラ付き）
- **XSS 対策**
  - 本文への埋め込み時にキャプション・地図の場所名・YouTube エラー表示を `markupsafe.escape()` で無害化
  - 地図 URL は `urllib.parse.quote()` で正しくエンコード
  - ハッシュタグプレビューは `innerHTML` を使わず DOM API（`textContent`）で構築
- **データ整合性**
  - 画像ファイルの物理削除は DB commit 成功後に実行（commit 失敗時は新規保存ファイルを掃除）
  - 孤立ハッシュタグの自動削除（記事の編集・削除時）

## 本文で使える独自タグ

| タグ | 効果 |
|---|---|
| `[toc]` | その位置に目次を挿入（未使用時は記事冒頭に自動生成） |
| `[img1]` `[img2]` … | アップロード画像を本文中に埋め込み（キャプション付き `<figure>` 対応） |
| `[map:東京スカイツリー]` | Google マップの iframe 埋め込み |
| `[youtube:https://youtu.be/...]` | YouTube 動画をファサード形式で埋め込み（watch / youtu.be / shorts / embed URL・動画 ID 単体に対応） |

いずれも投稿・編集画面のツールバーからワンクリック（地図・YouTube はプレビュー付きモーダル）で挿入できます。

## 本番デプロイ時の注意

- 環境変数 `DATABASE_URL`（PaaS が自動設定）または `FLASK_ENV=production` が存在すると本番判定になります
- 本番では `SECRET_KEY` 未設定時に起動を拒否します
- 本番判定時は `FLASK_DEBUG` を設定していてもデバッグモードは強制無効化されます
- Gunicorn などの WSGI サーバー経由での起動を推奨します（`python app.py` の直接起動は開発用）

## ライセンス

個人学習・ポートフォリオ用プロジェクトです。