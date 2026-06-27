# MIT Blog

Flask + PostgreSQL で構築した個人ブログアプリです。マークダウン記事投稿・画像アップロード・ハッシュタグ管理・YouTube / Google Maps 埋め込みなどに対応しています。

---

## 機能一覧

### 公開機能（誰でも閲覧可）
- 記事一覧表示（サムネイル付きカード形式）
- キーワード検索（タイトル・ハッシュタグを横断）
- ジャンル絞り込み・ハッシュタグ絞り込み
- 記事詳細表示（マークダウンレンダリング）
- 目次（`[toc]` マーカー）自動生成
- Google Maps 埋め込み（`[map:場所名]` 記法）
- YouTube 埋め込み（`[youtube:URL]` 記法、ファサード遅延読み込み）
- 関連記事自動表示（同ジャンル × 同タグ優先）
- レスポンシブデザイン（PC / スマホ対応）

### 管理者機能（ログイン必須）
- 記事の新規作成・編集・削除
- マークダウンツールバー（H2/H3/太字/目次/地図/YouTube/画像挿入）
- 複数画像アップロード（最大 30 MB）＋ キャプション入力
- デフォルトサムネイル選択（11 種）
- ジャンル選択 / 新規ジャンル作成
- ハッシュタグ管理（スペース・カンマ区切り入力、孤立タグの自動削除）
- 公開 / 非公開切り替え
- マイページ（投稿一覧・ニックネーム変更・使用ジャンル一覧）

---

## 技術スタック

| 区分 | 技術 |
|------|------|
| 言語 | Python 3.10 |
| フレームワーク | Flask 3.x |
| DB | PostgreSQL 18（Docker）|
| ORM | SQLAlchemy 2.x / Flask-SQLAlchemy |
| マイグレーション | Flask-Migrate（Alembic）|
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF |
| マークダウン | Python-Markdown（toc / nl2br 拡張）|
| 画像検証 | filetype（MIME タイプ判定）|
| フロントエンド | Vanilla JS / CSS（フレームワークなし）|

---

## ディレクトリ構成

```
.
├── app.py              # Application Factory（エントリポイント）
├── config.py           # 環境変数の読み込み
├── constants.py        # デフォルトジャンル一覧
├── extensions.py       # db / login_manager / migrate のインスタンス
├── models.py           # User / Post / Hashtag モデル
├── requirements.txt
├── docker-compose.yml  # PostgreSQL コンテナ定義
├── migrations/         # Alembic マイグレーションファイル
├── views/
│   ├── auth.py         # ログイン・ログアウト
│   ├── blog.py         # 公開ページ（一覧・詳細・ジャンル）
│   └── admin.py        # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/          # Jinja2 テンプレート
└── static/
    ├── css/
    └── img/
        ├── posts/      # アップロード画像の保存先
        └── thbnails/   # デフォルトサムネイル画像
```

---

## セットアップ

### 前提条件

- Python 3.10 以上
- Docker / Docker Compose

### 1. リポジトリのクローン

```bash
git clone <your-repo-url>
cd <repo-dir>
```

### 2. `.env` ファイルの作成

プロジェクトルートに `.env` を作成し、以下の環境変数を設定します。

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your-secret-key

# 管理者
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=hashed_password   # werkzeug.security.generate_password_hash() で生成
ADMIN_LOGIN_PATH=your-secret-login-path  # 例: secret-login-abc123
```

管理者パスワードのハッシュ値は Python で生成できます。

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

### 3. データベースの起動

```bash
docker compose up -d
```

### 4. Python 仮想環境と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. DB マイグレーションの実行

```bash
flask db upgrade
```

### 6. 管理者ユーザーの登録

Flask シェルで初期ユーザーを作成します。

```bash
flask shell
```

```python
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import os

user = User(
    username=os.getenv("ADMIN_USERNAME"),
    password=os.getenv("ADMIN_PASSWORD"),  # すでにハッシュ化済みの値
)
db.session.add(user)
db.session.commit()
print("管理者ユーザーを作成しました。")
```

### 7. 開発サーバーの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスすると一覧ページが表示されます。

---

## 管理者ログイン

ログインページの URL は `.env` の `ADMIN_LOGIN_PATH` で設定した値によって決まります。

```
http://localhost:5000/<ADMIN_LOGIN_PATH>
```

ログイン後は記事の投稿・編集・削除・マイページが利用できます。

---

## マークダウン記法

本文では以下の記法を使用できます。

| 記法 | 出力 |
|------|------|
| `## 見出し` | H2 見出し |
| `### 見出し` | H3 見出し |
| `**太字**` | **太字** |
| `[toc]` | 目次を自動生成 |
| `[img1]` | 1 枚目のアップロード画像を挿入 |
| `[map:東京スカイツリー]` | Google Maps を埋め込み |
| `[youtube:https://youtu.be/XXXXX]` | YouTube 動画を埋め込み（クリックで再生）|

---

## セキュリティ対策

- **CSRF 対策**: Flask-WTF によるトークン検証（全フォームに適用）
- **パスワード管理**: Werkzeug によるハッシュ化（平文保存なし）
- **ログインページ隠蔽**: `.env` で URL パスを任意に設定
- **ブルートフォース対策**: 5 回連続失敗で 5 分間ロックアウト
- **画像検証**: 拡張子チェック + filetype による MIME タイプ検証（拡張子偽装を検出）
- **ファイル名サニタイズ**: `secure_filename()` + UUID によるランダム化
- **Open Redirect 対策**: リダイレクト時の同一オリジン検証
- **アップロード容量制限**: 最大 30 MB

---

## 本番環境へのデプロイ

本番環境では以下の環境変数を追加で設定してください。

```env
DATABASE_URL=postgresql+psycopg://user:pass@host:port/dbname
FLASK_ENV=production
SECRET_KEY=<十分に長くランダムな文字列>
```

`DATABASE_URL` が設定されていると自動的に本番モードとして動作し、`SECRET_KEY` が未設定の場合は起動時にエラーを返します。

---

## ライセンス

このプロジェクトは個人利用・学習目的で作成されました。