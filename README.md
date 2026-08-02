# MITO Blog

Flask 製の個人用ブログアプリです。記事の投稿・編集・公開に加え、Markdown 記法・独自タグ（地図 / YouTube / 画像キャプション）による表現、ハッシュタグやジャンルでの絞り込み、ダークモード対応などを備えています。学習用途を想定し、コードには処理の流れが追える日本語コメントを付けています。

本番（PostgreSQL）と無料ホスティング（SQLite）の両方で動作するよう設計されています。

---

## 目次

- [MITO Blog](#mito-blog)
  - [目次](#目次)
  - [主な機能](#主な機能)
    - [閲覧者向けの機能（公開ページ）](#閲覧者向けの機能公開ページ)
    - [管理者向けの機能（ログイン必須）](#管理者向けの機能ログイン必須)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ](#セットアップ)
    - [環境変数（.env）](#環境変数env)
    - [ローカル開発（PostgreSQL）](#ローカル開発postgresql)
    - [SQLite で動かす場合](#sqlite-で動かす場合)
  - [管理コマンド](#管理コマンド)
  - [デプロイ](#デプロイ)
  - [ライセンス](#ライセンス)

---

## 主な機能

### 閲覧者向けの機能（公開ページ）

誰でもログインなしで利用できる機能です。

- **記事一覧・ページ送り** — トップページで公開記事を新着順に表示。サーバーサイドのページネーションに対応しています。
- **キーワード検索** — タイトルとハッシュタグ名を対象とした部分一致検索。PostgreSQL では pg_trgm のトリグラム索引を使い、部分一致でも高速に検索できます。
- **ジャンル絞り込み** — ジャンル単位で記事を絞り込み。ジャンル一覧ページはカテゴリごとのアコーディオン表示です。
- **ハッシュタグ絞り込み** — ジャンル選択中に、そのジャンル内で使われているタグでさらに絞り込めます。
- **記事詳細ページ** — 以下の表現に対応しています。
  - Markdown 記法（見出し・太字・箇条書きなど）
  - 目次の自動生成（記事冒頭表示、または本文中の `[toc]` 位置に展開）
  - 本文中への画像埋め込みとキャプション表示
  - Google マップの埋め込み（`[map:場所名]`）
  - YouTube 動画の埋め込み（サムネイルをタップして再生するファサード方式）
- **関連記事の表示** — 記事末尾に、同じジャンル・同じタグを優先して最大 4 件を表示します。
- **サイト統計** — トップページで総投稿数・ハッシュタグ種類数・最終更新日を表示します。
- **自己紹介 / 使い方ページ** — 管理者プロフィールとブログの使い方を掲載する静的ページ。
- **ダークモード切り替え** — 🌙 / ☀️ ボタンで切り替え。選択内容はブラウザに保存され、次回訪問時も維持されます。
- **レスポンシブ対応** — スマホではハンバーガーメニューによるドロワーナビ、スクロール連動のヘッダー表示/非表示に対応。
- **SEO 対応** — ページごとの `<title>` と OGP / Twitter Card メタタグ、`robots.txt`、`sitemap.xml`（公開記事のみ収録）を配信します。

### 管理者向けの機能（ログイン必須）

管理者としてログインした場合のみ利用できる機能です。

- **記事の投稿** — タイトル・本文・ジャンル・ハッシュタグ・公開設定を指定して投稿できます。
- **記事の編集** — 既存記事の内容・画像・キャプション・サムネイルをまとめて編集できます。
- **記事の削除** — CSRF トークン付きの POST でのみ削除でき、関連画像も物理削除されます。
- **Markdown エディタツールバー** — H2/H3 見出し・太字・目次・箇条書き（自動継続対応）・地図挿入・YouTube 挿入・画像挿入をボタン操作で入力できます。スマホでは編集ツールバーがキーボード直上に固定表示されます。
- **画像アップロードと自動最適化** — 本文画像は Pillow で長辺 1200px に縮小・再圧縮して保存。複数まとめて選択・1 枚ずつ追加の両方に対応し、各画像にキャプションを付けられます。
- **サムネイルの管理** — 記事一覧に表示するサムネイルを、専用画像のアップロード（WebP 縮小版で保存）／プリセットから選択／システム既定、の優先順位で設定できます。
- **ハッシュタグ入力** — スペース・カンマ区切りで複数入力でき、入力しながらタグのプレビューが表示されます。使われなくなった孤立タグは自動で掃除されます。
- **公開 / 非公開の切り替え** — 記事単位で公開状態を切り替え。非公開記事は管理者本人だけが閲覧できます。
- **マイページ** — 自分の投稿一覧（ページ送り付き）、総投稿数、使用ジャンルの確認、ニックネーム変更を行えます。

---

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| 言語 | Python 3.10 |
| フレームワーク | Flask（Application Factory パターン） |
| ORM / マイグレーション | SQLAlchemy 2.0 / Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム保護 | Flask-WTF（CSRF） |
| テンプレート | Jinja2 |
| 画像処理 | Pillow / filetype |
| 本文変換 | Markdown |
| データベース | PostgreSQL（本番・ローカル） / SQLite（無料枠） |
| フロントエンド | 素の HTML / CSS / JavaScript（ビルド不要） |

---

## ディレクトリ構成

```
.
├── app.py                    # エントリーポイント（create_app ファクトリ）
├── config.py                 # 環境変数の読み込み
├── constants.py              # ジャンル定義（唯一の情報源）
├── extensions.py             # db / login_manager / migrate のインスタンス
├── models.py                 # User / Post / Hashtag のテーブル定義
├── rendering.py              # 本文（Markdown + 独自タグ）→ HTML 変換
├── init_db.py                # SQLite 用のDB初期化スクリプト
│
├── views/                    # Blueprint（ルート定義）
│   ├── auth.py               #   ログイン・ログアウト
│   ├── blog.py               #   一般公開ページ（一覧・詳細・ジャンル・SEO）
│   └── admin.py              #   管理者専用（投稿・編集・削除・マイページ）
│
├── services/                 # ドメインロジック層
│   ├── images.py             #   画像の検証・最適化・保存・削除
│   ├── hashtags.py           #   ハッシュタグの解析・同期・掃除
│   └── captions.py           #   画像キャプションのフォーム取得
│
├── templates/                # Jinja2 テンプレート
├── static/                   # CSS / JS / 画像・favicon
├── migrations/               # Alembic マイグレーション
│
├── requirements.txt          # 依存パッケージ（PostgreSQL 含む）
└── requirements-pythonanywhere.txt  # SQLite 運用向け（psycopg 除外）
```

---

## セットアップ

### 環境変数（.env）

プロジェクト直下に `.env` を作成します（`.gitignore` 済み）。

```dotenv
# --- 共通（必須） ---
SECRET_KEY=ランダムな長い文字列
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ログインパスワード（平文でもハッシュ済みでも可）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx   # ログイン画面の秘密URLパス
ADMIN_GATE_KEY=別のランダムな長い文字列    # ログイン画面を表示する合言葉

# --- 本番運用（SQLite でも本番なら設定） ---
FLASK_ENV=production

# --- SQLite を使う場合 ---
USE_SQLITE=1

# --- ローカル PostgreSQL（docker-compose）を使う場合 ---
POSTGRES_USER=blog_user
POSTGRES_PASSWORD=blog_password
POSTGRES_DB=blog_db
```

ランダム文字列は次のコマンドで生成できます（`SECRET_KEY` と `ADMIN_GATE_KEY` には別々の値を使ってください）。

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

主な変数の意味は次のとおりです。

| 変数 | 説明 |
| --- | --- |
| `SECRET_KEY` | セッション・CSRF トークンの署名に使う秘密鍵。本番では未設定だと起動時に停止します。 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理者ログインのユーザー名・パスワード。 |
| `ADMIN_LOGIN_PATH` | ログイン画面の URL パス（推測されにくい文字列）。未設定だと起動できません。 |
| `ADMIN_GATE_KEY` | ログイン画面を表示するための合言葉。 |
| `FLASK_ENV` | `production` にすると本番扱いになり、Secure Cookie 有効化・SECRET_KEY 必須化が行われます。 |
| `USE_SQLITE` | `1` にすると `instance/blog.db`（SQLite）を使用します。 |

### ローカル開発（PostgreSQL）

依存パッケージのインストール：

```bash
python -m venv .venv
source .venv/bin/activate        # Windows は .venv\Scripts\activate
pip install -r requirements.txt
```

`docker-compose.yml` の PostgreSQL を起動（ホスト側ポートは 15432）：

```bash
docker compose up -d
```

マイグレーションを適用して起動：

```bash
flask db upgrade
python app.py
```

`DATABASE_URL` も `USE_SQLITE` も未設定のとき、`localhost:15432` のローカル PostgreSQL に接続します。デバッグモードは `FLASK_DEBUG=1` を設定したローカル環境でのみ有効になります。

### SQLite で動かす場合

マイグレーション不要で、テーブル作成と管理者ユーザー登録を一括で行えます。

```bash
pip install -r requirements-pythonanywhere.txt
python init_db.py
```

`.env` に `USE_SQLITE=1` と `FLASK_ENV=production` を設定しておいてください。`init_db.py` は何度実行しても安全です（既存テーブル・ユーザーはスキップされます）。

---

## 管理コマンド

`flask <コマンド名>` で実行できる運用コマンドがあります。

| コマンド | 説明 |
| --- | --- |
| `flask rerender-posts` | 本文キャッシュ HTML が古いバージョンの記事だけを再生成します。 |
| `flask rerender-posts --all` | 全記事の本文 HTML を強制的に再生成します。 |
| `flask rerender-posts --dry-run` | 再生成の対象を表示するだけで保存しません。 |
| `flask clean-orphan-images` | どの記事からも参照されていない孤児画像を一覧表示します。 |
| `flask clean-orphan-images --delete` | 孤児画像を実際に削除します。 |

記事本文の HTML は投稿・編集時に生成して DB にキャッシュしています。`rendering.py` の出力を変更したときは、`rendering.py` の `RENDER_VERSION` を `+1` してください。既存記事も次のアクセス時に自動で作り直されます（`flask rerender-posts` で一括更新も可能）。

---

## デプロイ

PythonAnywhere（無料枠・SQLite 運用）への手順は `deploy_pythonanywhere.md` に詳細をまとめています。要点は以下のとおりです。

1. GitHub からサーバーへ `git clone`
2. 仮想環境を作成し `requirements-pythonanywhere.txt` をインストール
3. サーバー上に `.env` を作成（`USE_SQLITE=1` / `FLASK_ENV=production` を含める）
4. `python init_db.py` でテーブルと管理者ユーザーを作成
5. Web タブで Manual configuration（WSGI から `create_app()` を呼び出し）を設定して Reload

コードを更新したときは「PC で修正 → GitHub に push → サーバーで pull → **Web タブで Reload**」が基本の流れです。静的ファイルは `static_url()` によるキャッシュバスティングに対応しているため、CSS/JS を更新すればブラウザにも即座に反映されます。

---

## ライセンス

学習・個人利用を目的としたプロジェクトです。

