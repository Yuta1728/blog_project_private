# MIT Blog — 個人ブログアプリ

Flask + PostgreSQL で構築した個人向けブログアプリです。管理者1名がログインして記事を投稿・管理し、閲覧者はログイン不要でトップページから記事を読むことができます。

---

## 主な機能

- **記事の投稿・編集・削除**（管理者のみ）
- **公開 / 非公開の切り替え**（非公開記事は管理者のみ閲覧可）
- **マークダウン記法**による本文入力（見出し・太字・目次 `[toc]`）
- **画像の複数アップロード**と本文への挿入（`[img1]`, `[img2]` …）
- **画像キャプション**の設定・表示（`<figure>` / `<figcaption>` で出力）
- **デフォルトサムネイル**の選択（アップロード画像がない場合のカバー画像）
- **ジャンル分類**（選択式 + 新規作成）
- **ハッシュタグ**の付与・絞り込み表示
- **キーワード検索**（タイトル部分一致）
- **ニックネーム変更**（マイページ）
- **「もっと見る」ボタン**による段階的なカード表示（JS）
- **CSRF 保護**（Flask-WTF）
- **ファイル検証**（拡張子チェック + マジックナンバー検証 by `filetype`）
- **レスポンシブデザイン**（PC / スマホ対応、ドロワーメニュー）

---

## 技術スタック

| 分類 | 使用技術 |
|---|---|
| バックエンド | Python 3.10 / Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| DB マイグレーション | Flask-Migrate 4.1（Alembic） |
| 認証 | Flask-Login 0.6 |
| CSRF 保護 | Flask-WTF 1.2 |
| マークダウン | Markdown 3.9（`toc`, `nl2br` 拡張） |
| ファイル検証 | filetype 1.2 |
| DB | PostgreSQL 18（Docker） |
| フロントエンド | HTML / CSS / Vanilla JS |

---

## ディレクトリ構成

```
.
├── app.py                  # アプリファクトリ（create_app）
├── config.py               # 環境変数の読み込み
├── extensions.py           # db / login_manager / migrate の初期化
├── models.py               # Post / User / Hashtag モデル
├── views/
│   ├── auth.py             # ログイン・ログアウト
│   ├── blog.py             # トップ・詳細・ジャンル一覧（閲覧系）
│   └── admin.py            # 投稿・編集・削除・マイページ（管理系）
├── templates/              # Jinja2 テンプレート
├── static/
│   ├── css/                # テーマ別スタイルシート
│   └── img/
│       ├── posts/          # アップロード画像の保存先
│       └── thbnails/       # デフォルトサムネイル画像
├── migrations/             # Alembic マイグレーションファイル
├── init/                   # Docker 初期化 SQL
└── docker-compose.yml      # PostgreSQL コンテナ定義
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd <repository-dir>
```

### 2. 環境変数の設定

`.env` ファイルをプロジェクトルートに作成します。

```env
# PostgreSQL 接続情報
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask セッション暗号化キー
SECRET_KEY=your-secret-key-here

# 管理者アカウント情報
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password

# ログイン画面への秘密の URL パス（例: admin-login）
ADMIN_LOGIN_PATH=your-secret-login-path
```

### 3. Docker で PostgreSQL を起動

```bash
docker compose up -d
```

### 4. Python 仮想環境の作成と依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. DB マイグレーションの実行

```bash
flask db upgrade
```

### 6. 開発サーバーの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` を開くとトップページが表示されます。  
ログインは `http://localhost:5000/<ADMIN_LOGIN_PATH>` から行います。

---

## 画像アップロードについて

- 対応形式：PNG / JPG / GIF / WebP
- 1リクエストあたりの上限：**30 MB**
- ファイル名は `uuid4` で自動リネームされ `static/img/posts/` に保存されます
- 拡張子チェックに加え、`filetype` ライブラリによるマジックナンバー検証を行い、画像偽装を防止しています

---

## 本番環境へのデプロイ時の注意

- 環境変数 `DATABASE_URL` または `FLASK_ENV=production` が設定されている場合、`SECRET_KEY` が未設定だとアプリの起動を拒否します
- `static/img/posts/` 以下のアップロード画像はバージョン管理対象外です（`.gitignore` 参照）
- 本番環境では `debug=False` で起動してください

---

## マイグレーション履歴

| リビジョン | 内容 |
|---|---|
| `f8bd789a6d74` | 初期リビジョン（`is_published` NOT NULL 化） |
| `42dc0996903d` | `post.default_thumb` カラム追加 |
| `add_hashtag_tables` | `hashtag` / `post_hashtags` テーブル追加 |
| `add_img_captions` | `post.img_captions` カラム追加 |