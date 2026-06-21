# MIT Blog

Flask製のパーソナルブログアプリケーション。マークダウン記事投稿・ハッシュタグ管理・地図埋め込みなどの機能を備えた、シングル管理者向けのブログシステムです。

---

## 主な機能

- **記事投稿・編集・削除** — マークダウン形式で記事を作成。見出し・太字・目次（`[toc]`）のツールバーボタン付き
- **画像アップロード** — 複数画像対応。`[img1]`・`[img2]` プレースホルダーで本文内の任意の位置に挿入可能。各画像にキャプション設定あり
- **地図埋め込み** — `[map:場所名]` で Google Maps を記事内に表示。投稿画面のモーダルからプレビュー付きで挿入可能
- **ハッシュタグ** — 記事に複数タグを設定。一覧画面でタグによる絞り込みが可能
- **ジャンル管理** — プリセットジャンルに加え、独自ジャンルの作成も可能
- **公開/非公開設定** — 記事ごとに公開状態を切り替え可能。非公開記事は管理者のみ閲覧可
- **キーワード検索** — タイトルおよびハッシュタグをまたいだ横断検索
- **管理者認証** — URL 隠蔽・連続失敗ロックアウト（5回失敗で5分間ロック）によるセキュアなログイン
- **レスポンシブデザイン** — PC・スマホ対応。モバイルではドロワーナビゲーション

---

## 技術スタック

| 分類 | 採用技術 |
|------|----------|
| フレームワーク | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| DB マイグレーション | Flask-Migrate (Alembic) |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF |
| データベース | PostgreSQL |
| マークダウン変換 | Python-Markdown（`toc`・`nl2br` 拡張）|
| ファイル検証 | filetype（MIME タイプ判定）|
| テンプレート | Jinja2 |
| コンテナ | Docker / Docker Compose |
| パスワードハッシュ | Werkzeug |

---

## ディレクトリ構成

```
.
├── app.py              # Application Factory（エントリーポイント）
├── config.py           # 環境変数の読み込み
├── constants.py        # DEFAULT_GENRES など定数
├── extensions.py       # db / login_manager / migrate インスタンス
├── models.py           # DB モデル（User, Post, Hashtag）
├── requirements.txt
├── docker-compose.yml
├── migrations/         # Alembic マイグレーションファイル
├── views/
│   ├── auth.py         # ログイン・ログアウト
│   ├── blog.py         # 一般公開ページ（一覧・詳細・ジャンル）
│   └── admin.py        # 管理者専用ページ（投稿・編集・削除・マイページ）
├── templates/          # Jinja2 テンプレート
└── static/
    ├── css/            # スタイルシート
    └── img/
        ├── posts/      # アップロード画像の保存先
        └── thbnails/   # デフォルトサムネイル画像
```

---

## セットアップ

### 前提条件

- Python 3.10
- Docker / Docker Compose

### 手順

**1. リポジトリをクローン**

```bash
git clone <repository-url>
cd <project-directory>
```

**2. `.env` ファイルを作成**

```env
# PostgreSQL
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

# Flask
SECRET_KEY=your-secret-key-here

# 管理者認証
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=<werkzeug でハッシュ化したパスワード>
ADMIN_LOGIN_PATH=your-secret-login-path

# 本番環境のみ（Heroku / Render など）
# DATABASE_URL=postgresql://...
```

`ADMIN_PASSWORD` は Werkzeug でハッシュ化した値を使用します：

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

**3. Docker で PostgreSQL を起動**

```bash
docker-compose up -d
```

**4. Python 仮想環境と依存パッケージのインストール**

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**5. DB マイグレーションの実行**

```bash
flask db upgrade
```

**6. 開発サーバーの起動**

```bash
python app.py
# または
flask run
```

`http://localhost:5000` でアクセスできます。

---

## 管理者ログイン

ログインページは `.env` の `ADMIN_LOGIN_PATH` で設定した秘密の URL からアクセスします。

```
http://localhost:5000/<ADMIN_LOGIN_PATH>
```

セキュリティ仕様：
- 5回連続で失敗すると5分間ロックアウト
- パスワードはハッシュ値のみ保存（平文は保持しない）
- CSRF トークンによるフォーム保護

---

## 記事本文の記法

| 記法 | 説明 |
|------|------|
| `## 見出し` | H2 見出し（目次に含まれる） |
| `### 見出し` | H3 見出し（目次に含まれる） |
| `**テキスト**` | 太字 |
| `[toc]` | 目次を挿入（H2・H3 から自動生成） |
| `[img1]` `[img2]` | アップロード画像を挿入（番号順） |
| `[map:場所名]` | Google Maps を埋め込み |

---

## セキュリティ対策

- **画像アップロード**: 拡張子チェック（第1層）＋ MIME タイプチェック（第2層）＋ `secure_filename` サニタイズ（第3層）＋ UUID ランダムファイル名（第4層）＋ 30MB 容量制限（第5層）
- **CSRF 保護**: Flask-WTF により全フォームにトークン検証を強制
- **Open Redirect 対策**: 削除後のリダイレクト先を同一オリジンに限定
- **ブルートフォース対策**: ログイン連続失敗でセッションロックアウト
- **本番環境の SECRET_KEY 検証**: 未設定の場合は起動時にエラーで終了

---

## ライセンス

このプロジェクトは個人利用を目的として開発されたものです。