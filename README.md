# MIT Blog — Flask 個人ブログアプリ

Flask + PostgreSQL で構築した、単一管理者向けの個人ブログアプリケーションです。
Markdown での記事執筆、画像・Google マップ・YouTube の埋め込み、ジャンル×ハッシュタグによる記事の絞り込みに対応しています。管理画面は「秘密の URL ＋ ゲートキー Cookie ＋ ID/パスワード」の多層防御で保護されています。

---

## 主な機能

### 閲覧者向け（一般公開ページ）
- **記事一覧（トップページ）**
  - ジャンル × キーワードを組み合わせたインページ検索
  - ジャンル選択中はハッシュタグによるさらに細かい絞り込みバーを表示
  - ページ番号方式のページ送り（1ページ 5 件、クライアントサイドで切り替え）
  - トップ表示時のみサイト統計（総投稿数・ハッシュタグ数・最終更新日）と自己紹介セクションを表示
- **記事詳細ページ**
  - Markdown → HTML 変換（`toc` / `nl2br` 拡張対応）
  - `[toc]` マーカーによる目次の自動生成（未使用時は記事先頭に自動表示）
  - `[imgN]` タグによる本文中への画像埋め込み（キャプション付き `<figure>` 対応）
  - `[map:場所名]` タグによる Google マップ埋め込み
  - `[youtube:URL]` タグによる YouTube 埋め込み（サムネイルをタップして再生する軽量なファサード形式）
  - 関連記事を最大 4 件表示（同ジャンル×同タグ → 同タグ → 同ジャンル → 最新記事の優先順で段階取得）
- **ジャンル一覧ページ**（アコーディオン形式のカテゴリグループ）
- **自己紹介ページ / 使い方ページ**
- スマホ対応（ドロワーメニュー・スクロール連動で隠れる固定ヘッダー）

### 管理者向け（要ログイン）
- **記事の投稿・編集・削除**
  - Markdown 編集ツールバー（H2/H3 見出し・太字・目次・リスト・地図・YouTube・画像タグの挿入）
  - 地図・YouTube はモーダル上でプレビューを確認してから本文に挿入
  - 画像の複数アップロード（一括選択 / 1枚ずつ追加、プレビュー・個別削除・キャプション入力）
  - 画像なし記事用のデフォルトサムネイル選択（11 種類）
  - 公開 / 非公開のトグル切り替え（非公開記事は管理者のみ閲覧可能）
  - ハッシュタグ入力（スペース・カンマ区切り、リアルタイムプレビュー、孤立タグの自動削除）
- **マイページ**（投稿一覧・使用ジャンル一覧・ニックネーム変更）

---

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1 |
| ORM / マイグレーション | Flask-SQLAlchemy（SQLAlchemy 2.0）/ Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF 保護 | Flask-WTF（CSRFProtect） |
| データベース | PostgreSQL 18（Docker Compose で起動） |
| Markdown 変換 | Python-Markdown（toc / nl2br 拡張） |
| フロントエンド | Jinja2 テンプレート + Vanilla JS + CSS（フレームワーク不使用） |

---

## ディレクトリ構成

```
.
├── app.py                 # アプリのエントリーポイント（Application Factory パターン）
├── config.py              # .env から環境変数を読み込むモジュール
├── constants.py           # デフォルトジャンルなどの定数定義
├── extensions.py          # db / login_manager / migrate のインスタンス定義（循環インポート回避）
├── models.py              # ORM モデル（User / Post / Hashtag / post_hashtags 中間テーブル）
├── docker-compose.yml     # PostgreSQL コンテナ定義
├── requirements.txt
├── migrations/            # Alembic マイグレーションファイル
├── views/
│   ├── auth.py            # ログイン・ログアウト（秘密 URL / ゲートキー / ロックアウト）
│   ├── blog.py            # 一般公開ページ（一覧・詳細・ジャンル・about・howto）
│   └── admin.py           # 管理者専用ページ（投稿・編集・削除・マイページ）
├── templates/             # Jinja2 テンプレート
└── static/
    ├── css/               # ページ・機能単位で分割した CSS
    └── img/
        ├── posts/         # アップロードされた記事画像（UUID ファイル名）
        └── thbnails/      # デフォルトサムネイル画像
```

---

## セットアップ手順

### 1. 前提条件
- Python 3.10.11
- Docker / Docker Compose

### 2. リポジトリの取得と仮想環境の準備

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

### 3. `.env` の作成

プロジェクトルートに `.env` ファイルを作成し、以下を設定します（`.env` は `.gitignore` 済み）。

```ini
# --- PostgreSQL 接続情報（docker-compose と共有） ---
POSTGRES_USER=bloguser
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=blogdb

# --- Flask セッション署名キー ---
# 生成例: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=your-random-secret-key

# --- 管理者認証情報 ---
ADMIN_USERNAME=admin
# ADMIN_PASSWORD には「ハッシュ化済み」の値を設定する
# 生成例: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('平文パスワード'))"
ADMIN_PASSWORD=pbkdf2:sha256:...

# --- ログインページの秘密 URL パス ---
# 例: secret-login-abc123 → /secret-login-abc123 でアクセス
ADMIN_LOGIN_PATH=secret-login-abc123

# --- ゲートキー（ログインページ表示用の合言葉） ---
# 生成例: python -c "import secrets; print(secrets.token_urlsafe(32))"
ADMIN_GATE_KEY=your-random-gate-key
```

> **注意:** `ADMIN_GATE_KEY` が未設定の場合、フェイルクローズ設計によりログインページは常に 404 を返します（設定忘れで無防備になる事故の防止）。

### 4. データベースの起動とマイグレーション

```bash
# PostgreSQL コンテナを起動（ホスト側 55432 番ポートにマッピング）
docker compose up -d

# テーブルを作成
flask db upgrade
```

### 5. 管理者ユーザーの登録

`user` テーブルに管理者レコードを 1 件登録します（`flask shell` を使う例）。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import config

user = User(
    username=config.ADMIN_USERNAME,
    password=generate_password_hash("平文パスワード"),  # .env の ADMIN_PASSWORD と同じ元パスワード
    nickname="お好みの表示名",
)
db.session.add(user)
db.session.commit()
```

### 6. 起動

```bash
python app.py
```

`http://localhost:5000` でトップページが表示されます。

---

## 管理画面へのログイン方法

ログインページは通常の URL からは到達できません。以下の手順でアクセスします。

1. **初回のみ**、ゲートキー付きの URL にアクセスする
   ```
   http://localhost:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
   ```
   → サーバーがゲート Cookie（有効期間 90 日）を発行し、`?key=` なしの URL へ自動リダイレクトします。
2. 以降は `http://localhost:5000/<ADMIN_LOGIN_PATH>` だけでログインページが開きます。
3. ユーザー名・パスワードを入力してログインします。

Cookie を持たない訪問者が秘密 URL にアクセスしても **404** が返り、ページの存在自体が隠されます。

---

## セキュリティ設計

本アプリは学習を兼ねて、多層防御を意識した実装になっています。

| 対策 | 内容 |
|---|---|
| ログインページの隠蔽 | 秘密の URL（`ADMIN_LOGIN_PATH`）＋ ゲートキー Cookie（`ADMIN_GATE_KEY`）。未通過の訪問者には 404 を返す |
| 未ログインアクセスの偽装 | `@login_required` ページへの未認証アクセスはログイン画面へ誘導せず 404 を返し、管理ページの存在を隠す |
| ブルートフォース対策 | ログイン 5 回連続失敗で 5 分間のセッションロックアウト |
| パスワード保護 | Werkzeug によるハッシュ化保存・照合（平文は保存しない） |
| CSRF 対策 | Flask-WTF の `CSRFProtect` を全フォームに適用 |
| ファイルアップロード検証 | ①拡張子ホワイトリスト → ②マジックナンバーによる MIME 判定（filetype）→ ③`secure_filename` によるサニタイズ → ④UUID によるファイル名ランダム化 → ⑤30MB の容量制限 |
| Open Redirect 対策 | 削除後のリダイレクト時に referer のオリジンを検証 |
| 本番起動時の安全確認 | 本番環境で `SECRET_KEY` 未設定の場合は起動を拒否 |

> セッションベースのロックアウトはブラウザを変えると回避可能です。本番運用では Flask-Limiter + Redis 等による IP ベースの制限を併用することを推奨します。

---

## 記事本文で使える独自タグ

| タグ | 効果 |
|---|---|
| `[toc]` | その位置に目次を生成（未使用時は記事先頭に自動表示） |
| `[img1]` `[img2]` … | アップロードした N 番目の画像を埋め込み（キャプション設定時は `<figure>` 化） |
| `[map:東京スカイツリー]` | Google マップの埋め込み |
| `[youtube:動画URL または ID]` | YouTube 動画の埋め込み（クリックで再生開始） |

いずれも投稿・編集画面のツールバーからワンクリック／モーダル経由で挿入できます。

---

## 本番デプロイについて

- 環境変数 `DATABASE_URL` を設定すると、ローカル用 URL の代わりにその接続先を使用します（Heroku / Render などの PaaS を想定）。
- `DATABASE_URL` または `FLASK_ENV=production` が設定されていると本番環境と判定され、`SECRET_KEY` 未設定時は起動エラーになります。
- `app.run(debug=True)` は開発用です。本番では Gunicorn 等の WSGI サーバーを使用してください。

## ライセンス

個人学習・ポートフォリオ用途のプロジェクトです。