# MITO Blog

Flask 製の個人ブログアプリケーションです。単一の管理者が記事を投稿・管理し、誰でも記事を閲覧できます。Markdown による執筆、画像・地図・YouTube の埋め込み、ハッシュタグ／ジャンルによる分類、ダークモードなどに対応しています。

構成は **Application Factory パターン**（`create_app()`）を採用し、ローカルは PostgreSQL、PythonAnywhere 無料枠では SQLite と、接続先を切り替えるだけで動作します。

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10 |
| Web フレームワーク | Flask 3 |
| ORM / DB | SQLAlchemy + Flask-SQLAlchemy（PostgreSQL / SQLite） |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム保護 | Flask-WTF（CSRF） |
| 本文変換 | Markdown（`toc` / `nl2br` 拡張） |
| 画像処理 | Pillow（縮小・WebP 変換）、filetype（MIME 検証） |
| その他 | pytz（Asia/Tokyo）、python-dotenv |

フロントエンドはテンプレート（Jinja2）+ 素の CSS / JavaScript で構成され、外部フレームワークには依存していません。

---

## 主な機能

機能を「閲覧者向け（誰でも利用可能）」と「管理者向け（ログインが必要）」に分けて示します。

### 閲覧者向け機能（ログイン不要）

- **記事一覧の閲覧**：トップページで公開記事を新着順に表示。1 ページ 4 件のサーバーサイドページネーションに対応。
- **キーワード検索**：記事タイトルとハッシュタグ名を対象に部分一致で検索。
- **ジャンル絞り込み**：ジャンルを指定して記事を絞り込み。ジャンル一覧ページ（アコーディオン表示）から選択可能。
- **ハッシュタグ絞り込み**：ジャンル選択中に、そのジャンル内で使われているタグでさらに絞り込み。
- **記事詳細の閲覧**：Markdown を HTML 変換して表示。以下の要素をサポート。
  - 見出しから自動生成される**目次（TOC）**
  - 本文中の**画像とキャプション**
  - **Google マップ**の埋め込み（`[map:場所名]`）
  - **YouTube 動画**の埋め込み（サムネイル→クリックで再生するファサード方式）
- **関連記事の表示**：同ジャンル・同タグを優先して最大 4 件を提示。
- **サイト統計**：総投稿数・ハッシュタグ数・最終更新日をトップページに表示。
- **自己紹介 / 使い方ページ**：静的な案内ページ。
- **ダークモード**：ワンクリックで切り替え、選択内容は `localStorage` に保存。
- **レスポンシブ対応**：スマホではドロワーメニュー、スクロール連動の追従ヘッダーを提供。

### 管理者向け機能（ログイン必須）

- **記事の新規投稿 / 編集 / 削除**：CSRF トークンで保護されたフォームから操作。
- **Markdown 編集ツールバー**：H2 / H3 見出し、太字、目次、箇条書き、画像挿入、地図挿入、YouTube 挿入をボタンで補助。スマホではキーボード直上にツールバーを固定する編集支援あり。
- **画像アップロード**：
  - 本文用画像を複数枚アップロード（`[imgN]` で本文中に配置）。1 枚ごとにキャプションを設定可能。
  - サムネイル専用画像を個別にアップロード可能。
  - プリセットのデフォルトサムネイルからの選択も可能。
  - サムネイル表示は「専用サムネイル → デフォルトサムネイル → システム共通画像」の優先順位でフォールバック。
- **画像の自動最適化**：アップロード時に Pillow で縮小・再圧縮（本文画像は長辺 1600px、サムネイルは幅 400px の WebP）。EXIF の向きも自動補正。
- **ジャンル管理**：プリセットからの選択に加え、新しいジャンルをその場で作成可能。
- **ハッシュタグ**：スペース・カンマ区切りで複数入力（`#` 省略可）。入力中にリアルタイムプレビュー。使われなくなったタグは自動削除。
- **公開設定**：記事ごとに「全体公開 / 非公開」をトグルで切り替え。非公開記事は管理者本人のみ閲覧可能。
- **マイページ**：総投稿数の確認、投稿一覧（ページネーション）、使用ジャンル一覧、ニックネームの変更。

---

## セキュリティ設計

- **秘密のログイン URL + ゲートキー方式**：ログインページの URL を環境変数で隠蔽。さらに合言葉（`ADMIN_GATE_KEY`）付き Cookie を持たない訪問者には 404 を返し、ページの存在自体を隠す。
- **ブルートフォース対策**：連続ログイン失敗でセッションを一定時間ロックアウト。
- **パスワードのハッシュ化**：平文は保存せず、Werkzeug のハッシュと照合。
- **CSRF 保護**：すべてのフォームにトークンを強制適用。
- **ファイルアップロード検証**：拡張子 + 先頭バイトの MIME 判定による多層防御。UUID でファイル名をランダム化し、合計 30MB の容量制限。
- **XSS 対策**：キャプション・地図・YouTube タグの出力時に HTML エスケープを徹底。
- **Open Redirect 対策**：リダイレクト先を同一オリジンに限定。
- **セキュリティヘッダー**：`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` を付与。
- **リバースプロキシ対応**：ProxyFix により本番環境で HTTPS を正しく判定し、Secure Cookie を有効化。

---

## ディレクトリ構成

```
.
├── app.py                  # エントリーポイント（create_app ファクトリ）
├── config.py               # 環境変数の読み込み
├── constants.py            # ジャンル定義（唯一の情報源）
├── extensions.py           # db / login_manager / migrate インスタンス
├── models.py               # ORM モデル（User / Post / Hashtag）
├── init_db.py              # DB 初期化スクリプト（SQLite / 管理者作成）
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # 公開ページ（一覧・詳細・ジャンル）
│   └── admin.py            # 管理ページ（投稿・編集・削除・マイページ）
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # ページ別スタイル + ダークモード
│   ├── js/editor.js        # エディタ共通ロジック
│   └── img/                # 記事画像・サムネイル・favicon
├── migrations/             # Alembic マイグレーション
├── docker-compose.yml      # ローカル開発用 PostgreSQL
├── requirements.txt        # 依存パッケージ（PostgreSQL 含む）
└── requirements-pythonanywhere.txt  # SQLite 運用向け依存一覧
```

---

## セットアップ（ローカル開発）

### 1. リポジトリの取得と仮想環境

```bash
git clone <このリポジトリのURL>
cd <プロジェクトディレクトリ>
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 環境変数の設定

プロジェクト直下に `.env` を作成します。

```env
# データベース（ローカル PostgreSQL を docker で起動する場合）
POSTGRES_USER=blog_user
POSTGRES_PASSWORD=blog_password
POSTGRES_DB=blog_db

# 管理者アカウント
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_password        # 平文可（ハッシュ化される）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx   # 推測されにくい URL パス
ADMIN_GATE_KEY=（ランダムな長い文字列）

# セッション署名鍵
SECRET_KEY=（ランダムな長い文字列）
```

ランダム文字列は次のコマンドで生成できます。

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. データベースの起動と初期化

```bash
# PostgreSQL コンテナを起動
docker compose up -d

# テーブル作成とマイグレーション適用
flask db upgrade
```

### 4. 起動

```bash
python app.py
```

ブラウザで `http://127.0.0.1:5000` にアクセスします。

---

## 管理者としてログインする

ログインページは隠蔽されています。初回は合言葉付き URL でアクセスします。

```
http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされます。その後、`ADMIN_USERNAME` と `ADMIN_PASSWORD` でログインします。

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用）向けの詳細な手順は `deploy_pythonanywhere.md` にまとめています。要点は次のとおりです。

- 環境変数に `USE_SQLITE=1` と `FLASK_ENV=production` を設定すると、`instance/blog.db` を SQLite として自動利用。
- 依存は `requirements-pythonanywhere.txt`（PostgreSQL ドライバを除外）を使用。
- `python init_db.py` でテーブル作成・管理者ユーザー作成・Alembic 履歴のスタンプを一括実行。

---

## ライセンス

学習・個人利用を目的としたプロジェクトです。