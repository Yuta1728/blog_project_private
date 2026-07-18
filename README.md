# MITO Blog

Flask 製の個人ブログアプリケーションです。
Markdown での記事執筆、画像・地図・YouTube の埋め込み、ジャンル／ハッシュタグによる分類・検索、ダークモード対応などを備えた、単一管理者運用のブログシステムです。

---

## 目次

- [MITO Blog](#mito-blog)
  - [目次](#目次)
  - [特徴](#特徴)
  - [主な機能](#主な機能)
    - [閲覧者向けの機能](#閲覧者向けの機能)
    - [管理者向けの機能](#管理者向けの機能)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ](#セットアップ)
    - [1. リポジトリの取得と仮想環境の作成](#1-リポジトリの取得と仮想環境の作成)
    - [2. 依存パッケージのインストール](#2-依存パッケージのインストール)
    - [3. データベースの用意](#3-データベースの用意)
    - [4. 起動](#4-起動)
  - [環境変数](#環境変数)
    - [接続先の決定順序](#接続先の決定順序)
  - [データベースの初期化](#データベースの初期化)
    - [マイグレーション運用（PostgreSQL 推奨）](#マイグレーション運用postgresql-推奨)
    - [一括初期化（SQLite 向け）](#一括初期化sqlite-向け)
  - [記事本文の書き方（独自記法）](#記事本文の書き方独自記法)
  - [セキュリティ設計](#セキュリティ設計)
  - [パフォーマンス上の工夫](#パフォーマンス上の工夫)
  - [デプロイ](#デプロイ)
  - [ライセンス](#ライセンス)

---

## 特徴

- **Application Factory パターン**（`create_app()`）と **Blueprint** による機能分割
- **PostgreSQL / SQLite の両対応**（環境変数の切り替えのみで動作）
- **多層防御のセキュリティ設計**（秘密 URL＋合言葉ゲート＋ブルートフォース対策＋CSRF＋アップロード検証）
- **表示速度を意識した実装**（本文 HTML のキャッシュ、画像の自動最適化、インデックス設計、ページネーション）
- ライト／ダークの **テーマ切り替え**（設定は端末に保存）
- スマートフォンでの記事編集に最適化した **ドッキング型エディタツールバー**

---

## 主な機能

### 閲覧者向けの機能

ログインなしで誰でも利用できる機能です。

| 機能 | 説明 |
| --- | --- |
| 記事一覧（トップページ） | 公開記事を新着順に表示。1 ページ 4 件のページ番号送りに対応 |
| キーワード検索 | 記事タイトル・ハッシュタグ名に対する部分一致検索 |
| ジャンル絞り込み | 検索エリアのセレクト、またはジャンル一覧ページから絞り込み |
| ジャンル一覧ページ | カテゴリ（ライフスタイル／娯楽 等）別のアコーディオン表示 |
| ハッシュタグ絞り込み | ジャンル選択中に、そのジャンル内で使われているタグでさらに絞り込み |
| 記事詳細ページ | Markdown で書かれた本文を整形表示 |
| 目次（TOC） | 見出し（H2／H3）から自動生成。本文中の任意の位置にも配置可能 |
| 画像とキャプション | 本文中の指定位置に画像を表示。キャプション付きにも対応 |
| 地図の埋め込み | 記事内に Google マップを表示 |
| YouTube の埋め込み | 最初はサムネイルのみ表示し、クリック時に再生を開始（ファサード方式） |
| 関連記事の表示 | 「同ジャンル×同タグ → 同タグ → 同ジャンル → 最新」の優先順で最大 4 件を提示 |
| サイト統計 | 総投稿数・ハッシュタグ数・最終更新日をトップページに表示 |
| 自己紹介／使い方ページ | 管理者プロフィールとブログの使い方の案内 |
| ダークモード | ヘッダーのボタンで切り替え。選択内容はブラウザに保存され次回も維持 |
| レスポンシブ対応 | PC／スマートフォンの双方に最適化。スマホではドロワーメニューを使用 |

### 管理者向けの機能

ログイン後にのみ利用できる機能です。

| 機能 | 説明 |
| --- | --- |
| 管理者ログイン | 秘密 URL ＋合言葉ゲートによる二重の入口制御 |
| 記事の新規投稿 | タイトル・本文・ジャンル・タグ・画像・公開設定をまとめて登録 |
| 記事の編集・削除 | 既存記事の全項目を変更可能。削除時は関連画像も自動で削除 |
| 公開／非公開の切り替え | 非公開記事は管理者本人のみ閲覧可能。一覧では「🔒 非公開」バッジを表示 |
| Markdown ツールバー | H2／H3 見出し・太字・箇条書き・目次・画像・地図・YouTube をワンタップ挿入 |
| 画像の複数アップロード | 「まとめて選択」「1 枚ずつ追加」に対応。プレビューと個別削除が可能 |
| 画像キャプションの編集 | 画像ごとに説明文を設定。既存画像のキャプションも後から変更可能 |
| サムネイル画像の設定 | 専用画像のアップロード、プリセットからの選択、システム既定の 3 段階 |
| ハッシュタグ入力 | スペース／カンマ区切りで複数入力。入力中にバッジをリアルタイム表示 |
| ジャンルの新規作成 | プリセットにないジャンルをその場で作成し、以降の選択肢に追加 |
| マイページ | 自分の全投稿をページ送りで一覧表示。総投稿数・使用ジャンルを確認可能 |
| ニックネーム変更 | 記事の投稿者名として表示される名前を変更 |
| スマホ編集の最適化 | ツールバーをキーボード直上に固定し、カーソルが隠れないよう自動スクロール |

---

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.1 |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy 3.1 |
| マイグレーション | Alembic / Flask-Migrate |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF (CSRFProtect) |
| データベース | PostgreSQL（本番・ローカル） / SQLite（無料ホスティング） |
| テンプレート | Jinja2 |
| 本文変換 | Markdown（toc / nl2br 拡張） |
| 画像処理 | Pillow |
| ファイル検証 | filetype |
| フロントエンド | 素の HTML / CSS / JavaScript（フレームワーク不使用） |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリ生成（Application Factory）
├── config.py               # .env からの環境変数読み込み
├── constants.py            # ジャンル定義（唯一の情報源）
├── extensions.py           # db / login_manager / migrate のインスタンス
├── models.py               # テーブル定義（User / Post / Hashtag）
├── rendering.py            # 本文（Markdown + 独自タグ）→ HTML 変換
├── init_db.py              # DB 初期化スクリプト（SQLite 運用向け）
│
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
│
├── templates/              # Jinja2 テンプレート
│   ├── base.html           # 全ページ共通レイアウト
│   ├── _macros.html        # 記事カード等の共通マクロ
│   ├── index.html / detail.html / create.html / update.html ...
│   └── _map_modal.html / _youtube_modal.html
│
├── static/
│   ├── css/                # ページ単位に分割した CSS + dark-mode.css
│   ├── js/editor.js        # create / update 共通のエディタ処理
│   └── img/                # 投稿画像・サムネイル
│
├── migrations/             # Alembic マイグレーション
├── requirements.txt                  # 通常環境（PostgreSQL 含む）
├── requirements-pythonanywhere.txt   # SQLite 運用向け（psycopg 除外）
└── deploy_pythonanywhere.md          # デプロイ手順書
```

---

## セットアップ

### 1. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリのURL>
cd <プロジェクトディレクトリ>

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

SQLite のみで動かす場合（PostgreSQL ドライバ不要）:

```bash
pip install -r requirements-pythonanywhere.txt
```

### 3. データベースの用意

ローカルで PostgreSQL を使う場合は、同梱の `docker-compose.yml` を利用できます。

```bash
docker compose up -d
```

SQLite を使う場合は、環境変数に `USE_SQLITE=1` を設定するだけで、`instance/blog.db` が自動的に作成されます。

### 4. 起動

```bash
python app.py
```

`http://127.0.0.1:5000` で起動します。

---

## 環境変数

プロジェクト直下に `.env` を作成します（`.gitignore` により Git 管理外です）。

```env
# --- 動作モード ---
FLASK_ENV=production          # 本番運用時に設定（Secure Cookie / SECRET_KEY 必須化）
USE_SQLITE=1                  # SQLite を使う場合に設定

# --- セッション・CSRF ---
SECRET_KEY=<ランダムな長い文字列>

# --- 管理者認証 ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<パスワード（平文可。init_db.py がハッシュ化）>
ADMIN_LOGIN_PATH=<推測されにくいログイン URL パス>
ADMIN_GATE_KEY=<ログイン画面を表示するための合言葉>

# --- PostgreSQL（ローカル開発時のみ） ---
POSTGRES_USER=<ユーザー名>
POSTGRES_PASSWORD=<パスワード>
POSTGRES_DB=<DB 名>

# --- 明示的な接続先を指定する場合（最優先） ---
# DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
```

ランダム文字列の生成:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 接続先の決定順序

1. `DATABASE_URL` が設定されていればそれを使用
2. `USE_SQLITE=1` なら `instance/blog.db`（SQLite）
3. いずれもなければローカルの PostgreSQL（`localhost:15432`）

---

## データベースの初期化

### マイグレーション運用（PostgreSQL 推奨）

```bash
flask db upgrade
```

`models.py` を変更した場合:

```bash
flask db migrate -m "変更内容"
flask db upgrade
```

### 一括初期化（SQLite 向け）

テーブル作成と管理者ユーザーの登録を同時に行います。何度実行しても安全です。

```bash
python init_db.py
```

このスクリプトは `db.create_all()` の後に Alembic の履歴を `head` にスタンプするため、後からマイグレーション運用へ移行しても不整合が起きません。

---

## 記事本文の書き方（独自記法）

本文は Markdown で記述でき、加えて以下の独自タグが使えます（いずれも編集画面のツールバーから挿入できます）。

| 記法 | 動作 |
| --- | --- |
| `## 見出し` / `### 見出し` | H2 / H3 見出し。目次の生成対象になります |
| `**太字**` | 太字 |
| `[toc]` | その位置に目次を展開（未使用時は記事冒頭に自動表示） |
| `[img1]` `[img2]` … | アップロード順に対応する画像を挿入。キャプション設定時は figure 形式 |
| `[map:東京スカイツリー]` | Google マップを埋め込み |
| `[youtube:https://youtu.be/xxxx]` | YouTube 動画を埋め込み（サムネイル → クリックで再生） |

`[youtube:]` は通常 URL・短縮 URL・ショート・埋め込み URL・動画 ID 単体のいずれにも対応しています。

また、空行を 2 行以上連続させると、その分だけ行間が保持されます（通常の Markdown では 1 つの段落区切りに潰されます）。

---

## セキュリティ設計

管理画面に到達するには、以下の 4 要素をすべて満たす必要があります。

1. **秘密の URL**（`ADMIN_LOGIN_PATH`）
2. **ゲートキー**（`ADMIN_GATE_KEY`。合言葉付き URL でアクセスすると Cookie が発行される）
3. **ユーザー名**（`ADMIN_USERNAME`）
4. **パスワード**

その他の対策:

- ゲート未通過・未ログイン時のアクセスには **404 を返し、ページの存在自体を隠す**
- `ADMIN_GATE_KEY` 未設定時は**常に 404**（フェイルクローズ設計）
- ログイン **5 回失敗で 5 分間ロックアウト**
- パスワードは **Werkzeug でハッシュ化**して保存（平文は保持しない）
- 全フォームへの **CSRF トークン**適用
- Cookie は **HttpOnly / SameSite=Lax / 本番では Secure**
- **ProxyFix** によりリバースプロキシ配下でも HTTPS を正しく判定
- アップロードは **拡張子＋MIME（先頭バイト）の二層検証**で偽装を検出
- アップロード合計サイズを **30MB に制限**
- `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` を付与
- 削除後のリダイレクトは **同一オリジンのみ許可**（Open Redirect 対策）
- ユーザー入力を含む HTML 生成箇所は **escape / quote** で無害化

---

## パフォーマンス上の工夫

- **本文 HTML のキャッシュ**: Markdown 変換と独自タグ置換の結果を投稿・編集時に `body_html` / `toc_html` へ保存し、閲覧時の再変換をなくしています（既存記事は初回表示時に自動生成・保存）
- **画像の自動最適化**: 本文画像は長辺 1600px まで縮小して再圧縮、サムネイルは幅 400px の WebP に変換
- **インデックス設計**: `created_at` / `genre` / `is_published` / `user_id` に加え、トップページの主経路向けに複合インデックス `(is_published, created_at)` を作成
- **部分一致検索の高速化**: PostgreSQL では `pg_trgm` の GIN インデックスにより `ILIKE '%word%'` でも索引が効きます（SQLite では自動的にスキップ）
- **N+1 問題の回避**: ハッシュタグを `selectinload` で一括取得
- **サーバーサイドページネーション**: 一覧・マイページとも必要な件数のみを取得
- **レイアウトシフト対策**: 画像に `width` / `height` を明示し、`loading="lazy"` を付与
- **CSS の `<head>` 読み込み**: ページ固有 CSS も `extra_css` ブロック経由で `<head>` に配置し、FOUC を抑制

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用）への公開手順を、`deploy_pythonanywhere.md` に詳細にまとめています。初回デプロイ、更新時の反映方法、トラブルシューティング、チェックリストを含みます。

大まかな流れ:

1. GitHub へ push
2. サーバー上で `git clone` → 仮想環境作成 → `pip install`
3. `.env` をサーバー上で作成（Git 管理外のため）
4. `python init_db.py` で初期化
5. Web タブで Manual configuration（Python 3.10）／Virtualenv／WSGI／Static files を設定
6. **Reload**

更新時は「PC で修正 → push → サーバーで pull → **Reload**」が基本の流れです。

---

## ライセンス

個人利用・学習目的のプロジェクトです。