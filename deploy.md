# デプロイ手順書 — 構成B（Render ＋ Neon ＋ Cloudflare R2）

このブログアプリを **Render（Web）＋ Neon（PostgreSQL）＋ Cloudflare R2（投稿画像）** で無料・永続的に公開するための手順書です。

進行順序は次のとおりです。**先にコードを改修してローカルで確認 → その後クラウドを繋ぐ**流れが安全です。

1. コード改修（画像の保存先を R2 に対応させる）
2. Neon（PostgreSQL）のセットアップ
3. Cloudflare R2（画像ストレージ）のセットアップ
4. Render（Web）へのデプロイ
5. 初回のみ：マイグレーション適用と管理者ユーザー投入

---

## 1. コード改修

### 1-1. 新規ファイル `storage.py` を配置

プロジェクトルート（`app.py` と同じ階層）に `storage.py` を置きます（別途用意した `storage.py` をそのまま配置）。このモジュールが「投稿画像の保存 / 削除 / 表示URL」を一手に引き受けます。R2 の環境変数が未設定なら従来どおりローカルディスクに保存するので、**手元では R2 なしで開発を続けられます**。

### 1-2. `requirements.txt` に追記

末尾に次の2行を追加します。

```
boto3==1.35.0
gunicorn==23.0.0
```

> `boto3` は R2（S3互換API）へのアップロードに、`gunicorn` は本番用の WSGI サーバーに使います。バージョンは環境に合わせて調整可。

### 1-3. `views/admin.py` の改修

**(a) import を追加**（ファイル上部の import 群、`import config` の近く）

```python
import storage
```

**(b) `_save_images()` の中の保存処理を差し替え**

`file.save(save_path)` を使っていた箇所を `storage.save_image()` に変更します。検証ロジック（拡張子・MIMEチェック）とアトミックな掃除処理はそのまま維持し、**保存の一行だけ**を置き換えるのがポイントです。該当の `STEP 4` ブロックを次のように変更します。

変更前:
```python
            # STEP 4. 【第 3 層】UUID でファイル名をランダム化して保存
            filename  = f"{uuid.uuid4()}{ext}"
            save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)
            file.save(save_path)
            filename_list.append(filename)
```

変更後:
```python
            # STEP 4. 【第 3 層】UUID でファイル名をランダム化して保存（R2 または ローカル）
            filename = f"{uuid.uuid4()}{ext}"
            storage.save_image(file, filename, content_type=kind.mime)
            filename_list.append(filename)
```

**(c) `_delete_images()` を差し替え**

関数全体を次に置き換えます（ローカル削除ロジックを `storage.delete_image()` に集約）。

```python
def _delete_images(img_name_str: str) -> None:
    """
    post.img_name（カンマ区切りファイル名）をもとに投稿画像を削除する。
    実際の保存先（R2 / ローカル）の違いは storage モジュールが吸収する。
    必ず DB の commit 成功後に呼ぶこと（安全側に倒すため）。
    """
    if not img_name_str:
        return
    for img_file in img_name_str.split(','):
        name = img_file.strip()
        if name:
            storage.delete_image(name)
```

> `current_app` を `_delete_images` 内で使わなくなりますが、`_save_images` 側では引き続き不要になります。`os`／`current_app` の import は他でも使うため残してOKです。

### 1-4. `views/blog.py` の改修

**(a) import を追加**（上部の import 群）

```python
import storage
```

**(b) `[img]` 埋め込みの src を差し替え**（`detail()` 内の STEP 6 のループ）

投稿画像のURLをハードコードの `/static/img/posts/...` から `storage.image_url()` に変更します。

変更前:
```python
            if caption:
                img_tag = (
                    f'<figure class="post-figure">'
                    f'<img src="/static/img/posts/{img_file}" alt="{caption}" style="max-width:100%; height:auto;">'
                    f'<figcaption class="post-figcaption">{caption}</figcaption>'
                    f'</figure>'
                )
            else:
                img_tag = (
                    f'<span style="display:block; text-align:center; margin: 15px 0;">'
                    f'<img src="/static/img/posts/{img_file}" style="max-width:100%; height:auto;">'
                    f'</span>'
                )
```

変更後:
```python
            src = storage.image_url(img_file)
            if caption:
                img_tag = (
                    f'<figure class="post-figure">'
                    f'<img src="{src}" alt="{caption}" style="max-width:100%; height:auto;">'
                    f'<figcaption class="post-figcaption">{caption}</figcaption>'
                    f'</figure>'
                )
            else:
                img_tag = (
                    f'<span style="display:block; text-align:center; margin: 15px 0;">'
                    f'<img src="{src}" style="max-width:100%; height:auto;">'
                    f'</span>'
                )
```

### 1-5. `app.py` にテンプレート用ヘルパーを登録

テンプレートから投稿画像URLを生成できるよう、`create_app()` 内にコンテキストプロセッサを追加します。まず上部の import に:

```python
import storage
```

を加え、`create_app()` の中（`return app` の手前あたり）に次を追加します。

```python
    # ------------------------------------------------------------------
    # テンプレートから投稿画像URLを生成できるようにする
    # （R2モードなら公開URL、ローカルなら /static/img/posts/... を返す）
    # ------------------------------------------------------------------
    @app.context_processor
    def inject_template_helpers():
        return {'post_image_url': storage.image_url}
```

### 1-6. テンプレートの投稿画像URLを差し替え

投稿画像（`post.img_name`）を参照している箇所だけを `post_image_url()` に変えます。**`default_thumb` と `system-default.jpg` は `static/img/thbnails/` に同梱のままなので変更しません。**

対象は3ファイルの、次のパターンです。

- `templates/index.html`
- `templates/mypage.html`

変更前:
```html
{% set first_img = post.img_name.split(',')[0] %}
<img src="{{ url_for('static', filename='img/posts/' + first_img) }}" alt="{{ post.title }}" class="thumb-img">
```

変更後:
```html
{% set first_img = post.img_name.split(',')[0] %}
<img src="{{ post_image_url(first_img) }}" alt="{{ post.title }}" class="thumb-img">
```

- `templates/detail.html`（関連記事のサムネイル）

変更前:
```html
{% set first_img = rel.img_name.split(',')[0] %}
<img src="{{ url_for('static', filename='img/posts/' + first_img) }}"
     alt="{{ rel.title }}" loading="lazy">
```

変更後:
```html
{% set first_img = rel.img_name.split(',')[0] %}
<img src="{{ post_image_url(first_img) }}"
     alt="{{ rel.title }}" loading="lazy">
```

### 1-7. ローカルで動作確認

ここまでで、R2 の環境変数を設定していなければ**従来どおりローカルディスクに保存**されます。まずローカルで投稿・表示・削除が問題なく動くことを確認してからクラウドに進みます。

---

## 2. Neon（PostgreSQL）のセットアップ

1. <https://neon.com> でアカウント作成（クレジットカード不要）
2. プロジェクトを新規作成（リージョンは日本から近い **Singapore** などを選択）
3. ダッシュボードの「Connection string」をコピー。次のような形です:
   ```
   postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/dbname?sslmode=require
   ```
4. **psycopg3 を使うため、スキーム部分に `+psycopg` を足します**:
   ```
   postgresql+psycopg://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/dbname?sslmode=require
   ```
   この文字列を、あとで Render の環境変数 `DATABASE_URL` に設定します。

> `app.py` は `os.getenv("DATABASE_URL")` を読む設計なので、コード変更は不要です。

---

## 3. Cloudflare R2（画像ストレージ）のセットアップ

1. <https://dash.cloudflare.com> でアカウント作成し、サイドバーの **R2** を開く
   （R2 の有効化には**無料枠でもクレジットカード登録が必要**。超過しなければ課金されません）
2. **Create bucket** でバケットを作成（例: `mit-blog-images`）。名前は控えておく
3. バケットの **Settings → Public access** で **r2.dev の公開URL**を有効化する
   - 有効化すると `https://pub-xxxxxxxx.r2.dev` のような公開URLが発行される。これが `R2_PUBLIC_BASE_URL` になる
4. アカウントトップ右上などに表示される **Account ID** を控える（`R2_ACCOUNT_ID`）
5. **R2 → Manage R2 API Tokens → Create API Token** で、**Object Read & Write** 権限のトークンを作成
   - 発行される **Access Key ID**（`R2_ACCESS_KEY_ID`）と **Secret Access Key**（`R2_SECRET_ACCESS_KEY`）を控える（シークレットは再表示できないので必ず保存）

---

## 4. Render（Web）へのデプロイ

前提: コードを GitHub リポジトリに push しておく。

1. <https://render.com> でアカウント作成し、GitHub リポジトリを連携
2. **New → Web Service** を選び、対象リポジトリを指定
3. 設定を次のようにする:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn "app:create_app()" --workers 2 --bind 0.0.0.0:$PORT`
4. **Environment Variables** に以下をすべて登録する:

| キー | 値 |
|---|---|
| `SECRET_KEY` | ランダムな長い文字列（`python -c "import secrets; print(secrets.token_urlsafe(32))"`） |
| `FLASK_ENV` | `production` |
| `DATABASE_URL` | 手順2で作った `postgresql+psycopg://…?sslmode=require` |
| `ADMIN_USERNAME` | 管理者ユーザー名 |
| `ADMIN_PASSWORD` | ハッシュ化済みパスワード（`generate_password_hash` で生成） |
| `ADMIN_LOGIN_PATH` | 秘密のログインパス（例: `secret-login-xxxx`） |
| `ADMIN_GATE_KEY` | ゲートキー（ランダムな長い文字列） |
| `R2_ACCOUNT_ID` | Cloudflare の Account ID |
| `R2_ACCESS_KEY_ID` | R2 トークンのアクセスキーID |
| `R2_SECRET_ACCESS_KEY` | R2 トークンのシークレット |
| `R2_BUCKET` | バケット名（例: `mit-blog-images`） |
| `R2_PUBLIC_BASE_URL` | R2 の公開URL（例: `https://pub-xxxx.r2.dev`） |

5. デプロイを実行。完了すると `https://<サービス名>.onrender.com` で公開されます（HTTPS 自動付与）。

> **補足**: `DATABASE_URL` を設定することで `app.py` が本番モードと判定し、`SECRET_KEY` の必須チェックとセッションCookieの `Secure` 属性が有効になります。Render のリバースプロキシ配下でも、実装済みの `ProxyFix` により HTTPS が正しく判定されます。

---

## 5. 初回のみ：マイグレーション適用と管理者ユーザー投入

### 5-1. マイグレーション（テーブル作成）

Render の **Shell**（または Pre-Deploy Command）で、`FLASK_APP` を指定して実行します。

```bash
export FLASK_APP="app:create_app"
flask db upgrade
```

> Pre-Deploy Command に `flask db upgrade` を設定しておくと、以後のデプロイで自動適用されます（その場合も `FLASK_APP=app:create_app` を環境変数に入れておく）。

### 5-2. 管理者ユーザーの投入（1回だけ）

`ADMIN_USERNAME` / `ADMIN_PASSWORD` に対応する User レコードを1件作成します。Render の Shell で:

```bash
python -c "
from app import create_app
from extensions import db
from models import User
import os
app = create_app()
with app.app_context():
    if not User.query.filter_by(username=os.getenv('ADMIN_USERNAME')).first():
        db.session.add(User(
            username=os.getenv('ADMIN_USERNAME'),
            password=os.getenv('ADMIN_PASSWORD'),  # 既にハッシュ済みの値を格納
            nickname='管理者'
        ))
        db.session.commit()
        print('管理者ユーザーを作成しました')
    else:
        print('管理者ユーザーは既に存在します')
"
```

> `ADMIN_PASSWORD` には `generate_password_hash()` で生成した**ハッシュ値**を入れておく前提です（`views/auth.py` は `check_password_hash` で照合するため）。

---

## 動作確認チェックリスト

- [ ] トップページが表示される
- [ ] `https://<サービス名>.onrender.com/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>` からログインできる
- [ ] 記事を新規投稿し、**画像が R2 に保存され表示される**（R2ダッシュボードのバケットにファイルが増えることを確認）
- [ ] 記事を削除すると R2 上の画像も消える
- [ ] 再デプロイ後も過去記事の画像が消えていない（＝R2に永続化できている）

---

## 運用上の注意

- **コールドスタート**: Render 無料枠は15分無アクセスで休止し、初回復帰に最大1分かかります。個人ブログでは許容範囲ですが、気になる場合は将来的に有料枠や常時稼働の構成（構成A）への移行を検討してください。
- **Neon の休止**: 1週間無アクティビティで休止しますが、初回リクエストに1〜2秒程度の遅延が乗るだけです。
- **無料枠の上限**: R2 は 10GB ストレージ・egress 無料。Neon は 0.5GB/プロジェクト。個人ブログなら十分ですが、画像が増えてきたら R2 の使用量を時々確認してください。
- **秘密情報**: `.env` はリポジトリに含めず（`.gitignore` 済み）、本番の秘密情報はすべて Render の環境変数で管理してください。