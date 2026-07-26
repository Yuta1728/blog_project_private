# MITO Blog

Flask 製の個人用ブログアプリケーションです。Markdown で記事を書き、画像・地図・YouTube 動画を埋め込みながら、ジャンルやハッシュタグで整理・検索できます。管理画面は秘密の URL とゲートキーで保護され、閲覧側はダークモード対応・レスポンシブ・SEO 対応済みです。

Application Factory パターン（`create_app()`）で構成されており、本番／ローカルの PostgreSQL と、無料ホスティング向けの SQLite の両方で動作します。

---

## 目次

- [MITO Blog](#mito-blog)
  - [目次](#目次)
  - [主な機能](#主な機能)
    - [閲覧者向けの機能](#閲覧者向けの機能)
    - [管理者向けの機能](#管理者向けの機能)
  - [技術スタック](#技術スタック)
  - [ディレクトリ構成](#ディレクトリ構成)
  - [セットアップ（ローカル開発）](#セットアップローカル開発)
  - [環境変数](#環境変数)
  - [データベースの初期化・マイグレーション](#データベースの初期化マイグレーション)
  - [管理コマンド](#管理コマンド)
  - [デプロイ](#デプロイ)
  - [セキュリティ設計](#セキュリティ設計)
  - [ライセンス](#ライセンス)

---

## 主な機能

機能を「誰でも使える閲覧者向け」と「ログインした管理者だけが使える管理者向け」に分けて整理します。

### 閲覧者向けの機能

ログイン不要で、サイトを訪れた誰もが利用できる機能です。

**記事の閲覧・回遊**
- トップページの記事一覧（サーバーサイドのページ番号ページ送り、1 ページ 4 件）
- 記事詳細ページ（本文・目次・投稿者・投稿／更新日時を表示）
- 記事末尾の関連記事表示（同ジャンル × 同タグ → 同タグ → 同ジャンル → 最新、の優先順で最大 4 件）
- 記事本文の目次（`[toc]`）を記事冒頭または任意の位置に自動生成

**検索・絞り込み**
- キーワード検索（記事タイトル・ハッシュタグ名の部分一致）
- ジャンルによる絞り込み
- ハッシュタグによる絞り込み（ジャンル選択中は、そのジャンル内のタグが絞り込みバーに並ぶ）
- キーワード × ジャンルの組み合わせ検索
- ジャンル一覧ページ（カテゴリごとのアコーディオン表示）

**記事内の埋め込みコンテンツ**
- 記事本文中の画像表示（キャプション付き）
- Google マップの埋め込み表示
- YouTube 動画の埋め込み（初期はサムネイル表示、クリックで再生が始まる軽量なファサード方式）

**表示・使い勝手**
- ダークモード切り替え（選択は次回訪問時も維持）
- スマートフォン対応のレスポンシブレイアウト（ハンバーガーメニュー／ドロワーナビ）
- スクロール連動で開閉するヘッダー
- サイト統計の表示（総投稿数・ハッシュタグ数・最終更新日）
- 自己紹介ページ・使い方ページ

**SEO・シェア**
- ページごとの `<title>`／`description`／OGP・Twitter Card（SNS シェア時にタイトル・説明・画像が出る）
- `robots.txt` と `sitemap.xml`（公開記事と主要ページを自動列挙）

### 管理者向けの機能

秘密の URL からログインした管理者だけが利用できる機能です。

**記事の作成・編集・削除**
- Markdown による記事作成・編集
- 記事の削除
- 公開／非公開の切り替え（非公開記事は管理者本人のみ閲覧可能）
- ジャンルの選択、およびその場での新規ジャンル作成

**Markdown 編集ツールバー**
- H2／H3 見出し、太字、箇条書きリストのワンタッチ挿入
- 目次マーカー `[toc]` の挿入
- 地図挿入モーダル（場所名を入力するとプレビューを表示して挿入）
- YouTube 挿入モーダル（URL／動画 ID を入力するとサムネイルをプレビュー）
- 挿入済み画像に対応した `[imgN]` ボタンの動的生成
- スマートフォンではツールバーをキーボード直上に固定するモバイル最適化

**画像管理**
- 本文画像の複数アップロード（一括選択・1 枚ずつ追加）と、画像ごとのキャプション入力
- アップロード画像は自動で最適化（EXIF の回転補正・長辺の縮小・再圧縮）
- サムネイル専用画像のアップロード（本文画像とは独立、WebP に自動変換）
- プリセットのデフォルトサムネイル（趣味・旅行・スポーツなど）からの選択
- 編集時の既存画像の個別削除・キャプション編集

サムネイルの表示優先順位は「専用サムネイル → デフォルトサムネイル → システム共通のデフォルト画像」です。

**ハッシュタグ**
- スペース・カンマ区切りでのハッシュタグ入力（`#` は省略可）と入力中のリアルタイムプレビュー
- どの記事からも使われなくなったタグの自動削除

**マイページ**
- 自分の投稿一覧（ページ送り付き）と総投稿数の確認
- ニックネームの変更
- 自分が作成・使用したジャンルの一覧

---

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| 言語 | Python 3.10 |
| フレームワーク | Flask 3（Application Factory パターン） |
| ORM | SQLAlchemy 2 / Flask-SQLAlchemy |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム保護 | Flask-WTF（CSRF） |
| データベース | PostgreSQL（本番・ローカル）／ SQLite（無料ホスティング） |
| 画像処理 | Pillow |
| Markdown | Markdown（toc / nl2br 拡張） |
| フロントエンド | 素の HTML / CSS / JavaScript（フレームワーク不使用） |

---

## ディレクトリ構成

```
.
├── app.py                  アプリ生成の起点（create_app）・ログ設定・CLI・エラーハンドラ
├── config.py               .env の読み込みと設定値の提供
├── constants.py            ジャンル定義（唯一の情報源）
├── extensions.py           db / login_manager / migrate インスタンスの置き場
├── models.py               テーブル定義（User / Post / Hashtag / 中間テーブル）
├── rendering.py            本文 Markdown + 独自タグ → HTML 変換の共通モジュール
├── init_db.py              マイグレーション不要の DB 初期化スクリプト（SQLite 向け）
├── views/
│   ├── auth.py             ログイン・ログアウト（秘密 URL・ゲートキー・ロックアウト）
│   ├── blog.py             公開ページ（一覧・検索・詳細・ジャンル・SEO）
│   └── admin.py            管理ページ（投稿・編集・削除・マイページ・画像処理）
├── templates/              Jinja2 テンプレート（base / 各ページ / 共通マクロ・モーダル）
├── static/
│   ├── css/                ページ別 CSS・ダークモード CSS
│   ├── js/                 base.js / editor.js / mobile-editor.js
│   ├── img/                投稿画像（posts/）・デフォルトサムネイル（thbnails/）
│   └── favicon/
├── migrations/             Alembic マイグレーション
├── docker-compose.yml      ローカル開発用 PostgreSQL
├── requirements.txt                  依存パッケージ（PostgreSQL 含む）
└── requirements-pythonanywhere.txt   依存パッケージ（SQLite 運用・psycopg 除外）
```

---

## セットアップ（ローカル開発）

PostgreSQL を Docker で起動して開発する例です。

1. リポジトリを取得し、仮想環境を用意して依存をインストールします。

   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Windows は .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. プロジェクト直下に `.env` を作成します（[環境変数](#環境変数)を参照）。

3. ローカル用 PostgreSQL を起動します。

   ```bash
   docker compose up -d
   ```

   `docker-compose.yml` はホストの `15432` 番ポートでコンテナの PostgreSQL を公開します。`app.py` は `DATABASE_URL` も `USE_SQLITE` も無い場合、`localhost:15432` の PostgreSQL に接続します。

4. データベースを構築します（[データベースの初期化・マイグレーション](#データベースの初期化マイグレーション)を参照）。

5. 開発サーバーを起動します。

   ```bash
   python app.py
   ```

   デバッグモードは、本番判定に該当せず、かつ `FLASK_DEBUG=1`（または `true`）のときのみ有効になります。

---

## 環境変数

`.env` に設定します。`config.py` が自身の場所を基準に `.env` を読み込むため、どこから起動しても確実に読み込まれます。

| 変数名 | 必須 | 説明 |
| --- | --- | --- |
| `ADMIN_LOGIN_PATH` | ○ | ログインページの URL パス（推測されにくいランダム文字列）。未設定だと起動時にエラー |
| `ADMIN_GATE_KEY` | ○（管理ログイン利用時） | ログイン画面を表示するための合言葉。未設定だとログイン画面は常に 404 |
| `ADMIN_USERNAME` | ○ | 管理者ログインのユーザー名 |
| `ADMIN_PASSWORD` | ○ | 管理者パスワード（平文・ハッシュ済みのどちらも可。`init_db.py` が適切に処理） |
| `SECRET_KEY` | 本番で必須 | セッション・CSRF トークンの署名に使う秘密鍵。本番で未設定だと起動を中止 |
| `FLASK_ENV` | 任意 | `production` を設定すると本番扱い（Secure Cookie 有効化・`SECRET_KEY` 必須化） |
| `USE_SQLITE` | 任意 | `1` にすると `instance/blog.db` を SQLite として使用（無料ホスティング向け） |
| `DATABASE_URL` | 任意 | 明示指定する接続 URL。設定されていれば最優先 |
| `LOG_LEVEL` | 任意 | ログレベル。未設定時は本番 `INFO`／開発 `DEBUG` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 任意 | ローカルの PostgreSQL 接続情報（`docker-compose.yml` と共用） |

**接続先の優先順位:** `DATABASE_URL` → `USE_SQLITE=1`（SQLite）→ ローカル PostgreSQL。

ランダム文字列の生成例:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## データベースの初期化・マイグレーション

用途に応じて 2 通りの方法があります。

**マイグレーション運用（PostgreSQL 推奨）**

```bash
flask db upgrade        # 既存のマイグレーションを適用
```

`models.py` を変更したときは、差分を検出して適用します。

```bash
flask db migrate -m "変更内容"
flask db upgrade
```

**初期化スクリプト（SQLite・マイグレーション不要）**

無料ホスティングなどでマイグレーションを使わない場合は、テーブル作成と管理者ユーザーの登録を一括で行います。

```bash
python init_db.py
```

このスクリプトは、テーブル作成後に Alembic の履歴を最新（head）へスタンプするため、後からマイグレーション運用へ移行しても履歴の食い違いが起きません。何度実行しても安全です。

---

## 管理コマンド

`flask <コマンド名>` で実行できる運用コマンドです。

**本文 HTML の再生成**

記事本文は投稿・編集時に HTML へ変換してキャッシュしています。`rendering.py` を変更した際は、`RENDER_VERSION` を +1 したうえで既存記事を作り直せます（未指定でもアクセス時に自動再生成されます）。

```bash
flask rerender-posts            # 古いバージョンの記事だけ再生成
flask rerender-posts --all      # 全記事を強制的に再生成
flask rerender-posts --dry-run  # 対象を表示するだけ（保存しない）
```

**孤児画像の掃除**

どの記事からも参照されていない画像ファイルを一覧・削除します。

```bash
flask clean-orphan-images           # 孤児画像を一覧表示するだけ
flask clean-orphan-images --delete  # 実際に削除する
```

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用、GitHub 経由）での公開手順は `deploy_pythonanywhere.md` に詳しくまとめています。要点は次のとおりです。

- 依存は `requirements-pythonanywhere.txt`（PostgreSQL ドライバを除外）を使用
- `.env` に `USE_SQLITE=1` と `FLASK_ENV=production` を設定
- `python init_db.py` でテーブルと管理者ユーザーを作成
- Web タブは Manual configuration（Python 3.10）で構成し、WSGI から `create_app()` を呼び出す（`wsgi_pythonanywhere.py` が貼り付け用サンプル）
- コード更新は「PC で修正 → GitHub に push → サーバーで pull → Web タブで Reload」

なお、リバースプロキシ配下でも HTTPS を正しく判定できるよう `ProxyFix` を適用し、静的ファイルには更新時刻ベースのキャッシュバスティング（`static_url`）を効かせています。

---

## セキュリティ設計

- **秘密の URL:** ログインページの URL は `ADMIN_LOGIN_PATH` で隠蔽
- **ゲートキー方式:** 合言葉（`ADMIN_GATE_KEY`）の Cookie を持たない訪問者にはログイン画面の存在自体を 404 で隠す（ゲートキー未設定時は安全側に倒して常に 404）
- **ブルートフォース対策:** ログインの連続失敗でセッションを一定時間ロックアウト
- **CSRF 保護:** 全フォームに CSRF トークンを強制
- **アップロード検証:** 拡張子 + 実バイトの MIME 判定による多層チェック、サイズ上限（30MB）
- **セキュリティヘッダー:** `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` を付与
- **Cookie 属性:** `HttpOnly` / `SameSite=Lax` を設定し、本番では `Secure` を有効化
- **エラー時の情報漏洩防止:** 未ログインでの管理ページアクセスはログイン画面へ誘導せず 404 を返す

---

## ライセンス

個人利用・学習目的のプロジェクトです。