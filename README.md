# MITO Blog

Flask 製の個人ブログアプリケーションです。Markdown での記事投稿、画像・地図・YouTube の埋め込み、ハッシュタグ検索、ダークモードなどを備え、**単一管理者による運用**を前提に設計されています。学習用に作られており、認証まわりのセキュリティ設計・DB のインデックス設計・レンダリングのキャッシュなど、実運用を意識した工夫が随所に入っています。

Application Factory パターン（`create_app()`）を採用し、PostgreSQL（本番・ローカル）と SQLite（無料ホスティング）の両方で動作します。

---

## 目次

- [MITO Blog](#mito-blog)
  - [目次](#目次)
  - [主な機能](#主な機能)
    - [閲覧者向け（誰でも利用可能）](#閲覧者向け誰でも利用可能)
    - [管理者向け（ログイン必須）](#管理者向けログイン必須)
  - [パフォーマンス最適化](#パフォーマンス最適化)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ（ローカル開発）](#セットアップローカル開発)
    - [1. リポジトリの取得と依存インストール](#1-リポジトリの取得と依存インストール)
    - [2. 環境変数（`.env`）の作成](#2-環境変数envの作成)
    - [3. データベースの用意](#3-データベースの用意)
    - [4. 起動](#4-起動)
    - [5. 管理者ログイン](#5-管理者ログイン)
  - [環境変数一覧](#環境変数一覧)
  - [管理コマンド（Flask CLI）](#管理コマンドflask-cli)
  - [デプロイ](#デプロイ)
  - [ライセンス](#ライセンス)

---

## 主な機能

### 閲覧者向け（誰でも利用可能）

- **記事一覧（トップページ）**: 公開記事を新着順に表示。1 ページ 4 件のページ送り（ページ番号ナビ付き）。
- **キーワード検索 × ジャンル絞り込み**: タイトル・ハッシュタグ名の部分一致検索と、ジャンル選択を組み合わせて絞り込み可能。
- **ハッシュタグ絞り込み**: ジャンル選択中に、そのジャンル内で使われているタグでさらに細かく絞り込み。
- **記事詳細ページ**: Markdown 本文を HTML 表示。以下の独自機能をサポート。
  - `[toc]` による目次の自動生成
  - `[imgN]` による本文中への画像埋め込み（キャプション対応）
  - `[map:場所名]` による Google マップの埋め込み
  - `[youtube:URL]` による YouTube 動画の埋め込み（サムネイルをクリックすると再生が始まる軽量な「ファサード」方式）
- **関連記事の表示**: 記事末尾に最大 4 件。「同ジャンル×同タグ → 同タグ → 同ジャンル → 最新」の優先順位で自動選定。
- **ジャンル一覧ページ**: カテゴリごとのアコーディオン表示。
- **自己紹介・使い方ページ**: 静的な案内ページ。
- **サイト統計**: 総投稿数・ハッシュタグ数・最終更新日をトップに表示。
- **ダークモード**: ワンタップで切り替え、選択は次回訪問時も保持（localStorage）。
- **レスポンシブ対応**: スマホではドロワーメニュー、スクロール連動でのヘッダー表示／非表示に対応。
- **SEO 対応**: `robots.txt` / `sitemap.xml` の配信、記事ごとの OGP・Twitter Card メタタグ出力。

### 管理者向け（ログイン必須）

- **記事の投稿・編集・削除**: Markdown 用のツールバー（見出し・太字・目次・リスト・地図・YouTube・画像挿入）付きエディタ。
- **公開設定の切り替え**: 記事ごとに「全体公開／非公開」をトグル。非公開記事は管理者本人のみ閲覧可能。
- **画像アップロード**: 複数枚の一括／個別追加に対応。アップロード時に自動で最適化（EXIF 回転補正・長辺 1200px までの縮小・再圧縮）。
- **サムネイル管理**: 専用サムネイルのアップロード、またはプリセットからのデフォルトサムネイル選択。専用サムネイルは軽量な WebP に自動変換。
- **ハッシュタグ入力**: スペース・カンマ区切りで複数入力（`#` は省略可）。入力中のリアルタイムプレビュー付き。使われなくなったタグは自動で掃除。
- **マイページ**: 自分の投稿一覧（ページ送り付き）、総投稿数、使用ジャンル一覧の確認、ニックネーム変更。
- **ジャンルの新規作成**: 投稿・編集フォームから独自ジャンルを追加可能。

---

## パフォーマンス最適化

- **本文 HTML のキャッシュ**: 記事本文の Markdown 変換結果を `body_html` / `toc_html` に保存し、閲覧のたびの再変換を回避。レンダラのバージョン（`RENDER_VERSION`）による一括再生成の仕組み付き。
- **DB インデックス**: 一覧・検索・詳細の主要クエリに合わせた単体・複合インデックスを整備。PostgreSQL では `pg_trgm` の GIN インデックスで部分一致検索を高速化。
- **N+1 の回避**: `joinedload` / `selectinload` による関連データの先読み。
- **静的ファイルのキャッシュバスティング**: `static_url()` が更新時刻（mtime）をクエリに付与し、長期キャッシュと即時反映を両立。
- **画像の遅延読み込み**: `loading="lazy"` の付与と、レイアウトシフト（CLS）防止のための幅・高さ指定。
- **重いライブラリの遅延 import**: Pillow などをリクエスト時にのみ読み込み、起動時間とベースメモリを節約。

---

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.x（Application Factory パターン） |
| ORM / DB | SQLAlchemy 2.0 / PostgreSQL・SQLite |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF | Flask-WTF |
| 画像処理 | Pillow / filetype |
| 本文変換 | Markdown |
| フロントエンド | Jinja2 テンプレート・素の CSS / JavaScript |

---

## ディレクトリ構成

```
.
├── app.py               # エントリーポイント（create_app・ログ・CLI・エラーハンドラ）
├── config.py            # .env の読み込み・設定値の提供
├── constants.py         # ジャンル定義（唯一の情報源）
├── extensions.py        # db / login_manager / migrate インスタンス
├── models.py            # User / Post / Hashtag のテーブル定義
├── rendering.py         # 本文（Markdown + 独自タグ）→ HTML 変換
├── init_db.py           # SQLite 向けのDB初期化スクリプト
├── views/               # ルート（Blueprint）
│   ├── auth.py          #   ログイン・ログアウト
│   ├── blog.py          #   公開ページ（一覧・詳細・ジャンル・SEO）
│   └── admin.py         #   管理者ページ（投稿・編集・削除・マイページ）
├── services/            # ドメインロジック層
│   ├── images.py        #   画像の検証・最適化・保存・削除
│   ├── hashtags.py      #   ハッシュタグの解析・同期・掃除
│   └── captions.py      #   画像キャプションの取得
├── templates/           # Jinja2 テンプレート
├── static/              # CSS / JS / 画像
├── migrations/          # Alembic マイグレーション
├── docker-compose.yml   # ローカル開発用 PostgreSQL
└── requirements.txt     # 依存パッケージ
```

---

## セットアップ（ローカル開発）

### 1. リポジトリの取得と依存インストール

```bash
git clone <このリポジトリのURL>
cd <プロジェクトディレクトリ>
python -m venv .venv
source .venv/bin/activate      # Windows は .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 環境変数（`.env`）の作成

プロジェクト直下に `.env` を作成します。

```bash
# 認証（必須）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ここにパスワード（平文またはハッシュ）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx
ADMIN_GATE_KEY=ランダムな長い文字列

# セッション署名
SECRET_KEY=別のランダムな長い文字列

# ローカル PostgreSQL（docker-compose 利用時）
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=blogpass
POSTGRES_DB=blogdb
```

ランダム文字列は次のコマンドで生成できます（`SECRET_KEY` と `ADMIN_GATE_KEY` には別々の値を使ってください）。

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. データベースの用意

**PostgreSQL（Docker）を使う場合:**

```bash
docker compose up -d          # localhost:15432 で PostgreSQL が起動
flask db upgrade              # マイグレーションを適用
```

**SQLite で手軽に試す場合:**

`.env` に `USE_SQLITE=1` を追加してから、

```bash
python init_db.py             # テーブル作成＋管理者ユーザー作成を一括実行
```

### 4. 起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` を開きます。

### 5. 管理者ログイン

隠蔽されたログイン URL に、合言葉付きでアクセスします。

```
http://localhost:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされます。以降は `ADMIN_USERNAME` / `ADMIN_PASSWORD` でログインできます。

---

## 環境変数一覧

| キー | 必須 | 説明 |
| --- | --- | --- |
| `ADMIN_USERNAME` | ○ | 管理者ログインのユーザー名 |
| `ADMIN_PASSWORD` | ○ | ログインパスワード（平文可。初期化時にハッシュ化） |
| `ADMIN_LOGIN_PATH` | ○ | ログイン画面の URL パス（推測されにくい文字列） |
| `ADMIN_GATE_KEY` | ○ | ログイン画面を表示するための合言葉 |
| `SECRET_KEY` | 本番必須 | セッション・CSRF 署名用の秘密鍵（本番では未設定だと起動停止） |
| `DATABASE_URL` | 任意 | DB 接続 URL（指定時は最優先） |
| `USE_SQLITE` | 任意 | `1` で SQLite（`instance/blog.db`）を使用 |
| `FLASK_ENV` | 任意 | `production` で本番モード（Secure Cookie 等が有効） |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 任意 | ローカル PostgreSQL 接続情報 |
| `LOG_LEVEL` | 任意 | ログ出力レベル（既定: 本番 INFO / 開発 DEBUG） |
| `FLASK_DEBUG` | 任意 | `1` でデバッグモード（本番では無効） |

---

## 管理コマンド（Flask CLI）

```bash
# 本文キャッシュ HTML の再生成（rendering.py 変更後に使用）
flask rerender-posts           # 古いバージョンの記事だけ再生成
flask rerender-posts --all     # 全記事を強制再生成
flask rerender-posts --dry-run # 対象を表示するだけ（保存しない）

# どの記事からも参照されていない孤児画像ファイルの掃除
flask clean-orphan-images           # 一覧表示のみ
flask clean-orphan-images --delete  # 実際に削除

# マイグレーション
flask db migrate -m "変更内容"   # モデル変更から差分を検出
flask db upgrade                 # DB に適用
```

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用）への GitHub 経由でのデプロイ手順は、`deploy_pythonanywhere.md` に詳しくまとめてあります。初回セットアップから公開後の更新フロー、トラブルシューティングまで記載しています。

---

## ライセンス

学習・個人利用を目的としたプロジェクトです。

