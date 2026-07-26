# MITO Blog

Flask 製の個人用ブログアプリケーション。Markdown で記事を書き、地図・YouTube・画像を埋め込みながら、ハッシュタグやジャンルで整理・検索できる。管理者ひとりで運用する構成を想定し、ログイン URL の隠蔽やブルートフォース対策などのセキュリティ機構を備える。

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
    - [3. 環境変数の設定](#3-環境変数の設定)
    - [4. ローカル PostgreSQL の起動（任意）](#4-ローカル-postgresql-の起動任意)
  - [データベースの初期化](#データベースの初期化)
    - [マイグレーションを使う場合（PostgreSQL 推奨）](#マイグレーションを使う場合postgresql-推奨)
    - [マイグレーションを使わない場合（SQLite）](#マイグレーションを使わない場合sqlite)
  - [起動](#起動)
    - [ローカル開発](#ローカル開発)
    - [本番](#本番)
  - [管理コマンド](#管理コマンド)
    - [本文 HTML の再生成](#本文-html-の再生成)
    - [孤児画像ファイルの掃除](#孤児画像ファイルの掃除)
  - [環境変数](#環境変数)
  - [デプロイ](#デプロイ)
  - [セキュリティ上の設計メモ](#セキュリティ上の設計メモ)
  - [ライセンス](#ライセンス)

---

## 特徴

- **Application Factory パターン**（`create_app()`）で構成され、テストや環境切り替えがしやすい。
- **PostgreSQL と SQLite の両対応**。ローカル・本番は PostgreSQL、無料ホスティング（PythonAnywhere など）は SQLite に切り替えられる。
- **本文 HTML のキャッシュ機構**。Markdown と独自タグの変換を投稿・編集時に一度だけ行い、閲覧のたびの再変換をなくしている。レンダラのバージョン管理により、変換ロジックを更新すると既存記事も自動で作り直される。
- **画像の自動最適化**。アップロード時に Pillow で縮小・再圧縮し、サムネイルは WebP に変換して転送量を抑える。
- **ダークモード**とレスポンシブ対応で、PC・スマートフォンのどちらでも見やすい。

---

## 主な機能

### 閲覧者向けの機能

| 機能 | 説明 |
| --- | --- |
| 記事一覧（トップページ） | 公開記事を新着順に表示。ページ番号によるページ送りに対応。 |
| キーワード × ジャンル検索 | タイトル・ハッシュタグ名の部分一致検索と、ジャンル絞り込みを組み合わせられる。 |
| ハッシュタグ絞り込み | ジャンル選択中に、そのジャンル内で使われているタグで記事をさらに絞り込める。 |
| 記事詳細ページ | Markdown で書かれた本文を整形表示。見出しからの目次（TOC）、画像とキャプション、Google マップ埋め込み、YouTube 埋め込み（サムネイルをタップして再生するファサード形式）に対応。 |
| 関連記事 | 記事末尾に「同じジャンル × 同じタグ → 同じタグ → 同じジャンル → 最新」の優先順位で最大 4 件を表示。 |
| ジャンル一覧 | カテゴリごとにグループ化したアコーディオン形式でジャンルを一覧表示。 |
| サイト統計 | 総投稿数・使用ハッシュタグ数・最終更新日をトップページに表示。 |
| 自己紹介 / 使い方ページ | 管理者のプロフィールとブログの使い方を紹介する静的ページ。 |
| ダークモード | 🌙 / ☀️ ボタンでテーマを切り替え、選択内容はブラウザに保存される。 |
| レスポンシブ表示 | スマートフォンではドロワーメニューやスクロール連動ヘッダーなど、モバイル向けに最適化された UI で表示。 |

### 管理者向けの機能

| 機能 | 説明 |
| --- | --- |
| 隠しログイン | ログイン URL を環境変数で隠蔽（秘密のパス）。さらに「ゲートキー（合言葉）」の Cookie を持たない訪問者にはページの存在自体を 404 で隠す多層防御。 |
| ブルートフォース対策 | 連続ログイン失敗が一定回数を超えると、一定時間ログインをロックアウトする。 |
| 記事の投稿 | Markdown ツールバー（見出し・太字・目次・リスト）、画像の一括／個別アップロードとプレビュー、地図・YouTube 挿入モーダル、ハッシュタグ入力、サムネイル指定、公開／非公開の切り替えに対応。 |
| 記事の編集 | 既存画像のキャプション編集・個別削除、画像の差し替え・追加、サムネイルの変更・削除、ジャンルやタグの更新に対応。 |
| 記事の削除 | CSRF トークン付きの POST でのみ実行可能。関連する画像ファイルも安全に物理削除する。 |
| マイページ | 自分の投稿一覧（ページ送り対応）、総投稿数、使用ジャンルの一覧を表示。ニックネームの変更もここで行う。 |
| 非公開記事の閲覧 | 非公開に設定した記事は、投稿者本人がログイン中のときだけ一覧・詳細で確認できる。 |

---

## 技術スタック

- **言語 / 実行環境**: Python 3.10
- **フレームワーク**: Flask
- **ORM**: Flask-SQLAlchemy（SQLAlchemy 2.0）
- **マイグレーション**: Flask-Migrate（Alembic）
- **認証**: Flask-Login
- **フォーム保護**: Flask-WTF（CSRF）
- **画像処理**: Pillow
- **ファイル検証**: filetype（MIME 判定による拡張子偽装の検出）
- **Markdown 変換**: Markdown（`toc` / `nl2br` 拡張）
- **データベース**: PostgreSQL（本番・ローカル）/ SQLite（無料ホスティング）
- **その他**: python-dotenv、pytz、Werkzeug（ProxyFix・パスワードハッシュ）

---

## ディレクトリ構成

```
.
├── app.py                  # エントリーポイント（create_app / ログ設定 / CLI / エラーハンドラ）
├── config.py               # .env からの環境変数読み込み
├── constants.py            # ジャンル定義（唯一の情報源）
├── extensions.py           # db / login_manager / migrate インスタンスの置き場
├── models.py               # テーブル定義（User / Post / Hashtag / 中間テーブル）
├── rendering.py            # 本文（Markdown + 独自タグ）→ HTML 変換
├── init_db.py              # SQLite 向けの DB 初期化スクリプト
├── views/
│   ├── blog.py             # 一般公開ページ（一覧・詳細・ジャンル・about・howto）
│   ├── admin.py            # 管理者ページ（投稿・編集・削除・マイページ）
│   └── auth.py             # ログイン・ログアウト
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # ページ別スタイル + ダークモード
│   ├── js/                 # base.js / editor.js / mobile-editor.js
│   ├── img/                # 投稿画像・サムネイル・favicon
│   └── favicon/
├── migrations/             # Alembic マイグレーション
├── requirements.txt                 # PostgreSQL を含む依存一覧
├── requirements-pythonanywhere.txt  # SQLite 運用向けの依存一覧
├── docker-compose.yml      # ローカル開発用 PostgreSQL
└── deploy_pythonanywhere.md # PythonAnywhere へのデプロイ手順書
```

---

## セットアップ

### 1. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリの URL>
cd <プロジェクトディレクトリ>

python -m venv .venv
source .venv/bin/activate      # Windows は .venv\Scripts\activate
```

### 2. 依存パッケージのインストール

PostgreSQL を使う場合（ローカル開発・本番）:

```bash
pip install -r requirements.txt
```

SQLite で動かす場合（PythonAnywhere など）:

```bash
pip install -r requirements-pythonanywhere.txt
```

### 3. 環境変数の設定

プロジェクト直下に `.env` を作成する（[環境変数](#環境変数) の節を参照）。

### 4. ローカル PostgreSQL の起動（任意）

ローカルで PostgreSQL を使う場合は Docker Compose を利用できる。

```bash
docker compose up -d
```

`localhost:15432` に PostgreSQL が起動する。

---

## データベースの初期化

### マイグレーションを使う場合（PostgreSQL 推奨）

```bash
flask db upgrade
```

`migrations/` のリビジョンが順に適用され、`models.py` と一致するスキーマが構築される。

### マイグレーションを使わない場合（SQLite）

テーブル作成と管理者ユーザーの登録を一括で行うスクリプトを実行する。

```bash
python init_db.py
```

何度実行しても安全で、既にテーブルや管理者ユーザーがあればスキップする。Alembic の履歴も最新（head）にスタンプされるため、後からマイグレーション運用へ移行しても整合が取れる。

---

## 起動

### ローカル開発

```bash
python app.py
```

`FLASK_DEBUG=1`（かつ本番以外）のときのみデバッグモードで起動する。

### 本番

本番では WSGI サーバーから `create_app()` を呼び出して公開する。PythonAnywhere での具体的な設定は `deploy_pythonanywhere.md` を参照。

---

## 管理コマンド

`flask <コマンド名>` で実行できる運用コマンドを備える。

### 本文 HTML の再生成

`rendering.py` を修正したあと、既存記事のキャッシュ HTML を作り直す。

```bash
flask rerender-posts            # 古いバージョンの記事だけ再生成
flask rerender-posts --all      # 全記事を強制的に再生成
flask rerender-posts --dry-run  # 対象を表示するだけ（保存しない）
```

> `rendering.py` の出力を変更したら、`RENDER_VERSION` を +1 しておく。閲覧時にも自動でバックフィルされるが、このコマンドでまとめて更新できる。

### 孤児画像ファイルの掃除

どの記事からも参照されていない画像ファイルを一覧・削除する。

```bash
flask clean-orphan-images           # 孤児を一覧表示するだけ
flask clean-orphan-images --delete  # 実際に削除する
```

---

## 環境変数

`.env` に以下を設定する。

| キー | 必須 | 説明 |
| --- | --- | --- |
| `SECRET_KEY` | 本番で必須 | セッション・CSRF トークンの署名鍵。長いランダム文字列を指定する。 |
| `ADMIN_USERNAME` | ○ | 管理者ログインのユーザー名。 |
| `ADMIN_PASSWORD` | ○ | 管理者パスワード（平文・ハッシュ済みのどちらでも可）。 |
| `ADMIN_LOGIN_PATH` | ○ | ログインページの URL パス（推測されにくい文字列）。未設定だと起動しない。 |
| `ADMIN_GATE_KEY` | ○ | ログインページを表示するための合言葉。未設定だとログインページは常に 404。 |
| `FLASK_ENV` | 本番で推奨 | `production` を指定すると本番モード（Secure Cookie・SECRET_KEY 必須化）になる。SQLite 運用でも本番なら設定する。 |
| `USE_SQLITE` | 任意 | `1` にすると `instance/blog.db` を SQLite として使う。 |
| `DATABASE_URL` | 任意 | 明示指定すると最優先で使われる（PostgreSQL / SQLite どちらも可）。 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 任意 | ローカルの PostgreSQL に接続する場合のみ必要。 |
| `LOG_LEVEL` | 任意 | ログ出力レベル（未設定なら本番 `INFO` / 開発 `DEBUG`）。 |

**ランダム文字列の生成例:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`SECRET_KEY` と `ADMIN_GATE_KEY` にはそれぞれ別の値を使う。

**ログイン方法:** ログイン画面は隠蔽されているため、初回は合言葉付きの URL でアクセスする。

```
https://<ホスト>/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされる。以降はユーザー名とパスワードでログインする。

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用）への公開手順・更新運用・トラブルシューティングは `deploy_pythonanywhere.md` に詳しくまとめてある。基本の更新フローは次のとおり。

```
[PC] コード修正 → git push → [サーバー] git pull → Web タブで Reload
```

- ライブラリを追加したときは、pull 後に `pip install -r requirements-pythonanywhere.txt` を実行する。
- `models.py`（DB 構造）を変更したときは、動作確認用途であれば `instance/blog.db` を削除して `python init_db.py` で作り直すのが手軽（投稿データは消える）。

---

## セキュリティ上の設計メモ

- ログイン URL の隠蔽 + ゲートキー Cookie + ユーザー名 + パスワードの多層防御。いずれかが欠けると管理画面に到達できない。
- 未ログインで管理者用ページへアクセスした場合は、ログイン画面へ誘導せず 404 を返して存在を隠す。
- アップロード画像は拡張子と MIME タイプの二層で検証し、拡張子を偽装したファイルを弾く。
- 全フォームに CSRF トークンを強制。`X-Content-Type-Options` などのセキュリティヘッダーを付与し、リバースプロキシ配下でも `ProxyFix` で HTTPS を正しく判定する。
  
---

## ライセンス

個人利用・学習目的のプロジェクトです。