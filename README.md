# MIT Blog — Flask 製 個人ブログアプリ

Flask + PostgreSQL で構築した、単一管理者運用の個人ブログアプリケーションです。
Markdown による記事執筆、画像・地図・YouTube の埋め込み、ジャンル×ハッシュタグによる絞り込み検索などを備え、セキュリティ対策（秘密ログイン URL＋ゲートキー方式、CSRF 保護、アップロード検証の多層防御など）を重視した設計になっています。

## 主な機能

### 閲覧者向け

- **記事一覧（トップページ）** — 記事カード形式の一覧表示。1 ページ 4 件のページ番号方式ページ送り
- **キーワード × ジャンル検索** — ヘッダー検索バー、およびページ内検索エリアからタイトル・ハッシュタグを横断検索
- **ジャンル一覧** — アコーディオン形式のカテゴリグループ（ライフスタイル / 社会・経済 / 技術・勉強 / スポーツ / 娯楽 / 仕事）
- **ハッシュタグ絞り込み** — ジャンル選択中に、そのジャンル内で使われているタグでさらに絞り込み
- **記事詳細ページ**
  - Markdown → HTML 変換（`nl2br` / `toc` 拡張対応）
  - `[toc]` マーカーによる目次の自動生成
  - `[imgN]` タグによる本文中への画像＋キャプション埋め込み
  - `[map:場所名]` タグによる Google マップ埋め込み
  - `[youtube:URL]` タグによる YouTube 埋め込み（サムネイルをタップして再生する軽量なファサード方式）
  - 関連記事の自動表示（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新記事の 4 段階フォールバック、最大 4 件)
- **サイト統計** — 総投稿数・ハッシュタグ数・最終更新日をトップページに表示
- **自己紹介 / 使い方ページ**、レスポンシブ対応（スマホ用ドロワーメニュー、スクロール連動の固定ヘッダー）

### 管理者向け

- **新規投稿 / 編集 / 削除**（ログイン必須・CSRF トークン検証あり）
- **Markdown 編集ツールバー** — 見出し（H2/H3）・太字・目次・箇条書き・地図・YouTube・画像タグをワンクリック挿入（スティッキー表示対応）
- **画像アップロード** — 複数一括／1 枚ずつ追加、プレビュー、キャプション入力、個別削除（更新確定まで取り消し可能）
- **デフォルトサムネイル選択** — 画像なし記事用に 11 種類のプリセットから選択
- **公開 / 非公開トグル** — 非公開記事は管理者のみ閲覧可能
- **ジャンル管理** — プリセット（`constants.py` の `DEFAULT_GENRES`）＋独自ジャンルの新規作成
- **マイページ** — 自分の投稿一覧・使用ジャンル一覧・ニックネーム変更

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1（Application Factory パターン + Blueprint 構成） |
| ORM / マイグレーション | SQLAlchemy 2.0 / Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF 保護 | Flask-WTF（CSRFProtect） |
| データベース | PostgreSQL 18（Docker Compose で構築） |
| Markdown 変換 | Python-Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype（MIME タイプ判定） |
| フロントエンド | Jinja2 テンプレート + バニラ JS + CSS（Coastal Dawn テーマ） |

## ディレクトリ構成

```
.
├── app.py               # アプリ生成のエントリーポイント（create_app ファクトリ）
├── config.py            # .env 読み込み・環境変数の提供
├── constants.py         # デフォルトジャンルなどの定数
├── extensions.py        # db / login_manager / migrate インスタンス（循環インポート回避）
├── models.py            # ORM モデル（User / Post / Hashtag / post_hashtags）
├── docker-compose.yml   # PostgreSQL コンテナ定義（ホスト側ポート 15432）
├── requirements.txt
├── migrations/          # Alembic マイグレーション
├── views/
│   ├── auth.py          # ログイン・ログアウト（秘密 URL + ゲートキー + ロックアウト）
│   ├── blog.py          # 公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py         # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/           # Jinja2 テンプレート
└── static/
    ├── css/             # ページ別 CSS
    └── img/
        ├── posts/       # アップロード画像（UUID ファイル名）
        └── thbnails/    # デフォルトサムネイル
```

## データベース構成

| テーブル | 内容 |
|---|---|
| `user` | 管理者情報（ユーザー名・ハッシュ化パスワード・ニックネーム） |
| `post` | 記事（タイトル・本文・ジャンル・画像名・キャプション・公開設定・投稿/更新日時など） |
| `hashtag` | ハッシュタグ（名前は一意制約） |
| `post_hashtags` | Post ↔ Hashtag の多対多中間テーブル |

- 画像ファイル名はカンマ区切り、キャプションはタブ区切りで 1 カラムに格納（順番で対応付け）
- `updated_at` は「一度も更新されていない」状態を NULL で表現
- `hashtags` リレーションは `lazy='selectin'` で N+1 問題を回避

## セットアップ

### 1. 前提

- Python 3.10.x
- Docker / Docker Compose

### 2. リポジトリの取得と仮想環境

```bash
git clone <このリポジトリの URL>
cd <リポジトリ名>

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. `.env` ファイルの作成

プロジェクトルートに `.env` を作成します（`.gitignore` 済み）。

```env
# --- PostgreSQL（docker-compose と共有） ---
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=blogdb

# --- 管理者認証 ---
ADMIN_USERNAME=your-admin-name
# Werkzeug の generate_password_hash() で生成したハッシュ値を DB に登録して使用
ADMIN_PASSWORD=your-hashed-password

# --- ログインページの隠蔽（どちらも未設定だと起動しません / フェイルクローズ） ---
# 推測されにくいランダム文字列を推奨
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx
# 生成例: python -c "import secrets; print(secrets.token_urlsafe(32))"
ADMIN_GATE_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# --- セッション署名キー（本番では必須） ---
SECRET_KEY=your-secret-key

# --- ローカル開発時のみ（デバッグモード有効化） ---
FLASK_DEBUG=1
```

### 4. データベースの起動とマイグレーション

```bash
# PostgreSQL コンテナを起動（ホスト側 15432 番ポート）
docker compose up -d

# スキーマを適用
flask db upgrade
```

### 5. 管理者ユーザーの作成

`user` テーブルに管理者レコードを 1 件登録します（例: `flask shell` で実行）。

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

user = User(
    username="<ADMIN_USERNAME と同じ値>",
    password=generate_password_hash("<ログイン用パスワード>"),
)
db.session.add(user)
db.session.commit()
```

### 6. 起動

```bash
python app.py
# → http://127.0.0.1:5000
```

### 管理画面へのログイン方法

秘密 URL とゲートキーの両方が必要です。**初回のみ**次の形式でアクセスします。

```
http://127.0.0.1:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
```

合言葉の検証に成功するとゲート Cookie（有効期間 90 日）が発行され、以降は `?key=` なしの秘密 URL だけでログインページを開けます。Cookie を持たない訪問者には 404 を返し、ページの存在自体を隠します。

## セキュリティ設計

管理画面への到達には「① 秘密 URL → ② ゲートキー Cookie → ③ ユーザー名 → ④ パスワード」の 4 要素すべてが必要な多層防御構成です。

- **ログインページの隠蔽** — `ADMIN_LOGIN_PATH` による秘密 URL ＋ ゲートキー方式。未ログインで管理ページにアクセスしても 404 を返し、ログインページへ誘導しない（`login_view` 非設定 + `unauthorized_handler`）
- **フェイルクローズ** — `ADMIN_LOGIN_PATH` / `ADMIN_GATE_KEY` / 本番の `SECRET_KEY` が未設定なら起動拒否または常時 404
- **ブルートフォース対策** — ログイン 5 回連続失敗で 5 分間のセッションロックアウト
- **CSRF 保護** — CSRFProtect により全変更系リクエストでトークン検証
- **セッション Cookie** — `HttpOnly` / `SameSite=Lax` / 本番時 `Secure` を明示設定。ProxyFix によりリバースプロキシ（Render / Heroku 等）配下でも HTTPS を正しく判定
- **セキュリティヘッダー** — `X-Content-Type-Options: nosniff` / `X-Frame-Options: SAMEORIGIN` / `Referrer-Policy: strict-origin-when-cross-origin` を全レスポンスに付与
- **ファイルアップロードの多層防御** — 拡張子ホワイトリスト → filetype による MIME タイプ検証（拡張子偽装の検出）→ UUID によるファイル名ランダム化 → 30MB のリクエストサイズ制限
- **XSS 対策** — キャプション・地図ラベル・YouTube エラー表示など HTML を直組みする箇所は `markupsafe.escape()` で無害化。フロント側のタグプレビューも `textContent` ベースで構築
- **Open Redirect 対策** — 削除後のリダイレクト先はオリジン検証済みの referer のみ許可
- **整合性の保証** — 画像の物理削除は DB commit 成功後にのみ実行。commit 失敗時は新規保存ファイルを掃除し、DB とファイルの不整合を防止

## 記事本文で使える独自タグ

| タグ | 効果 |
|---|---|
| `[toc]` | その位置に目次を生成（未使用時は記事冒頭に自動表示） |
| `[img1]` `[img2]` … | アップロード画像を本文中に埋め込み（キャプション設定時は figure 表示） |
| `[map:東京スカイツリー]` | Google マップの埋め込み |
| `[youtube:https://...]` | YouTube 動画の埋め込み（クリックで再生開始） |

いずれも投稿・編集画面のツールバーからワンクリックで挿入できます。

## ライセンス / 備考

個人学習・ポートフォリオ用途のプロジェクトです。
本番運用でロックアウトをより強固にする場合は、Flask-Limiter + Redis による IP ベースのレート制限の導入を推奨します（`views/auth.py` のコメント参照）。