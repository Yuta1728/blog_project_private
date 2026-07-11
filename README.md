# MIT Blog

Flask 製の個人ブログアプリケーションです。Markdown での記事投稿に加え、画像・地図・YouTube 動画の埋め込み、ハッシュタグ／ジャンルによる分類・検索、そして多層的なセキュリティ設計を備えています。学習目的での開発・公開を想定し、少ない構成で本番運用まで持っていけるよう作られています。

---

## 主な機能

### 記事の投稿・管理
- **Markdown 記事投稿**（`toc` / `nl2br` 拡張対応）。編集用ツールバーから見出し・太字・目次・リストをワンクリック挿入
- **独自 Markdown 記法**による画像・地図・YouTube の埋め込み（詳細は後述）
- **複数画像アップロード**：一括選択／1 枚ずつ追加に対応し、画像ごとにキャプションを設定可能
- **編集時の画像個別削除**：「更新」を押すまで確定しないプレビュー方式で誤操作に強い
- **デフォルトサムネイル**：画像を上げない記事にはプリセットのサムネイルを選択可能
- **公開／非公開設定**：非公開記事は投稿者本人のみ閲覧可
- **目次の自動生成**：`[toc]` を置いた位置、または記事冒頭に見出しから目次を生成

### 分類・検索
- **ジャンル分類**：プリセット + ユーザー独自ジャンルに対応（`constants.py` で一元管理）
- **ハッシュタグ**（多対多）：スペース・カンマ・全角スペース区切りで柔軟に入力。孤立タグは自動削除
- **検索・絞り込み**：キーワード（タイトル／タグ）× ジャンル × ハッシュタグを組み合わせて絞り込み
- **関連記事**：ジャンル・タグの一致度で段階的に最大 4 件を表示
- **サイト統計**：総投稿数・ハッシュタグ数・最終更新日をトップに表示

### 表示・UI
- レスポンシブ対応の「Coastal Dawn」テーマ
- スクロール連動で表示／非表示が切り替わる固定ヘッダー
- 記事一覧のページ番号送り、マイページの「もっと見る」表示
- YouTube はサムネイル + 再生ボタンの**ファサード方式**（クリック時に初めて iframe を生成し軽量化）

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.x（Application Factory パターン） |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| フォーム保護 | Flask-WTF（CSRF） |
| データベース | PostgreSQL（本番・ローカル） / SQLite（無料枠デプロイ向け） |
| Markdown | Markdown（`toc` / `nl2br` 拡張） |
| その他 | python-dotenv, pytz, filetype, Werkzeug |

---

## ディレクトリ構成

```
.
├── app.py                # アプリのエントリーポイント（create_app ファクトリ）
├── config.py             # .env の読み込み・環境変数の提供
├── constants.py          # デフォルトジャンル一覧（DRY 原則で一元管理）
├── extensions.py         # 拡張機能インスタンス（db / login_manager / migrate）
├── init_db.py            # マイグレーション不要のDB初期化スクリプト（SQLite向け）
├── models.py             # ORM モデル（Post / User / Hashtag / 中間テーブル）
├── views/
│   ├── auth.py           # ログイン・ログアウト（秘密URL・ゲートキー・ロックアウト）
│   ├── blog.py           # 公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py          # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/            # Jinja2 テンプレート
├── static/css/           # ページごとに分割された CSS
├── static/img/           # 投稿画像 / サムネイル
├── migrations/           # Alembic マイグレーション
├── requirements.txt                   # 依存パッケージ（PostgreSQL 含む）
├── requirements-pythonanywhere.txt    # SQLite 運用向け（psycopg 除外）
├── docker-compose.yml    # ローカル開発用 PostgreSQL
└── deploy_pythonanywhere.md           # PythonAnywhere デプロイ手順書
```

---

## セットアップ（ローカル開発）

### 1. リポジトリの取得と仮想環境

```bash
git clone <このリポジトリのURL>
cd <プロジェクトフォルダ>

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. `.env` の作成

プロジェクト直下に `.env` を作成します（値は自分のものに変更してください）。ランダム文字列は次で生成できます：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```dotenv
# --- Flask ---
FLASK_ENV=development
SECRET_KEY=ランダムな長い文字列

# --- 管理者認証 ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ログインパスワード（平文でOK。init_db.py がハッシュ化）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx      # 推測されにくいログインURLパス
ADMIN_GATE_KEY=別のランダムな長い文字列       # ログイン画面を表示する合言葉

# --- データベース（下記いずれかを選択） ---
# (A) ローカル PostgreSQL（docker-compose 使用時）
POSTGRES_USER=blog_user
POSTGRES_PASSWORD=blog_pass
POSTGRES_DB=blog_db
# (B) SQLite を使う場合
# USE_SQLITE=1
```

### 3. データベースの用意

**PostgreSQL（docker-compose）を使う場合：**

```bash
docker compose up -d          # localhost:15432 で PostgreSQL 起動
flask db upgrade              # マイグレーション適用
```

**SQLite で手早く動かす場合**（`.env` に `USE_SQLITE=1` を設定）：

```bash
python init_db.py             # テーブル作成 + 管理者ユーザー作成を一括実行
```

### 4. 起動

```bash
python app.py
```

ブラウザで `http://127.0.0.1:5000` を開くとトップページが表示されます。

---

## 環境変数一覧

| キー | 必須 | 説明 |
|------|:---:|------|
| `SECRET_KEY` | 本番必須 | セッション・CSRF トークンの署名鍵 |
| `ADMIN_USERNAME` | ✅ | 管理者ログインのユーザー名 |
| `ADMIN_PASSWORD` | ✅ | 管理者パスワード（平文・ハッシュ済みどちらも可） |
| `ADMIN_LOGIN_PATH` | ✅ | ログイン画面の URL パス（未設定だと起動時にエラー） |
| `ADMIN_GATE_KEY` | ✅ | ログイン画面を表示するための合言葉（未設定だと常に 404） |
| `FLASK_ENV` | 任意 | `production` で本番モード（Secure Cookie 等が有効化） |
| `USE_SQLITE` | 任意 | `1` で SQLite 運用（`instance/blog.db` を自動生成） |
| `DATABASE_URL` | 任意 | DB 接続 URL を明示指定（最優先） |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 任意 | ローカル PostgreSQL 接続情報 |

**DB 接続の優先順位**：`DATABASE_URL` → `USE_SQLITE=1` → ローカル PostgreSQL（フォールバック）

---

## 独自 Markdown 記法

本文中に以下のタグを書くと、記事表示時に自動変換されます（編集ツールバーからも挿入可）。

| 記法 | 変換内容 |
|------|----------|
| `[toc]` | その位置に目次を展開 |
| `[img1]` `[img2]` … | アップロード画像を挿入（キャプションがあれば `<figure>` として表示） |
| `[map:場所名]` | Google マップの埋め込み（例：`[map:東京スカイツリー]`） |
| `[youtube:URL]` | YouTube 動画をファサード形式で埋め込み（URL / 動画 ID 両対応） |

---

## セキュリティ設計

本アプリは学習目的ながら、管理画面を持つアプリとして多層的な防御を実装しています。

### 認証・アクセス制御
- **秘密のログイン URL**：`ADMIN_LOGIN_PATH` により URL 自体を隠蔽
- **ゲートキー方式**：合言葉（`?key=` → Cookie）を持たない訪問者にはログイン画面の存在自体を 404 で隠す。キー未設定時は**フェイルクローズ**（常に 404）
- **ブルートフォース対策**：5 回失敗で 5 分間セッションロックアウト
- **パスワードハッシュ照合**：`werkzeug` によるハッシュ検証（平文比較なし）
- **未認証時の 404 偽装**：`@login_required` 保護ページへの不正アクセスにログイン画面を見せない

### アプリケーション保護
- **CSRF 保護**：全フォームにトークンを強制適用
- **セキュリティヘッダー**：`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy`
- **Secure Cookie**：本番環境で `Secure` / `HttpOnly` / `SameSite=Lax`
- **ProxyFix**：リバースプロキシ配下でも HTTPS を正しく判定
- **Open Redirect 対策**：リダイレクト先の同一オリジン検証

### 入力・出力の無害化
- **画像アップロード検証**：拡張子（第 1 層）+ MIME タイプ判定（第 2 層）+ UUID 化（第 3 層）+ 30MB 制限（第 4 層）
- **XSS 対策**：キャプション・地図ラベル・YouTube エラー等、HTML へ直接埋め込む箇所を `escape()` で無害化。ハッシュタグプレビューも `textContent` で組み立て
- **URL エンコード**：地図 URL は `urllib.parse.quote()` で正しくエンコード

### データ整合性
- **画像とDBのアトミック性**：画像保存が途中で失敗した場合は保存済みファイルを掃除。DB の物理削除は **commit 成功後**にのみ実行し、失敗時は孤立ファイルが残る側（=データを壊さない側）に倒す

---

## デプロイ

PythonAnywhere 無料枠（SQLite 運用）への詳細なデプロイ・更新手順は [`deploy_pythonanywhere.md`](./deploy_pythonanywhere.md) にまとめています。GitHub 経由の `git clone` / `git pull`、WSGI 設定、初回セットアップ、公開後の運用まで網羅しています。

概略：

```
[自分のPC] コード修正 ──push──▶ [GitHub] ──git pull──▶ [PythonAnywhere] → Web タブで Reload
```

---

## ライセンス

個人利用・学習目的のプロジェクトです。利用する場合は各依存ライブラリのライセンスに従ってください。