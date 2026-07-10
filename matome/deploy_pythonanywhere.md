# PythonAnywhere デプロイ手順書（GitHub から公開）

このブログアプリを **PythonAnywhere の無料枠**に、**GitHub 経由**で一時公開するための手順書です。データベースは無料枠でも使える **SQLite** に切り替えて運用します。

---

## 0. この手順で行うことの全体像

```
[自分のPC]                         [GitHub]                 [PythonAnywhere]
 修正ファイルを反映  ──push──▶   リポジトリ  ──git clone──▶   サーバー上に配置
                                                              ├ 仮想環境を作成
                                                              ├ pip install
                                                              ├ .env を作成
                                                              ├ init_db.py で初期化
                                                              └ Web タブで公開設定 → Reload
                                                                      │
                                                              https://<ユーザー名>.pythonanywhere.com
```

ポイントは3つです。

1. DB は PostgreSQL ではなく **SQLite**（`USE_SQLITE=1` を設定するだけ）
2. テーブルと管理者ユーザーは **`init_db.py`** で作成（マイグレーション不要）
3. `.env` は **GitHub に含めず**、PythonAnywhere 上で手動作成する

---

## 1. 変更したファイル（何が変わったか）

| ファイル | 変更内容 |
|----------|----------|
| `app.py` | DB 接続に SQLite 対応を追加。`USE_SQLITE=1` でプロジェクト内 `instance/blog.db` を使う |
| `config.py` | `.env` を config.py と同じ場所から確実に読み込むように修正（WSGI 起動対策） |
| `init_db.py`（新規） | `db.create_all()` でテーブル作成＋管理者ユーザー作成を一括実行 |
| `requirements-pythonanywhere.txt`（新規） | PostgreSQL ドライバ（psycopg 系）を除いた依存一覧 |
| `wsgi_pythonanywhere_sample.py`（新規） | PythonAnywhere の WSGI 設定に貼り付ける内容のサンプル |

これらのファイルを既存プロジェクトに上書き・追加してください。配置場所は以下のとおりプロジェクト直下です。

```
<プロジェクト>/
├── app.py                          ← 上書き
├── config.py                       ← 上書き
├── init_db.py                      ← 新規追加
├── requirements.txt                （そのまま。ローカルPostgres用に残す）
├── requirements-pythonanywhere.txt ← 新規追加
├── wsgi_pythonanywhere_sample.py   ← 新規追加（参考用）
├── constants.py
├── extensions.py
├── models.py
├── views/
├── templates/
├── static/
│   └── img/
│       └── posts/                  ← アップロード画像の保存先（永続）
├── instance/                       ← 自動生成。SQLite の blog.db がここに作られる
│   └── blog.db
└── .env                            ← GitHubには含めない。サーバー上で作成する
```

> `instance/blog.db` はアプリ起動時に自動作成されるディレクトリ・ファイルです。`.gitignore` に `*.db` があるため Git には含まれません。

---

## 2. 事前準備（自分のPC側）

### 2-1. 変更ファイルを反映して GitHub に push

修正した `app.py` / `config.py` と、新規の `init_db.py` / `requirements-pythonanywhere.txt` / `wsgi_pythonanywhere_sample.py` をプロジェクトに配置します。

`.gitignore` に以下が含まれていることを確認してください（元から入っています）。含まれていないと `.env` や DB ファイルが公開されてしまいます。

```
.env
.env.*
*.db
*.sqlite3
```

確認できたら push します。

```bash
git add .
git commit -m "PythonAnywhere向けにSQLite対応を追加"
git push origin main
```

### 2-2. リポジトリを private にするか確認

一時公開とはいえ、管理画面を持つアプリです。リポジトリは **private** を推奨します（public でも `.env` を含めていなければ致命的ではありませんが、念のため）。

---

## 3. PythonAnywhere でのデプロイ手順

### 3-1. アカウント作成

1. https://www.pythonanywhere.com/ にアクセス
2. 「Pricing & signup」→ 無料の **Beginner** アカウントを作成（クレジットカード不要）
3. ログインするとダッシュボードが表示される

> 無料枠では公開先が `https://<ユーザー名>.pythonanywhere.com` になります。

### 3-2. Bash コンソールでリポジトリを clone

1. ダッシュボード上部の **「Consoles」** タブ →「**Bash**」をクリックして新しいコンソールを開く
2. ホームディレクトリ（`/home/<ユーザー名>`）にいることを確認し、リポジトリを clone する

```bash
cd ~
git clone https://github.com/<あなた>/<リポジトリ名>.git mysite
cd mysite
```

- 上記では clone 先フォルダ名を **`mysite`** にしています（以降この名前で説明します）。
- private リポジトリの場合は、GitHub の Personal Access Token を使うか、SSH 鍵を設定してください。

> clone 後のプロジェクトの場所は **`/home/<ユーザー名>/mysite`** になります。この絶対パスを後で WSGI ファイルに書きます。

### 3-3. 仮想環境の作成と依存インストール

PythonAnywhere には `virtualenvwrapper` が入っているので `mkvirtualenv` が使えます。Python は元プロジェクトに合わせて **3.10** を指定します。

```bash
mkvirtualenv --python=/usr/bin/python3.10 blog-venv
```

プロンプトが `(blog-venv) $` に変わればその仮想環境が有効化されています。この状態で依存をインストールします。

```bash
pip install -r requirements-pythonanywhere.txt
```

> 仮想環境の場所は **`/home/<ユーザー名>/.virtualenvs/blog-venv`** になります。この絶対パスも後で Web タブに入力します。
>
> あとでコンソールを開き直したときは `workon blog-venv` で再有効化できます。

### 3-4. `.env` を作成する

`.env` は GitHub に含めていないので、サーバー上で作成します。プロジェクト直下で `nano` エディタを開きます。

```bash
cd ~/mysite
nano .env
```

以下を貼り付けます（値は自分のものに変更）。

```env
# --- 本番動作フラグ（Secure Cookie / SECRET_KEY必須化を有効にする） ---
FLASK_ENV=production

# --- SQLite を使う（PythonAnywhere無料枠） ---
USE_SQLITE=1

# --- セッション・CSRF署名用の秘密鍵 ---
SECRET_KEY=ここにランダムな長い文字列

# --- 管理者ログイン情報 ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ここにログインパスワード（平文でOK。init_db.pyがハッシュ化します）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx
ADMIN_GATE_KEY=ここにランダムな長い文字列
```

- 保存: `Ctrl + O` → `Enter`、終了: `Ctrl + X`
- `SECRET_KEY` と `ADMIN_GATE_KEY` はそれぞれ別の長いランダム文字列にします。コンソールで以下を実行すると生成できます。

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

- `ADMIN_PASSWORD` は平文で構いません（`init_db.py` がハッシュ化して DB に保存します）。ハッシュ済み文字列を入れてもそのまま使われます。
- `ADMIN_LOGIN_PATH` は推測されにくい文字列にします（例: `secret-login-a1b2c3`）。ログイン画面の URL になります。

> なぜ `USE_SQLITE=1` と `FLASK_ENV=production` の両方が必要か:
> `USE_SQLITE=1` は DB を SQLite にする指示、`FLASK_ENV=production` は「本番モード」として Secure Cookie の有効化と SECRET_KEY の必須チェックを働かせるためです。

### 3-5. データベースを初期化する（テーブル＋管理者ユーザー作成）

仮想環境が有効（`workon blog-venv`）な状態で、プロジェクト直下から実行します。

```bash
cd ~/mysite
workon blog-venv          # 念のため再有効化
python init_db.py
```

以下のような表示が出れば成功です。

```
[OK] テーブルを作成しました。
[OK] 管理者ユーザー "admin" を作成しました。

初期化が完了しました。Web タブから Reload してください。
```

これで `/home/<ユーザー名>/mysite/instance/blog.db` に SQLite データベースが作成され、管理者ユーザーも登録されました。

### 3-6. Web アプリを作成する（Manual configuration）

1. ダッシュボード上部の **「Web」** タブを開く
2. 「**Add a new web app**」をクリック
3. ドメイン確認画面が出たら「Next」（無料枠は `<ユーザー名>.pythonanywhere.com` 固定）
4. フレームワーク選択で **「Manual configuration」** を選ぶ
   （「Flask」ではなく **Manual configuration**。create_app() 方式のため手動設定が必要）
5. Python バージョンは仮想環境と同じ **Python 3.10** を選ぶ
6. 確認画面で「Next」→ Web アプリの設定ページが表示される

### 3-7. 仮想環境のパスを設定する

Web タブの設定ページを下にスクロールし、**「Virtualenv」** セクションで以下を入力します。

```
/home/<ユーザー名>/.virtualenvs/blog-venv
```

入力後、チェックマークで保存します。

### 3-8. WSGI 設定ファイルを編集する

1. Web タブの **「Code」** セクションにある **WSGI configuration file** のリンクをクリック
   （ファイル名は `/var/www/<ユーザー名>_pythonanywhere_com_wsgi.py`）
2. **中身をすべて削除**し、以下に置き換える（`<ユーザー名>` を自分のものに変更）

```python
import sys

project_home = '/home/<ユーザー名>/mysite'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import create_app
application = create_app()
```

3. 右上の「Save」で保存

> リポジトリ内の `wsgi_pythonanywhere_sample.py` と同じ内容です。コピー元として使えます。

### 3-9. 静的ファイル（CSS・画像）の配信設定

Web タブの **「Static files」** セクションで「Enter URL」「Enter path」に以下を入力し、チェックマークで保存します。

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/<ユーザー名>/mysite/static` |

これで CSS・サムネイル・アップロード画像（`static/img/posts/`）が正しく配信されます。

### 3-10. Reload して公開

Web タブ上部の緑色の **「Reload <ユーザー名>.pythonanywhere.com」** ボタンを押します。

ブラウザで以下にアクセスして、トップページが表示されれば公開成功です。

```
https://<ユーザー名>.pythonanywhere.com
```

---

## 4. 動作確認

### 4-1. 管理者ログイン

ログイン URL は隠蔽されています。以下の手順でアクセスします。

1. ブラウザで次を開く（合言葉付き）:
   ```
   https://<ユーザー名>.pythonanywhere.com/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
   ```
   （`.env` に設定した `ADMIN_LOGIN_PATH` と `ADMIN_GATE_KEY` の値を使う）
2. 合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされる
3. ユーザー名（`ADMIN_USERNAME`）とパスワード（`ADMIN_PASSWORD` に設定した値）でログイン

ログイン後、記事投稿・画像アップロード・地図/YouTube 埋め込みなどが動作するか確認してください。**画像はアップロード後も再起動で消えません**（永続ディスク）。

### 4-2. うまく動かないときの確認場所

Web タブの **「Log files」** に3種類のログがあります。エラー時はここを確認します（末尾が最新）。

- **Error log**: アプリの例外・トレースバック（最重要）
- **Server log**: 起動時のメッセージ
- **Access log**: アクセス記録

---

## 5. コードを更新したときの反映方法

GitHub に push した変更をサーバーに反映する手順です。

```bash
# Bash コンソールで
cd ~/mysite
git pull origin main

# 依存が増えた場合のみ
workon blog-venv
pip install -r requirements-pythonanywhere.txt

# モデル（models.py）を変更してテーブル構造が変わった場合のみ
python init_db.py
```

最後に **Web タブで「Reload」** を押すと反映されます。

> 注意: `init_db.py`（`db.create_all()`）は「無いテーブルを作る」だけで、既存テーブルの**カラム追加などの変更は行いません**。列を増やすなど構造を変えた場合は、動作確認用途であれば `instance/blog.db` を削除してから `python init_db.py` で作り直すのが手軽です（既存データは消えます）。

---

## 6. 無料枠での注意点

- **アプリの延長**: 無料枠のWebアプリはWeb タブに表示される「Run until 3 months from today」（現在は約1か月）のボタンを定期的に押さないと失効します。期限が近づくとメールで通知が来ます。
- **CPU時間**: 1日あたりのCPU秒数に上限があります。動作確認レベルなら問題ありません。
- **外部ネット接続**: 無料枠はサーバーからの外部通信が制限されます。ただし本アプリのアバター（DiceBear）・地図・YouTube 埋め込みは**すべて閲覧者のブラウザ側で読み込まれる**ため、この制限には影響されません。
- **公開の終了**: 一時公開が目的なので、確認が済んだら Web タブで **Disable**（無効化）または Web アプリ自体を削除し、公開を終了してください。

---

## 7. チェックリスト

- [ ] `app.py` / `config.py` を修正版に置き換えた
- [ ] `init_db.py` / `requirements-pythonanywhere.txt` を追加した
- [ ] `.gitignore` に `.env` と `*.db` が含まれている
- [ ] GitHub に push した
- [ ] PythonAnywhere で `git clone` した（`/home/<ユーザー名>/mysite`）
- [ ] `mkvirtualenv --python=/usr/bin/python3.10 blog-venv` を作成した
- [ ] `pip install -r requirements-pythonanywhere.txt` を実行した
- [ ] `.env` をサーバー上に作成した（`USE_SQLITE=1` / `FLASK_ENV=production` 含む）
- [ ] `python init_db.py` でテーブルと管理者ユーザーを作成した
- [ ] Web タブで Manual configuration（Python 3.10）を作成した
- [ ] Virtualenv パスを設定した
- [ ] WSGI ファイルを編集した
- [ ] Static files（`/static/`）を設定した
- [ ] Reload した
- [ ] トップページとログインが動作した