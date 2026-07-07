# MIT Blog — 個人用ブログアプリ

Flask + PostgreSQL で構築した、単一管理者運用の個人ブログアプリケーションです。
Markdown ベースの記事執筆に加え、画像・Google マップ・YouTube の埋め込み、ジャンル×ハッシュタグによる絞り込み検索など、個人ブログに必要な機能を一通り備えています。

学習目的も兼ねているため、各ファイルには処理フロー図や設計意図を記したコメントを多く残しています。

---

## 主な機能

### 閲覧者向け（一般公開ページ）
- **記事一覧（トップページ）** — 記事カード表示、ページ番号によるページ送り、サイト統計（総投稿数・タグ数・最終更新日）、自己紹介（hero）セクション
- **検索・絞り込み** — キーワード検索（タイトル・ハッシュタグの部分一致）、ジャンル絞り込み、ジャンル×ハッシュタグの組み合わせ絞り込み
- **記事詳細ページ** — Markdown 変換された本文、目次の自動生成（`[toc]`）、画像キャプション、Google マップ埋め込み、YouTube のファサード（クリック時ロード）埋め込み、関連記事の自動表示（最大4件）
- **静的ページ** — 自己紹介（`/about`）、ブログの使い方（`/howto`）、ジャンル一覧（`/genre`）
- **レスポンシブ対応** — スマホ用ドロワーメニュー、スクロール連動の固定ヘッダー

### 管理者向け（ログイン必須）
- **記事の投稿・編集・削除** — Markdown ツールバー（見出し／太字／リスト／目次／地図／YouTube／画像タグ挿入）付きエディタ
- **画像アップロード** — 複数一括／1枚ずつ追加、プレビュー、キャプション入力、既存画像の個別削除、デフォルトサムネイル選択
- **公開設定** — 記事ごとの公開／非公開トグル（非公開記事は本人のみ閲覧可）
- **ハッシュタグ管理** — スペース・カンマ区切りの自由入力、リアルタイムプレビュー、孤立タグの自動削除
- **マイページ** — 投稿一覧、使用ジャンル一覧、ニックネーム変更

---

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1 |
| ORM / マイグレーション | Flask-SQLAlchemy (SQLAlchemy 2.0) / Flask-Migrate (Alembic) |
| 認証 | Flask-Login |
| CSRF 保護 | Flask-WTF (CSRFProtect) |
| DB | PostgreSQL 18（Docker Compose、ドライバは psycopg 3） |
| Markdown 変換 | Python-Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |
| フロントエンド | Jinja2 テンプレート + 素の CSS / JavaScript（フレームワーク不使用） |

---

## ディレクトリ構成

```
.
├── app.py                # エントリーポイント（Application Factory パターン）
├── config.py             # .env の読み込み・環境変数の提供
├── constants.py          # デフォルトジャンルなどの定数
├── extensions.py         # db / login_manager / migrate インスタンスの置き場
├── models.py             # ORM モデル（Post / Hashtag / User / 中間テーブル）
├── docker-compose.yml    # ローカル開発用 PostgreSQL
├── requirements.txt
├── migrations/           # Alembic マイグレーション
├── views/
│   ├── auth.py           # ログイン・ログアウト（秘密URL + ゲートキー方式）
│   ├── blog.py           # 一般公開ページ（一覧・詳細・ジャンルなど）
│   └── admin.py          # 管理者専用ページ（投稿・編集・削除・マイページ）
├── templates/            # Jinja2 テンプレート
└── static/
    ├── css/              # ページ別 CSS（Coastal Dawn テーマ）
    └── img/
        ├── posts/        # アップロード画像（UUID ファイル名）
        └── thbnails/     # デフォルトサムネイル
```

---

## セットアップ（ローカル開発）

### 1. リポジトリの取得と仮想環境の作成

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. .env ファイルの作成

プロジェクトルートに `.env` を作成し、以下を設定します（`.env` は `.gitignore` 済み）。

```dotenv
# --- PostgreSQL（docker-compose と共有） ---
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=blogdb

# --- Flask ---
SECRET_KEY=your-random-secret-key
FLASK_DEBUG=1                     # 開発時のみ。本番では無視される

# --- 管理者・ログイン画面の隠蔽 ---
ADMIN_USERNAME=admin
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx   # ログインページのURLパス（推測困難な文字列に）
ADMIN_GATE_KEY=xxxxxxxxxxxxxxxxxxxxxxxx # ログインページ表示用の合言葉
```

ランダム文字列の生成例:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`ADMIN_LOGIN_PATH` と `ADMIN_GATE_KEY` は**未設定だとアプリが起動しない／ログインページが常に 404 になる**フェイルクローズ設計です。必ず設定してください。

### 3. データベースの起動とマイグレーション

```bash
# PostgreSQL をコンテナで起動（ホスト側ポート 15432）
docker compose up -d

# スキーマを適用
flask db upgrade
```

### 4. 管理者ユーザーの作成

初回のみ、`flask shell` などから管理者ユーザーを登録します（パスワードはハッシュ化して保存します）。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

user = User(
    username='admin',   # .env の ADMIN_USERNAME と一致させる
    password=generate_password_hash('your-login-password'),
    nickname='管理者',
)
db.session.add(user)
db.session.commit()
```

### 5. 起動

```bash
python app.py
```

`http://localhost:5000` でトップページが表示されます。

### 6. 管理画面へのログイン

初回は合言葉付き URL にアクセスします（ブックマーク推奨）:

```
http://localhost:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

合言葉が正しいとゲート Cookie（90日有効）が発行され、以降は `?key=` なしの秘密 URL だけでログインページに到達できます。Cookie を持たない訪問者には 404 を返し、ログインページの存在自体を隠します。

---

## 記事本文で使える独自タグ

本文は Markdown（見出し `##` / `###`、太字、`[toc]` 目次など）に加えて、以下の独自タグに対応しています。いずれもエディタのツールバーから挿入できます。

| タグ | 機能 |
|---|---|
| `[toc]` | その位置に目次を展開（未使用時は記事冒頭に自動表示） |
| `[img1]` `[img2]` … | アップロードした N 枚目の画像を挿入（キャプション付き `<figure>` 対応） |
| `[map:東京スカイツリー]` | Google マップの iframe を埋め込み |
| `[youtube:URLまたは動画ID]` | YouTube をファサード形式で埋め込み（サムネイルをタップすると再生開始） |

---

## セキュリティ設計

多層防御を意識した実装になっています。

- **ログインページの隠蔽（4層）** — ① 秘密の URL（`ADMIN_LOGIN_PATH`）② ゲートキー Cookie（`ADMIN_GATE_KEY`）③ ユーザー名 ④ パスワード。未ログインで管理者ページへアクセスしても 404 を返し、ページの存在を偽装
- **ブルートフォース対策** — ログイン 5 回連続失敗で 5 分間のセッションロックアウト
- **CSRF 保護** — 全変更系リクエストに CSRF トークンを強制（Flask-WTF）
- **画像アップロードの多層検証** — 拡張子ホワイトリスト → MIME タイプ判定（filetype）→ UUID によるファイル名ランダム化 → 30MB のサイズ上限
- **XSS 対策** — キャプション・地図ラベル・YouTube エラーメッセージなど、HTML に連結するユーザー入力を `markupsafe.escape()` で無害化。フロント側のタグプレビューも `textContent` ベースで構築
- **Open Redirect 対策** — Referer リダイレクト時に同一オリジンを検証
- **セキュリティヘッダー** — `X-Content-Type-Options: nosniff` / `X-Frame-Options: SAMEORIGIN` / `Referrer-Policy: strict-origin-when-cross-origin`
- **Cookie 属性** — `HttpOnly` / `SameSite=Lax` / 本番では `Secure` を付与（ProxyFix によりリバースプロキシ配下でも正しく判定）
- **フェイルクローズ** — `SECRET_KEY`（本番）・`ADMIN_LOGIN_PATH`・`ADMIN_GATE_KEY` の設定漏れは起動拒否または常時 404 で安全側に倒す

### DB とファイルの整合性ルール

画像ファイルと DB レコードの不整合を防ぐため、以下の順序を全ビューで厳守しています。

1. 新規画像の保存（`_save_images()` は全成功 or 全掃除のアトミック動作）
2. DB 変更をセッションに積んで `commit`
3. commit **失敗** → rollback + 今回保存した新ファイルを掃除（DB は無傷）
4. commit **成功** → ここで初めて旧ファイルを物理削除（失敗しても孤立ファイルが残るだけでデータは壊れない）

---

## 本番デプロイの注意点

- 本番判定は「`DATABASE_URL` が設定されている」または「`FLASK_ENV=production`」で行われます
- 本番では PaaS（Render / Heroku 等）が設定する `DATABASE_URL` を接続先として使用します
- リバースプロキシ配下での HTTPS 判定のため、`ProxyFix(x_proto=1, x_host=1)` を適用済みです（多段プロキシ構成の場合は段数を調整してください）
- 本番では `FLASK_DEBUG` を設定していてもデバッグモードは強制無効化されますが、`python app.py` での直接起動ではなく Gunicorn 等の WSGI サーバーでの運用を推奨します

```bash
pip install gunicorn
gunicorn "app:create_app()"
```

- ロックアウトはセッション（ブラウザ）単位のため、より強固にするには Flask-Limiter + Redis 等による IP ベースの制限を検討してください

---

## ライセンス / 作者

個人学習・個人運用を目的としたプロジェクトです。

作者: MIT（「MIT Blog」管理者）