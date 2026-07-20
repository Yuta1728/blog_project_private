# MITO Blog

Flask 製の個人ブログアプリケーションです。Markdown で記事を書き、画像・地図・YouTube 動画を埋め込みながら、ハッシュタグやジャンルで整理された記事を公開できます。単一の管理者が運用し、閲覧は誰でも行える構成になっています。

Application Factory パターン（`create_app()`）で構築されており、本番の PostgreSQL とローカル／無料ホスティング向けの SQLite の両方で動作します。

---

## 目次

- [MITO Blog](#mito-blog)
  - [目次](#目次)
  - [主な機能](#主な機能)
    - [閲覧者向けの機能](#閲覧者向けの機能)
    - [管理者向けの機能](#管理者向けの機能)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ](#セットアップ)
    - [1. リポジトリの取得と仮想環境](#1-リポジトリの取得と仮想環境)
    - [2. 依存パッケージのインストール](#2-依存パッケージのインストール)
    - [3. `.env` の作成](#3-env-の作成)
  - [環境変数](#環境変数)
  - [データベースの初期化](#データベースの初期化)
    - [マイグレーションを使う場合（PostgreSQL 推奨）](#マイグレーションを使う場合postgresql-推奨)
    - [マイグレーション不要の一括初期化（SQLite 向け）](#マイグレーション不要の一括初期化sqlite-向け)
  - [起動方法](#起動方法)
    - [ローカル PostgreSQL を使う場合](#ローカル-postgresql-を使う場合)
    - [SQLite で手軽に起動する場合](#sqlite-で手軽に起動する場合)
    - [管理画面へのログイン](#管理画面へのログイン)
  - [管理コマンド](#管理コマンド)
  - [デプロイ](#デプロイ)
  - [ライセンス](#ライセンス)

---

## 主な機能

機能を「閲覧者向け（ログイン不要）」と「管理者向け（ログイン必須）」に分けて整理します。

### 閲覧者向けの機能

誰でもアクセスでき、記事を探して読むための機能です。

- **記事一覧・トップページ** — 公開記事を新しい順に、1 ページ 4 件でページ送り表示します。トップ 1 ページ目にはサイト統計（総投稿数・ハッシュタグ数・最終更新日）と自己紹介セクションが表示されます。
- **キーワード × ジャンル検索** — タイトルやハッシュタグ名の部分一致でキーワード検索でき、ジャンルと組み合わせて絞り込めます。PostgreSQL では `pg_trgm` のトリグラム索引により部分一致検索が高速化されます。
- **ジャンル一覧** — カテゴリ（ライフスタイル／社会・経済／技術・勉強 など）ごとにアコーディオン形式でジャンルを一覧表示します。ジャンル定義は `constants.py` に一元管理されています。
- **ハッシュタグ絞り込み** — ジャンル選択中に、そのジャンル内で使われているタグで記事をさらに絞り込めます。
- **記事詳細ページ** — Markdown で書かれた本文を、目次・画像キャプション・地図・YouTube 埋め込みを含めて表示します。本文 HTML は投稿・編集時にキャッシュされ、閲覧のたびに再変換されません。
- **関連記事の表示** — 記事末尾に、同一ジャンル × 同一タグ → 同一タグ → 同一ジャンル → 最新記事、の優先順位で最大 4 件の関連記事を表示します。
- **地図・YouTube 埋め込み** — 記事中の地図はその場で確認でき、YouTube 動画はサムネイル（ファサード）をタップすると再生が始まる軽量な埋め込み方式です。
- **ダークモード** — ヘッダーのボタンで切り替えでき、選択内容はブラウザに保存されます。描画前に適用されるためチラつきが起きません。
- **自己紹介・使い方ページ** — 管理者のプロフィールとブログの使い方を紹介する静的ページです。
- **レスポンシブ表示** — スマートフォンではドロワーメニューや専用レイアウトに切り替わります。

### 管理者向けの機能

秘密の URL とゲートキーによる認証を通過した管理者のみが利用できる機能です。

- **記事の投稿・編集・削除** — Markdown で記事を作成・編集できます。編集時は画像の個別削除やキャプション変更にも対応します。
- **Markdown 編集ツールバー** — H2／H3 見出し、太字、目次（`[toc]`）、箇条書きリスト、地図、YouTube、画像（`[imgN]`）をボタンから挿入できます。スマホではキーボード直上に固定されるツールバーになります。
- **画像アップロードと自動最適化** — 本文画像は EXIF の回転補正・長辺 1200px への縮小・形式ごとの再圧縮を行って保存します。拡張子と実際の MIME タイプの二層検証で偽装ファイルを弾きます。
- **サムネイル管理** — 本文画像とは独立した専用サムネイルをアップロードでき、軽量な WebP に変換されます。専用サムネイル → プリセットのデフォルトサムネイル → システム共通デフォルト、の優先順位で表示されます。
- **ハッシュタグの付与** — スペースやカンマ区切りで複数のタグを入力でき、入力中にプレビューが表示されます。孤立したタグは自動で整理されます。
- **ジャンルの選択・新規作成** — プリセットのジャンルから選ぶか、その場で新しいジャンルを作成できます。
- **公開／非公開の切り替え** — 記事ごとに公開状態をトグルできます。非公開記事は管理者本人だけが閲覧できます。
- **マイページ** — 自分の総投稿数・使用ジャンル・投稿一覧（ページ送り付き）を確認でき、ニックネームを変更できます。
- **セキュリティ対策** — 秘密のログイン URL、ゲートキー Cookie による存在隠蔽（未通過は 404）、連続ログイン失敗時のロックアウト、CSRF 保護、パスワードのハッシュ照合、各種セキュリティヘッダーを備えています。

---

## 技術スタック

- **言語 / フレームワーク** — Python 3.10 / Flask 3
- **ORM / マイグレーション** — SQLAlchemy 2.0 / Flask-Migrate（Alembic）
- **認証** — Flask-Login
- **フォーム保護** — Flask-WTF（CSRF）
- **データベース** — PostgreSQL（本番・ローカル）/ SQLite（無料ホスティング）
- **画像処理** — Pillow（縮小・WebP 変換）／ filetype（MIME 検証）
- **本文変換** — Markdown（`toc` / `nl2br` 拡張）＋ 独自タグ置換
- **フロントエンド** — Jinja2 テンプレート、素の CSS / JavaScript（ビルド不要）

---

## ディレクトリ構成

```
.
├── app.py                 # エントリーポイント（create_app / ログ / CLI / static_url）
├── config.py              # .env の読み込みと設定値の提供
├── constants.py           # ジャンル定義（唯一の情報源）
├── extensions.py          # db / login_manager / migrate インスタンス
├── models.py              # テーブル定義（User / Post / Hashtag / 中間テーブル）
├── rendering.py           # 本文 Markdown + 独自タグ → HTML 変換
├── init_db.py             # SQLite 向けの DB 初期化スクリプト
├── views/
│   ├── auth.py            # ログイン・ログアウト（秘密URL・ゲートキー）
│   ├── blog.py            # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py           # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/             # Jinja2 テンプレート
├── static/                # CSS / JS / 画像 / favicon
├── migrations/            # Alembic マイグレーション
├── requirements.txt       # 依存パッケージ（PostgreSQL 込み）
└── requirements-pythonanywhere.txt  # SQLite 運用向け（psycopg 除外）
```

---

## セットアップ

### 1. リポジトリの取得と仮想環境

```bash
git clone <このリポジトリの URL>
cd <プロジェクトディレクトリ>
python -m venv .venv
source .venv/bin/activate      # Windows は .venv\Scripts\activate
```

### 2. 依存パッケージのインストール

PostgreSQL を使う場合（本番・ローカル）:

```bash
pip install -r requirements.txt
```

SQLite で動かす場合（PythonAnywhere など）:

```bash
pip install -r requirements-pythonanywhere.txt
```

### 3. `.env` の作成

プロジェクト直下に `.env` を作成します（次節の[環境変数](#環境変数)を参照）。`.env` は `.gitignore` により Git 管理外です。

---

## 環境変数

`.env` に以下を設定します。ランダム文字列は `python -c "import secrets; print(secrets.token_urlsafe(32))"` で生成できます。

| 変数名 | 必須 | 説明 |
| --- | --- | --- |
| `SECRET_KEY` | 本番で必須 | セッション・CSRF トークンの署名鍵（長いランダム文字列） |
| `ADMIN_USERNAME` | ○ | 管理者のログインユーザー名 |
| `ADMIN_PASSWORD` | ○ | 管理者パスワード（平文・ハッシュ済みどちらも可） |
| `ADMIN_LOGIN_PATH` | ○ | ログインページの URL パス（推測されにくい文字列） |
| `ADMIN_GATE_KEY` | ○ | ログインページを表示するための合言葉（長いランダム文字列） |
| `FLASK_ENV` | 本番で推奨 | `production` にすると本番モード（Secure Cookie 等）が有効になる |
| `USE_SQLITE` | 任意 | `1` で SQLite を使用（`instance/blog.db`） |
| `DATABASE_URL` | 任意 | 明示指定時に最優先で使われる DB 接続 URL |
| `LOG_LEVEL` | 任意 | ログ出力レベル（未設定時は本番 INFO / 開発 DEBUG） |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 任意 | ローカル PostgreSQL（docker-compose）接続用 |

**DB 接続先の優先順位**: `DATABASE_URL` → `USE_SQLITE=1`（`instance/blog.db`）→ ローカル PostgreSQL（`localhost:15432`）。

> ⚠️ SQLite 運用でも Secure Cookie などを有効化するため、本番では `FLASK_ENV=production` を設定してください（`DATABASE_URL` 未設定だと自動では本番判定になりません）。

---

## データベースの初期化

### マイグレーションを使う場合（PostgreSQL 推奨）

```bash
flask db upgrade
```

管理者ユーザーは別途作成が必要です。

### マイグレーション不要の一括初期化（SQLite 向け）

テーブル作成と管理者ユーザー登録を同時に行います。何度実行しても安全です。

```bash
python init_db.py
```

このスクリプトは `db.create_all()` でテーブルを作成し、Alembic の履歴を最新（head）にスタンプしたうえで、`.env` の管理者ユーザーを登録します。

---

## 起動方法

### ローカル PostgreSQL を使う場合

```bash
docker compose up -d      # localhost:15432 で PostgreSQL を起動
python app.py
```

デバッグモードで起動するには `FLASK_DEBUG=1`（かつ本番判定でないこと）を設定します。

### SQLite で手軽に起動する場合

`.env` に `USE_SQLITE=1` を設定してから:

```bash
python init_db.py
python app.py
```

起動後、`http://127.0.0.1:5000` にアクセスします。

### 管理画面へのログイン

ログイン URL は隠蔽されています。次の手順でアクセスします。

1. 合言葉付き URL を開く: `http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>`
2. 合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされます
3. `ADMIN_USERNAME` と `ADMIN_PASSWORD` でログインします

---

## 管理コマンド

記事本文のキャッシュ HTML を再生成するコマンドが用意されています。`rendering.py` を変更して `RENDER_VERSION` を +1 した後などに使います。

```bash
flask rerender-posts            # 未生成または旧バージョンの記事だけ再生成
flask rerender-posts --all      # 全記事を強制的に再生成
flask rerender-posts --dry-run  # 対象件数を確認するだけ（保存しない）
```

実行前に `FLASK_APP=app.py` を設定するか、プロジェクト直下で実行してください。

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用）への GitHub 経由でのデプロイ手順は、リポジトリ内の [`deploy_pythonanywhere.md`](./deploy_pythonanywhere.md) に詳しくまとめてあります。WSGI 設定のサンプルは [`wsgi_pythonanywhere.py`](./wsgi_pythonanywhere.py) を参照してください。

基本的な更新フローは「**PC で修正 → GitHub に push → サーバーで pull → Web タブで Reload**」です。

---

## ライセンス

個人利用・学習目的のプロジェクトです。