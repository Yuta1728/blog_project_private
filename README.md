# MIT Blog

Flask 製の個人ブログアプリケーションです。単一の管理者が記事を投稿・編集・管理し、一般の閲覧者が公開記事を読めるシンプルな構成になっています。Markdown での執筆、画像アップロード、ハッシュタグ・ジャンルによる分類、地図や YouTube 動画の埋め込みなどに対応しています。

セキュリティ面では、秘密のログイン URL とゲートキー方式による多層防御、ブルートフォース対策、CSRF 保護、アップロードファイルの検証などを実装しています。

---

## 主な機能

### 閲覧者向け機能
- **記事一覧・検索**：トップページでキーワード（タイトル・タグ）検索、ジャンル絞り込み、ハッシュタグ絞り込みができます。
- **記事詳細**：Markdown で書かれた本文を HTML に変換して表示します。目次（`[toc]`）、画像＋キャプション、Google マップ、YouTube 動画（サムネイル→クリックで再生するファサード方式）の埋め込みに対応しています。
- **関連記事**：記事詳細の末尾に、ジャンルやタグの近さをもとにした関連記事を最大 4 件表示します。
- **ジャンル一覧**：アコーディオン形式でジャンルをカテゴリ別に閲覧できます。
- **サイト統計**：トップページに総投稿数・ハッシュタグ数・最終更新日を表示します。
- **レスポンシブ対応**：スマホではドロワーメニュー、スクロール連動ヘッダーなどのモバイル向け UI を備えています。

### 管理者向け機能
- **記事の投稿・編集・削除**：Markdown ツールバー（見出し・太字・リスト・目次・地図・YouTube・画像挿入）付きのエディタで執筆できます。
- **画像アップロード**：複数まとめて選択・1 枚ずつ追加・個別削除に対応。各画像にキャプションを付けられます。
- **公開／非公開の切り替え**：記事ごとに全体公開・非公開を設定できます。非公開記事は管理者本人のみ閲覧可能です。
- **ジャンル・ハッシュタグ管理**：プリセットジャンルからの選択、独自ジャンルの新規作成、ハッシュタグの自由入力ができます。
- **マイページ**：自分の投稿一覧の確認、ニックネームの変更ができます。

---

## 技術スタック

| 種別 | 使用技術 |
| --- | --- |
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1.3 |
| ORM | SQLAlchemy 2.0 / Flask-SQLAlchemy 3.1 |
| DB マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF |
| データベース | PostgreSQL 18 |
| Markdown 変換 | Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |

設計上のポイントとして、**Application Factory パターン**を採用し、拡張機能インスタンスを `extensions.py` に分離することで循環インポートを回避しています。

---

## ディレクトリ構成

```
.
├── app.py                # アプリのエントリーポイント（create_app ファクトリ）
├── config.py             # .env から環境変数を読み込む
├── constants.py          # デフォルトジャンル一覧などの定数
├── extensions.py         # db / login_manager / migrate インスタンス
├── models.py             # ORM モデル（Post / Hashtag / User + 中間テーブル）
├── requirements.txt      # 依存パッケージ
├── docker-compose.yml    # ローカル開発用の PostgreSQL
├── migrations/           # Alembic マイグレーション
├── views/                # Blueprint（機能ごとのルート）
│   ├── auth.py           # ログイン・ログアウト
│   ├── blog.py           # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py          # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/            # Jinja2 テンプレート
└── static/               # CSS・画像・サムネイル
```

### データモデルの関係

```
User (管理者) ──1対多──> Post (記事) ──多対多──> Hashtag (タグ)
                                      (post_hashtags 中間テーブル経由)
```

---

## セットアップ

### 1. 前提

- Python 3.10.11
- Docker / Docker Compose（ローカル DB 用）

### 2. リポジトリの取得と依存パッケージのインストール

```bash
git clone <このリポジトリの URL>
cd <プロジェクトディレクトリ>

python -m venv .venv
source .venv/bin/activate        # Windows は .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. 環境変数（.env）の作成

プロジェクトルートに `.env` ファイルを作成し、以下を設定します（`.env` は `.gitignore` により Git 管理対象外です）。

```dotenv
# --- PostgreSQL 接続情報（docker-compose と共通） ---
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# --- セッション・CSRF トークンの署名鍵 ---
SECRET_KEY=long_random_secret_string

# --- 管理者認証情報 ---
ADMIN_USERNAME=your_admin_name
ADMIN_PASSWORD=werkzeug_hashed_password   # ハッシュ化済みパスワード

# --- 秘密のログイン URL（推測されにくいランダム文字列） ---
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx

# --- ログインページのゲートキー（合言葉） ---
ADMIN_GATE_KEY=another_long_random_string

# --- 任意（ローカル開発でデバッグを有効にする場合） ---
# FLASK_DEBUG=1
```

**補足**

- `ADMIN_PASSWORD` は平文ではなくハッシュ値を保存します。次のように生成できます。

  ```bash
  python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('あなたのパスワード'))"
  ```

- `ADMIN_GATE_KEY` / `SECRET_KEY` のようなランダム文字列は次のように生成できます。

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

### 4. データベースの起動

```bash
docker compose up -d
```

ホスト側の `15432` 番ポートで PostgreSQL に接続できます。

### 5. マイグレーションの適用

```bash
flask db upgrade
```

### 6. 管理者ユーザーの作成

このアプリは単一管理者を想定しており、`User` テーブルに `ADMIN_USERNAME` と一致するユーザーが 1 件必要です。ハッシュ化済みパスワードを含めて DB に登録してください（Flask シェルや DB クライアント経由）。

### 7. アプリの起動

```bash
python app.py
```

デバッグモードは `FLASK_DEBUG=1` を明示した場合のみ有効になります（本番環境では強制的に無効化されます）。

---

## 管理者としてログインする

このアプリはログインページの存在自体を隠す設計になっています。ログインには次の 2 段階が必要です。

1. **初回アクセス**：`https://<ホスト>/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>` にアクセスします。合言葉が正しければゲート用 Cookie が発行され、`key` なしの URL にリダイレクトされます（この URL をブックマークしておくと便利です）。
2. **以降のアクセス**：Cookie が有効な間（90 日）は `https://<ホスト>/<ADMIN_LOGIN_PATH>` だけでログインフォームに到達できます。

正しいゲート Cookie を持たない訪問者には、ログインページが `404 Not Found` として表示されます。

---

## セキュリティ機能

多層防御を意識した以下の対策を実装しています。

- **秘密のログイン URL**：`ADMIN_LOGIN_PATH` を環境変数で隠蔽（Security through obscurity）。
- **ゲートキー方式**：合言葉 Cookie を持たない訪問者にはログインページの存在を隠して 404 を返す（設定漏れ時は安全側に倒して 404＝フェイルクローズ）。
- **ブルートフォース対策**：ログイン失敗 5 回で 5 分間ロックアウト。
- **未認証アクセスの隠蔽**：管理者専用ページに未ログインでアクセスした場合、ログイン画面に誘導せず 404 を返す。
- **CSRF 保護**：全ての変更系リクエストに CSRF トークン検証を強制。
- **アップロードファイルの検証**：拡張子チェック（第 1 層）＋ MIME タイプ判定（第 2 層、拡張子偽装の検出）＋ UUID によるファイル名ランダム化（第 3 層）＋ 30MB の容量制限（第 4 層）。
- **セキュリティヘッダー**：`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy` を全レスポンスに付与。
- **Cookie 属性**：`HttpOnly` / `SameSite=Lax` / 本番では `Secure` を設定。
- **XSS 対策**：地図・YouTube・画像キャプションなどユーザー入力を HTML に埋め込む箇所で `escape()` / `quote()` を適用。
- **Open Redirect 対策**：リダイレクト先を同一オリジンかどうか検証。
- **本番環境の起動保護**：`SECRET_KEY` 未設定時は起動を拒否し、デバッガの露出を防ぐため本番ではデバッグモードを強制無効化。
- **リバースプロキシ対応**：`ProxyFix` により PaaS 配下でも HTTPS を正しく判定。

---

## Markdown 記法の補足

本文では標準の Markdown に加えて、以下の独自タグが使えます。

| タグ | 機能 |
| --- | --- |
| `[toc]` | 目次を挿入 |
| `[imgN]` | N 番目にアップロードした画像を挿入（キャプション対応） |
| `[map:場所名]` | Google マップを埋め込み |
| `[youtube:URL]` | YouTube 動画を埋め込み（サムネイル→クリックで再生） |

また、2 行以上の連続する空行は行間として保持されます（`<br>` に展開）。

---

## デプロイについて

本番環境（Heroku / Render などの PaaS）では、`DATABASE_URL` 環境変数が設定されていれば自動的にそれを DB 接続先として使用します。`DATABASE_URL` または `FLASK_ENV=production` が設定されている場合は本番環境と判定され、`SECRET_KEY` の必須化や Cookie の `Secure` 属性有効化などが自動で行われます。

---

## ライセンス 

個人学習・個人運用を目的としたプロジェクトです。