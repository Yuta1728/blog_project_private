# MIT Blog

Flask 製の個人用ブログアプリケーションです。単一の管理者が記事を投稿・管理し、閲覧者は誰でも公開記事を読めるという構成になっています。Markdown での執筆支援、画像アップロード、地図・YouTube 埋め込み、ハッシュタグ、ジャンル絞り込みなどの機能を備え、管理画面には多層的なセキュリティ対策を施しています。

---

## 主な機能

### 閲覧者向け
- **記事一覧・詳細表示**（Markdown → HTML 変換）
- **キーワード検索**（タイトル・ハッシュタグの部分一致）
- **ジャンル絞り込み**（アコーディオン形式のジャンル一覧）
- **ハッシュタグ絞り込み**（ジャンル × タグの複合絞り込み）
- **関連記事表示**（同ジャンル・同タグを優先して最大 4 件）
- **サイト統計**（総投稿数・ハッシュタグ数・最終更新日）
- **地図埋め込み**（`[map:場所名]` → Google マップ iframe）
- **YouTube 埋め込み**（`[youtube:URL]` → サムネイル＋再生ボタンのファサード方式）
- **目次の自動生成**（`[toc]` マーカーまたは記事冒頭）
- レスポンシブ対応（スマホ用ドロワーメニュー、スクロール連動ヘッダー）

### 管理者向け
- **記事の作成 / 編集 / 削除**
- **Markdown 編集ツールバー**（H2/H3 見出し・太字・目次・箇条書き・地図・YouTube 挿入）
- **複数画像アップロード**（一括選択 / 1 枚ずつ追加、キャプション付与、個別削除）
- **デフォルトサムネイル選択**（画像未添付時の代替画像）
- **公開 / 非公開の切り替え**
- **ハッシュタグ入力**（スペース・カンマ区切り、リアルタイムプレビュー）
- **マイページ**（投稿一覧・使用ジャンル一覧・ニックネーム変更）

---

## 技術スタック

| 分類 | 使用技術 |
|------|----------|
| 言語 | Python 3.10.11 |
| フレームワーク | Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| マイグレーション | Flask-Migrate（Alembic） |
| 認証 | Flask-Login |
| CSRF 対策 | Flask-WTF |
| データベース | PostgreSQL 18（Docker） |
| DB ドライバ | psycopg 3 |
| Markdown 変換 | Markdown（toc / nl2br 拡張） |
| ファイル検証 | filetype |
| 環境変数管理 | python-dotenv |

設計面では **Application Factory パターン**（`create_app()`）を採用し、拡張機能インスタンスを `extensions.py` に分離することで循環インポートを回避しています。

---

## ディレクトリ構成

```
.
├── app.py                # エントリーポイント（create_app ファクトリ）
├── config.py             # 環境変数の読み込み
├── constants.py          # デフォルトジャンル一覧
├── extensions.py         # db / login_manager / migrate インスタンス
├── models.py             # ORM モデル（Post / Hashtag / User）
├── requirements.txt
├── docker-compose.yml    # PostgreSQL コンテナ定義
├── migrations/           # Alembic マイグレーション
├── views/
│   ├── blog.py           # 一般公開ページ（一覧・詳細・ジャンル）
│   ├── auth.py           # ログイン / ログアウト
│   └── admin.py          # 管理者ページ（投稿・編集・削除・マイページ）
├── templates/            # Jinja2 テンプレート
└── static/
    ├── css/              # ページ別スタイルシート
    └── img/              # 投稿画像・サムネイル
```

### データモデル

- **User** … 管理者アカウント（ユーザー名・ハッシュ化パスワード・ニックネーム）
- **Post** … 記事（タイトル・本文・ジャンル・画像・公開設定・日時など）
- **Hashtag** … ハッシュタグ
- **post_hashtags** … Post ↔ Hashtag の多対多を仲介する中間テーブル

`User (1) — (多) Post`、`Post (多) — (多) Hashtag` の関係です。

---

## セットアップ

### 1. 前提条件
- Python 3.10.11
- Docker / Docker Compose（PostgreSQL 用）

### 2. リポジトリの取得と依存関係のインストール

```bash
git clone <このリポジトリの URL>
cd <プロジェクトフォルダ>

python -m venv venv
source venv/bin/activate        # Windows は venv\Scripts\activate

pip install -r requirements.txt
```

### 3. 環境変数の設定（`.env` の作成）

プロジェクトルートに `.env` ファイルを作成し、以下を設定します。`.env` は `.gitignore` 済みなのでリポジトリには含まれません。

```env
# PostgreSQL 接続情報（docker-compose.yml と同じ値にする）
POSTGRES_USER=blog_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=personal_blog

# 管理者認証情報
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<ハッシュ化済みパスワード>   # 下記コマンドで生成
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx       # 推測されにくい秘密のログイン URL

# ゲートキー（ログインページを表示するための合言葉）
ADMIN_GATE_KEY=<ランダムな長い文字列>

# セッション・CSRF 署名用の秘密鍵
SECRET_KEY=<ランダムな長い文字列>
```

**パスワードハッシュの生成例:**

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('あなたのパスワード'))"
```

**ランダム文字列（SECRET_KEY / ADMIN_GATE_KEY）の生成例:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> `ADMIN_USERNAME` と `ADMIN_PASSWORD` に対応するユーザーは、あらかじめ DB に登録しておく必要があります（DBeaver 等で手動投入、または初期化スクリプトで作成）。

### 4. データベースの起動

```bash
docker compose up -d
```

`docker-compose.yml` の設定により、ホストの **15432 番ポート**でコンテナ内の PostgreSQL（5432）にアクセスできます。

### 5. マイグレーションの適用

```bash
flask db upgrade
```

### 6. アプリの起動

```bash
# 開発モード（自動リロード・トレースバック表示を有効化する場合）
export FLASK_DEBUG=1        # Windows は set FLASK_DEBUG=1
python app.py
```

デフォルトでは `http://localhost:5000` で起動します。

---

## 使い方

### 管理者ログイン

ログインページの URL 自体が隠蔽されているため、以下の手順でアクセスします。

1. ブラウザで `http://localhost:5000/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>` を開く
2. 合言葉（`key`）が正しければゲート通過用の Cookie が発行され、`key` なしの URL にリダイレクトされる
3. 以降 90 日間は Cookie だけでログインページへアクセス可能
4. ユーザー名・パスワードを入力してログイン

Cookie を持たない第三者には **404 が返され、ページの存在自体が隠されます**。

### 本文中で使える独自タグ

Markdown に加えて、以下の独自記法が利用できます（編集ツールバーからも挿入可能）。

| 記法 | 効果 |
|------|------|
| `[img1]` `[img2]` … | アップロードした N 番目の画像を挿入 |
| `[toc]` | その位置に目次を展開 |
| `[map:東京スカイツリー]` | Google マップの地図を埋め込み |
| `[youtube:https://youtu.be/xxxx]` | YouTube 動画を埋め込み（クリックで再生開始） |

---

## セキュリティ対策

本アプリは学習を兼ねて、以下の多層防御を実装しています。

### 認証・アクセス制御
- ログイン URL の隠蔽（`ADMIN_LOGIN_PATH`）
- **ゲートキー方式**：合言葉 Cookie を持たない訪問者にはログインページを 404 で隠す（フェイルクローズ設計）
- 未ログインで管理ページへアクセスした場合は 404 を返し、ページの存在を秘匿
- **ブルートフォース対策**：5 回連続失敗で 5 分間ロックアウト
- パスワードはハッシュ値で照合（平文比較なし）
- ログイン失敗時に「どちらが誤りか」を明示しない（ユーザー名列挙の防止）

### リクエスト・セッション保護
- 全変更系リクエストへの CSRF トークン強制（Flask-WTF）
- セッション Cookie に `HttpOnly` / `SameSite=Lax` / `Secure`（本番）を明示付与
- リバースプロキシ対応（`ProxyFix`）による HTTPS 判定補正
- Open Redirect 対策（リダイレクト先の同一オリジン検証）

### 入力・出力の保護
- 画像アップロードの検証：**拡張子チェック → MIME タイプチェック（中身の確認）→ UUID リネーム**
- アップロードサイズ上限 30MB（DoS 対策）
- XSS 対策：キャプション・地図・YouTube 出力を `escape()` で無害化、プレビューは `innerHTML` ではなく DOM API で構築

### レスポンスヘッダー
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`

### 本番運用
- `SECRET_KEY` 未設定時は本番環境での起動を拒否
- `ADMIN_LOGIN_PATH` 未設定時はアプリ起動を拒否
- デバッグモードは `FLASK_DEBUG=1` を明示した非本番環境でのみ有効

---

## データ整合性のルール（開発者向けメモ）

画像ファイルと DB の不整合を防ぐため、投稿・編集・削除の各処理では次の順序を厳守しています。

1. 画像を保存（`_save_images` はアトミック動作：全成功 or 全掃除）
2. DB 変更をセッションに積む
3. `commit()`
   - 失敗 → `rollback` ＋ 今回保存した新ファイルを掃除
   - 成功 → **ここで初めて**削除対象の旧ファイルを物理削除

これにより「DB は残っているのに画像だけ消えた」といった復旧不能な不整合を回避しています。

---

## ライセンス

個人利用・学習目的のプロジェクトです。