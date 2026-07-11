# MIT Blog

Flask 製の個人用ブログアプリです。単一管理者が記事を投稿・管理し、閲覧は誰でも行えます。Markdown ベースのエディタ、画像・地図・YouTube の埋め込み、ハッシュタグ／ジャンルによる検索、ダークモードなどを備えています。

Application Factory パターン（`create_app()`）で構成されており、ローカル開発では PostgreSQL、PythonAnywhere などの無料枠では SQLite と、環境変数の切り替えだけで両対応します。

---

## 主な機能

**記事の投稿・編集（管理者のみ）**
- Markdown で本文を記述。専用ツールバーから H2/H3 見出し・太字・目次（`[toc]`）・箇条書きリスト・地図・YouTube をワンクリックで挿入できます。
- 複数画像のアップロードに対応（一括選択／1枚ずつ追加、ドラッグ不要）。各画像にキャプションを設定でき、本文中に `[img1]` `[img2]` … で好きな位置へ配置できます。
- 画像未アップロード時は 11 種類のデフォルトサムネイルから選択、またはシステム共通サムネイルに自動フォールバックします。
- 公開／非公開をトグルで切り替え可能。非公開記事は管理者本人のみ閲覧できます。

**閲覧・検索**
- キーワード（タイトル・ハッシュタグ）× ジャンル × ハッシュタグを組み合わせた絞り込み検索。
- ジャンル選択時は、そのジャンル内で使われているハッシュタグでさらに絞り込めます。
- 記事詳細では、同ジャンル×同タグ → 同タグ → 同ジャンル → 最新、の優先順位で関連記事を最大4件表示します。
- トップページに総投稿数・ハッシュタグ数・最終更新日の統計を表示。記事一覧はページ番号方式でページ送りします。

**本文埋め込み**
- `[map:場所名]` で Google マップ、`[youtube:URL]` でファサード形式（サムネイル→クリックで再生）の YouTube を埋め込めます。

**UI**
- ライト／ダークモード切り替え（`localStorage` に保存、OS 設定にも追従）。
- スマホ対応。記事編集時はツールバーがキーボード直上に固定され、最終行が隠れないよう余白を自動確保します。
- スクロール連動でヘッダーが自動で表示／非表示になります。

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.1（Application Factory パターン） |
| ORM / マイグレーション | SQLAlchemy 2.0 / Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム / CSRF | Flask-WTF |
| データベース | PostgreSQL 18（ローカル） / SQLite（無料枠デプロイ） |
| Markdown | Markdown（`toc` / `nl2br` 拡張） |
| 画像検証 | filetype（MIME 判定） |
| フロント | 素の HTML / CSS / JavaScript（テンプレート内） |
| 本番連携 | ProxyFix（リバースプロキシ配下での HTTPS 判定補正） |

---

## ディレクトリ構成

```
.
├── app.py                  # エントリーポイント。create_app() でアプリを組み立てる
├── config.py               # .env の読み込み・環境変数の提供
├── constants.py            # デフォルトジャンル一覧（DEFAULT_GENRES）
├── extensions.py           # db / login_manager / migrate インスタンスの置き場
├── models.py               # テーブル定義（User / Post / Hashtag / 中間テーブル）
├── init_db.py              # SQLite 向け初期化（テーブル作成＋管理者ユーザー作成）
│
├── views/                  # Blueprint（機能別ルート）
│   ├── auth.py             #   ログイン・ログアウト
│   ├── blog.py             #   一般公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py            #   管理者専用（投稿・編集・削除・マイページ）
│
├── templates/              # Jinja2 テンプレート
├── static/css/             # ページ別 CSS（Coastal Dawn テーマ / ダークモード）
├── static/img/             # 投稿画像・サムネイル
├── migrations/             # Alembic マイグレーション
│
├── docker-compose.yml      # ローカル開発用 PostgreSQL
├── requirements.txt        # 依存パッケージ（PostgreSQL ドライバ込み）
├── requirements-pythonanywhere.txt  # 無料枠向け（SQLite・psycopg 除外）
├── wsgi_pythonanywhere.py  # PythonAnywhere の WSGI 設定サンプル
└── deploy_pythonanywhere.md # PythonAnywhere へのデプロイ・運用手順書
```

---

## データモデル

```
User (管理者) ──1対多──▶ Post (記事) ──多対多──▶ Hashtag (タグ)
                                    （post_hashtags 中間テーブル経由）
```

- **User**: `username` / ハッシュ化した `password` / `nickname`（任意）。
- **Post**: `title` / `body`(Markdown) / `genre` / `created_at` / `updated_at`(未更新時は NULL) / `img_name`(カンマ区切りのファイル名, Text 型) / `img_captions`(タブ区切り) / `default_thumb` / `is_published`。
- **Hashtag**: `name`（`#` を除いた文字列、ユニーク）。どの記事にも紐付かなくなったタグは記事の編集・削除時に自動で掃除されます。

---

## セキュリティ設計

このアプリは学習を兼ねて多層防御を実装しています。

- **ログイン URL の隠蔽**: ログインページの URL を `.env`（`ADMIN_LOGIN_PATH`）でランダム化。
- **ゲートキー方式**: 合言葉（`ADMIN_GATE_KEY`）付き URL でアクセスした場合のみ Cookie を発行。Cookie を持たない訪問者にはログインページを 404 として隠します（設定漏れ時はフェイルクローズで 404）。
- **ブルートフォース対策**: ログイン連続失敗5回で5分間ロックアウト（セッションベース）。
- **パスワード**: Werkzeug でハッシュ化して保存し、平文比較は行いません。
- **CSRF 保護**: 全フォームに CSRF トークンを強制適用。
- **画像アップロード検証**: 拡張子ホワイトリスト＋先頭バイトの MIME 判定＋ UUID によるファイル名ランダム化＋30MB の容量制限。保存はアトミック（途中失敗時は保存済みファイルを掃除）。
- **DB とファイルの整合性**: 画像の物理削除は必ず DB コミット成功後に実行。コミット失敗時はロールバックして新規保存ファイルを掃除します。
- **XSS 対策**: 画像キャプション・地図ラベル・YouTube エラー表示など、HTML に埋め込むユーザー入力を `markupsafe.escape()` でエスケープ。地図 URL は `urllib.parse.quote()` で正しくエンコード。
- **Open Redirect 対策**: 削除後のリダイレクト先を同一オリジンか検証。
- **セキュリティヘッダー**: `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` を付与。
- **Secure Cookie**: 本番判定時に `SESSION_COOKIE_SECURE` を有効化。`ProxyFix` によりリバースプロキシ配下でも HTTPS を正しく判定します。

---

## ローカル開発環境のセットアップ

### 1. リポジトリの取得と仮想環境

```bash
git clone <このリポジトリのURL>
cd <プロジェクトディレクトリ>

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. PostgreSQL の起動（Docker）

```bash
docker compose up -d
```

`docker-compose.yml` はホスト側 `15432` 番ポートで PostgreSQL 18 を公開します（接続情報は `.env` の値を使用）。

### 3. `.env` の作成

プロジェクト直下に `.env` を作成します（`.gitignore` 済みなので Git には含まれません）。

```ini
# --- 本番判定 / DB 切り替え ---
# ローカル PostgreSQL を使う場合は下2つは未設定でOK
# FLASK_ENV=production
# USE_SQLITE=1

# --- Flask ---
SECRET_KEY=ランダムな長い文字列
FLASK_DEBUG=1                 # ローカルでデバッグしたい場合

# --- ローカル PostgreSQL（docker-compose 用）---
POSTGRES_USER=blog_user
POSTGRES_PASSWORD=blog_password
POSTGRES_DB=blog_db

# --- 管理者認証 ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ログインパスワード（平文可・ハッシュ済みも可）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx   # 推測されにくいログインURLのパス
ADMIN_GATE_KEY=ランダムな長い文字列       # ログイン画面を開くための合言葉
```

ランダム文字列の生成:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`SECRET_KEY` と `ADMIN_GATE_KEY` には**別々の値**を設定してください。

### 4. データベースの初期化

マイグレーションを適用します。

```bash
flask db upgrade
```

その後、管理者ユーザーを作成します（SQLite 運用と共通で使える初期化スクリプト）。

```bash
python init_db.py
```

`init_db.py` はテーブル作成と管理者ユーザー登録を一括で行い、`ADMIN_PASSWORD` が平文でもハッシュ済みでも適切に処理します。何度実行しても安全です。

### 5. アプリの起動

```bash
python app.py
```

`http://127.0.0.1:5000/` にアクセスするとトップページが表示されます。

---

## 使い方

### 管理者ログイン

ログイン URL は隠蔽されています。初回は合言葉付き URL でアクセスします。

```
http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされます。以降はその Cookie（90日間有効）でログイン画面にアクセスでき、`ADMIN_USERNAME` / `ADMIN_PASSWORD` でログインします。

### 記事の投稿

ログイン後、ヘッダーの「新規投稿」から記事を作成できます。ツールバーで見出し・目次・リスト・地図・YouTube・画像を挿入し、ハッシュタグはスペースやカンマ区切りで入力します（`#` は付けても省略しても可）。

---

## データベース構造を変更したとき

`models.py` を変更した場合はマイグレーションを生成・適用します。

```bash
flask db migrate -m "変更内容"
flask db upgrade
```

（SQLite の動作確認用途では、`init_db.py` の `db.create_all()` は「無いテーブルを作る」だけでカラム追加はしない点に注意してください。詳細は `deploy_pythonanywhere.md` を参照。）

---

## デプロイ

PythonAnywhere（無料枠・SQLite）への公開手順と、公開後のコード更新フローは **[`deploy_pythonanywhere.md`](deploy_pythonanywhere.md)** に詳しくまとめています。

要点は「PC で修正 → GitHub に push → サーバーで `git pull` → Web タブで Reload」です。SQLite 運用時は `.env` に `USE_SQLITE=1` と `FLASK_ENV=production` の設定が必須です。

---

## ライセンス

学習・個人利用を目的としたプロジェクトです。