# MITO Blog

Flask 製の個人用ブログアプリケーションです。記事の投稿・編集・公開を管理者が行い、閲覧者はジャンルやハッシュタグ、キーワードで記事を探して読むことができます。Markdown での執筆に加え、画像・地図・YouTube 動画の埋め込み、ダークモード、レスポンシブ対応など、個人ブログに必要な機能を一通り備えています。

Application Factory パターン（`create_app()`）で構成され、本番は PostgreSQL、PythonAnywhere 無料枠などでは SQLite と、環境変数だけで接続先を切り替えられる設計です。

---

## 目次

- [MITO Blog](#mito-blog)
  - [目次](#目次)
  - [主な機能](#主な機能)
    - [閲覧者向けの機能](#閲覧者向けの機能)
    - [管理者向けの機能](#管理者向けの機能)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セキュリティ設計](#セキュリティ設計)
  - [セットアップ（ローカル開発）](#セットアップローカル開発)
  - [環境変数](#環境変数)
  - [本番デプロイ](#本番デプロイ)
  - [ライセンス](#ライセンス)

---

## 主な機能

機能を「誰が使うか」で二つに分けて整理します。閲覧者は誰でも利用でき、管理者機能はログインした管理者のみが利用できます。

### 閲覧者向けの機能

記事を探して読むための、公開ページ側の機能です。

- **記事一覧（トップページ）** — 公開記事を新しい順に表示。1 ページ 4 件のサーバーサイドページネーションに対応。
- **キーワード検索** — 記事タイトルとハッシュタグ名を対象に部分一致で検索。
- **ジャンル絞り込み** — ジャンルを選んで該当記事だけを表示。ジャンル選択中は、そのジャンル内で使われているハッシュタグでさらに絞り込み可能。
- **ハッシュタグ絞り込み** — タグをタップしてジャンル×タグの複合絞り込みができる。
- **記事詳細ページ** — Markdown で書かれた本文を HTML に変換して表示。目次（TOC）・画像＋キャプション・地図・YouTube 動画の埋め込みに対応。
- **関連記事表示** — 記事末尾に最大 4 件。「同ジャンル×同タグ → 同タグ → 同ジャンル → 最新」の優先順位で段階的に選出。
- **ジャンル一覧ページ** — カテゴリごとにグループ化されたアコーディオン形式で全ジャンルを一覧表示。
- **自己紹介ページ・使い方ページ** — 管理者プロフィールとサイトの使い方の静的ページ。
- **サイト統計** — トップページに総投稿数・ハッシュタグ数・最終更新日を表示。
- **ダークモード切り替え** — ライト／ダークをワンタップで切り替え。選択は `localStorage` に保存され次回も維持される。
- **レスポンシブ対応** — スマホではハンバーガーメニューのドロワーナビに切り替わり、スクロールに追従してヘッダーが表示・非表示になる。

### 管理者向けの機能

記事を作成・管理するための、ログイン必須の機能です。

- **記事の投稿・編集・削除** — 作成、既存記事の更新、削除に対応。
- **公開／非公開の切り替え** — 記事ごとに公開状態をトグルで設定。非公開記事は管理者本人だけが閲覧できる。
- **Markdown 執筆ツールバー** — H2/H3 見出し・太字・目次（`[toc]`）・箇条書きリストをボタンで挿入。スマホではキーボード直上にツールバーが固定され、カーソルが常に見える位置へ自動スクロールする。
- **画像アップロード** — 本文中に `[imgN]` で挿入する画像を複数枚アップロード可能。画像ごとにキャプションを設定でき、プレビューを見ながら追加・削除できる。
- **サムネイル管理** — 記事一覧などで表示されるサムネイルを、本文画像とは独立して個別にアップロード可能。表示の優先順位は「専用サムネイル → 選択したプリセット → システム共通デフォルト」。
- **地図の埋め込み** — 場所名を入力すると `[map:場所名]` タグが挿入され、Google マップがプレビュー付きで埋め込まれる。
- **YouTube 動画の埋め込み** — URL または動画 ID を入力すると `[youtube:URL]` タグが挿入され、サムネイル＋再生ボタンのファサード形式（クリック時に初めて iframe を生成）で軽量に埋め込まれる。
- **ジャンルの作成・選択** — プリセットから選ぶか、新しいジャンルをその場で作成できる。
- **ハッシュタグの付与** — スペース・カンマ区切りで複数入力。入力に応じてタグのプレビューがリアルタイム表示される。
- **マイページ** — 自分の投稿一覧の確認、使用中ジャンルの一覧、ニックネームの変更ができる。

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10.11 |
| フレームワーク | Flask（Application Factory パターン） |
| ORM / DB マイグレーション | SQLAlchemy / Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF（CSRFProtect） |
| データベース | PostgreSQL（本番・ローカル） / SQLite（PythonAnywhere 等） |
| 本文変換 | Markdown（`toc` / `nl2br` 拡張） |
| ファイル検証 | filetype（MIME 判定） |
| タイムゾーン | pytz（Asia/Tokyo） |
| フロントエンド | 素の HTML / CSS / JavaScript（フレームワーク不使用） |
| コンテナ | Docker Compose（ローカル PostgreSQL 用） |

Blueprint は用途ごとに `auth`（ログイン）・`blog`（公開ページ）・`admin`（管理ページ）の 3 つに分割しています。

---

## ディレクトリ構成

```
.
├── app.py                  # エントリーポイント（create_app ファクトリ）
├── config.py               # .env からの環境変数読み込み
├── constants.py            # ジャンル定義（唯一の情報源）
├── extensions.py           # db / login_manager / migrate インスタンス
├── models.py               # User / Post / Hashtag テーブル定義
├── init_db.py              # SQLite 向け初期化スクリプト（テーブル＋管理者作成）
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 一覧・詳細・ジャンル・自己紹介・使い方
│   └── admin.py            # 投稿・編集・削除・マイページ
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # ページ別 CSS（ダークモード含む）
│   ├── img/                # 投稿画像・サムネイル
│   └── favicon/
├── migrations/             # Alembic マイグレーション
├── docker-compose.yml      # ローカル PostgreSQL
├── requirements.txt        # 依存パッケージ（PostgreSQL 含む）
├── requirements-pythonanywhere.txt  # SQLite 運用向け（psycopg 除外）
└── deploy_pythonanywhere.md         # PythonAnywhere デプロイ手順書
```

---

## セキュリティ設計

多層防御を意識した以下の対策を実装しています。

- **管理画面の秘匿** — ログイン URL を環境変数で隠蔽（`ADMIN_LOGIN_PATH`）。さらに合言葉（`ADMIN_GATE_KEY`）による Cookie を持たない訪問者にはログインページの存在自体を隠し、404 を返す（ゲートキー方式）。設定漏れ時は無防備になるのを避けるため、常に 404 とするフェイルクローズ設計。
- **ブルートフォース対策** — ログイン連続失敗 5 回で 5 分間ロックアウト。
- **パスワードのハッシュ化** — Werkzeug でハッシュ化し、平文は保存しない。
- **CSRF 保護** — 全フォームに CSRF トークンを強制適用。
- **ファイルアップロード検証** — 拡張子チェック・MIME タイプ判定（拡張子偽装の検出）・UUID によるファイル名ランダム化・30MB の容量制限。保存はアトミックで、途中失敗時に孤立ファイルを残さない。
- **XSS 対策** — 画像キャプションや地図ラベルの出力を `markupsafe.escape` でエスケープ。ハッシュタグのプレビューは `innerHTML` を使わず DOM API で組み立て。
- **Open Redirect 対策** — リダイレクト先が同一オリジンか検証。
- **セキュリティヘッダー** — `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` を付与。
- **Cookie 属性** — `HttpOnly` / `SameSite=Lax` / 本番では `Secure` を有効化。リバースプロキシ配下の HTTPS 判定は ProxyFix で補正。

---

## セットアップ（ローカル開発）

ローカルでは Docker Compose の PostgreSQL に接続する構成を想定しています。

```bash
# 1. リポジトリを取得
git clone <リポジトリURL>
cd <プロジェクト>

# 2. 仮想環境の作成と依存インストール
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. .env を作成（下記「環境変数」を参照）

# 4. PostgreSQL を起動
docker compose up -d

# 5. DB マイグレーションを適用
flask db upgrade

# 6. 開発サーバーを起動
python app.py
```

`http://127.0.0.1:5000` にアクセスして動作を確認します。管理画面には `/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>` からアクセスします。

---

## 環境変数

プロジェクト直下に `.env` を置きます（`config.py` が同ディレクトリから確実に読み込みます）。

| 変数 | 説明 |
|------|------|
| `SECRET_KEY` | セッション・CSRF トークンの署名鍵（長いランダム文字列）。本番では必須。 |
| `ADMIN_USERNAME` | 管理者ログインのユーザー名 |
| `ADMIN_PASSWORD` | 管理者パスワード（平文でもハッシュ済みでも可） |
| `ADMIN_LOGIN_PATH` | ログインページの URL パス（推測されにくい文字列）。**必須** |
| `ADMIN_GATE_KEY` | ログインページを表示するための合言葉（長いランダム文字列） |
| `FLASK_ENV` | `production` で本番モード（Secure Cookie・鍵の必須化） |
| `DATABASE_URL` | 明示指定する DB 接続 URL（最優先） |
| `USE_SQLITE` | `1` で `instance/blog.db` を SQLite として使用 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | ローカル PostgreSQL 接続情報（Docker 用） |

ランダム文字列は次のコマンドで生成できます（`SECRET_KEY` と `ADMIN_GATE_KEY` には別々の値を使ってください）。

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

DB 接続の優先順位は `DATABASE_URL` → `USE_SQLITE=1` → ローカル PostgreSQL の順です。

---

## 本番デプロイ

PythonAnywhere 無料枠（SQLite）へ GitHub 経由でデプロイする詳細な手順書を `deploy_pythonanywhere.md` に用意しています。要点は以下の通りです。

- DB は追加ドライバ不要の **SQLite** を使用（`USE_SQLITE=1` + `FLASK_ENV=production`）。
- 依存関係は PostgreSQL ドライバを除いた `requirements-pythonanywhere.txt` を使用。
- テーブル作成と管理者ユーザー登録は `python init_db.py` で一括実行（マイグレーション不要）。
- WSGI 設定から `create_app()` を呼び出して `application` として公開。

コード更新時の基本フローは「PC で修正 → GitHub に push → サーバーで `git pull` → Web タブで **Reload**」です。詳しい手順・トラブルシューティング・更新方法の早見表は手順書を参照してください。

---

## ライセンス

個人利用・学習目的のプロジェクトです。