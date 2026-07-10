# MIT Blog — PythonAnywhere デプロイ・運用仕様書

Flask 製ブログアプリを **PythonAnywhere 無料枠**に **GitHub 経由**で公開し、公開後にコードを更新・反映していくための仕様書です。実際のデプロイで使用した設定値・遭遇したつまずきポイントも反映しています。

---

## 1. この仕様書の概要

| 項目 | 内容 |
|------|------|
| 対象アプリ | Flask 製個人ブログ（Application Factory パターン / `create_app()` 方式） |
| 公開の目的 | 学習目的の一時公開・動作確認 |
| ホスティング | PythonAnywhere 無料枠（Beginner、クレジットカード不要） |
| データベース | SQLite（無料枠でも使える。永続ディスクに DB ファイルを保存） |
| コード配布 | GitHub リポジトリからの `git clone` / `git pull` |
| 公開URL | `https://<PythonAnywhereユーザー名>.pythonanywhere.com` |

### なぜ PostgreSQL ではなく SQLite なのか

PythonAnywhere 無料枠は 2026年1月以降、新規アカウントでは MySQL も使えず、PostgreSQL は有料アドオンのみです。そのため DB サービスを使わず、ファイル1つで完結する **SQLite** に切り替えて運用します。このアプリは SQLAlchemy を使っているため、接続先を切り替えるだけで大きな改修なく動作します。

---

## 2. 構成情報（本番デプロイで使用した値）

以降の手順で使うパス・名称の一覧です。自分の環境に合わせて読み替えてください。

| 種別 | 値 |
|------|-----|
| PythonAnywhere ユーザー名 | `yuta1728` |
| GitHub リポジトリ | `https://github.com/Yuta1728/blog_project_private.git`（private） |
| clone 先フォルダ | `myblog` |
| **プロジェクト本体の場所** | **`/home/yuta1728/myblog/matome`** |
| 仮想環境名 | `blog-venv`（Python 3.10） |
| 仮想環境のパス | `/home/yuta1728/.virtualenvs/blog-venv` |
| WSGI 設定ファイル | `/var/www/yuta1728_pythonanywhere_com_wsgi.py` |
| SQLite DB ファイル | `/home/yuta1728/myblog/matome/instance/blog.db` |
| 静的ファイル | `/home/yuta1728/myblog/matome/static` |
| 公開URL | `https://yuta1728.pythonanywhere.com` |

> ⚠️ **重要な前提**: このリポジトリは、アプリ本体が clone 直下ではなく **`matome/` サブフォルダ**の中にあります。そのため、以降のコマンド・パス指定はすべて `matome` を含めた `/home/yuta1728/myblog/matome` を「プロジェクトのルート」として扱います。

---

## 3. コードの変更点（デプロイ前に反映済み）

SQLite で動かすために、以下のファイルを修正・追加しています。

| ファイル | 種別 | 内容 |
|----------|------|------|
| `app.py` | 修正 | DB 接続に SQLite 対応を追加。`USE_SQLITE=1` で `instance/blog.db` を使用 |
| `config.py` | 修正 | `.env` を config.py と同じ場所から確実に読み込む（WSGI 起動対策） |
| `init_db.py` | 新規 | `db.create_all()` でテーブル作成＋管理者ユーザー作成を一括実行 |
| `requirements-pythonanywhere.txt` | 新規 | PostgreSQL ドライバ（psycopg 系）を除いた依存一覧 |
| `wsgi_pythonanywhere_sample.py` | 新規 | WSGI 設定に貼り付ける内容のサンプル（参考用） |

### 変更のポイント

- **`app.py`**: DB 接続の優先順位は `(1) DATABASE_URL` → `(2) USE_SQLITE=1` → `(3) ローカル PostgreSQL`。`USE_SQLITE=1` を指定すると、`app.py` の位置から DB ファイルの絶対パスを自動計算するため、環境変数に長いパスを書く必要がない。
- **`config.py`**: PythonAnywhere の WSGI から起動されるとカレントディレクトリがずれて `.env` を読めないことがあるため、`config.py` 自身の絶対パスを基準に `.env` を読み込むよう変更。
- **`init_db.py`**: このアプリはログイン時に管理者ユーザーが DB に存在する前提のため、テーブル作成と同時に管理者ユーザーも作成する。`ADMIN_PASSWORD` は平文・ハッシュ済みどちらでも受け付ける。

---

## 4. 初回デプロイ手順

### フェーズ 0：全体像

```
[自分のPC]                    [GitHub]                [PythonAnywhere]
修正を反映  ──push──▶  リポジトリ  ──git clone──▶  サーバーに配置
                                                     ├ 仮想環境作成
                                                     ├ pip install
                                                     ├ .env 作成（手動）
                                                     ├ init_db.py で初期化
                                                     └ Web タブで公開設定 → Reload
```

### フェーズ 1：自分のPCでの準備

**1-1.** 修正・新規ファイルをプロジェクトに反映し、`.gitignore` に以下が含まれることを確認する（`.env` や DB ファイルの流出防止）。

```
.env
.env.*
*.db
*.sqlite3
```

**1-2.** GitHub へ push する。

```bash
git add .
git commit -m "PythonAnywhere向けにSQLite対応を追加"
git push origin main
```

> リポジトリは private を推奨（管理画面を持つアプリのため）。

### フェーズ 2：PythonAnywhere でのセットアップ

#### 2-1. アカウント作成
1. https://www.pythonanywhere.com/ で無料の **Beginner** アカウントを作成（カード不要）
2. ログインするとダッシュボードが表示される

#### 2-2. リポジトリを clone
「**Consoles**」タブ →「**Bash**」で新しいコンソールを開き、以下を実行。

```bash
cd ~
git clone https://github.com/Yuta1728/blog_project_private.git myblog
cd myblog
ls -la
```

> ✅ **確認**: `ls -la` で `matome` フォルダが見えること。アプリ本体はこの中にある。

#### 2-3. 仮想環境の作成と依存インストール
アプリ本体のある `matome` に移動してから作業する。

```bash
cd ~/myblog/matome
mkvirtualenv --python=/usr/bin/python3.10 blog-venv
pip install -r requirements-pythonanywhere.txt
```

- プロンプトが `(blog-venv) $` になれば仮想環境が有効。
- あとで再度有効化するには `workon blog-venv`。

> ⚠️ **つまずき例**: clone 直下（`~/myblog`）で `pip install` すると `requirements-pythonanywhere.txt が無い` エラーになる。プロジェクト本体は `matome/` の中なので、必ず `cd ~/myblog/matome` してから実行する。

#### 2-4. `.env` をサーバー上に作成
`.env` は `.gitignore` により **GitHub に含まれず、clone にも入っていない**。サーバー上で手動作成する。

`nano` が難しい場合は、以下を **丸ごとコピーしてコンソールに貼り付け**れば一発で作成できる（値は自分のものに変更してから貼り付ける）。

```bash
cd ~/myblog/matome
cat > .env << 'EOF'
FLASK_ENV=production
USE_SQLITE=1
SECRET_KEY=ここにランダムな長い文字列
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ここにログインパスワード（平文でOK）
ADMIN_LOGIN_PATH=secret-login-xxxxxxxx
ADMIN_GATE_KEY=ここに別のランダムな長い文字列
EOF
```

作成後、内容を確認する。

```bash
cat .env
```

**各項目の意味:**

| キー | 説明 |
|------|------|
| `FLASK_ENV=production` | 本番モード。Secure Cookie 有効化・SECRET_KEY 必須化（**SQLite運用でも必須**） |
| `USE_SQLITE=1` | DB を SQLite にする |
| `SECRET_KEY` | セッション・CSRF 署名用の秘密鍵（長いランダム文字列） |
| `ADMIN_USERNAME` | 管理者ログインのユーザー名 |
| `ADMIN_PASSWORD` | ログインパスワード（平文可。`init_db.py` がハッシュ化） |
| `ADMIN_LOGIN_PATH` | ログイン画面の URL パス（推測されにくい文字列） |
| `ADMIN_GATE_KEY` | ログイン画面を表示するための合言葉 |

ランダム文字列の生成（`SECRET_KEY` と `ADMIN_GATE_KEY` に別々の値を使う）:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **nano で編集する場合の操作**: 保存 = `Ctrl + O` → `Enter`、終了 = `Ctrl + X`。（`^` は Ctrl キーの意味）

#### 2-5. データベースの初期化
テーブルと管理者ユーザーを作成する。

```bash
cd ~/myblog/matome
workon blog-venv
python init_db.py
```

成功時の表示:

```
[OK] テーブルを作成しました。
[OK] 管理者ユーザー "admin" を作成しました。

初期化が完了しました。Web タブから Reload してください。
```

これで `instance/blog.db` に SQLite DB が作成され、管理者ユーザーも登録される。

### フェーズ 3：Web タブでの公開設定

以降はブラウザ画面での操作。画面上部のメニューから「**Web**」タブを開く（見当たらない場合は右上のハンバーガーメニュー ≡ 内）。

#### 3-1. Web アプリを作成（Manual configuration）
1. 「**Add a new web app**」をクリック
2. ドメイン確認 → 「**Next**」（無料枠は `yuta1728.pythonanywhere.com` 固定）
3. フレームワーク選択で「**Manual configuration**」を選ぶ
   - ⚠️ **「Flask」ではなく Manual configuration**。`create_app()` 方式のため手動設定が必要
4. Python バージョンで「**Python 3.10**」を選ぶ（仮想環境と合わせる）
5. 「**Next**」→ 設定ページが開く

#### 3-2. Virtualenv パスを設定
「**Virtualenv**」セクションに以下を入力してチェックマークで保存。

```
/home/yuta1728/.virtualenvs/blog-venv
```

#### 3-3. WSGI 設定ファイルを編集
「**Code**」セクションの **WSGI configuration file** のリンクを開き、**中身をすべて削除**して以下に置き換え、「Save」で保存。

```python
import sys

project_home = '/home/yuta1728/myblog/matome'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import create_app
application = create_app()
```

> ⚠️ `project_home` が `matome` まで含んでいることを必ず確認する。

#### 3-4. 静的ファイルの配信設定
「**Static files**」セクションに以下を入力してチェックマークで保存。

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/yuta1728/myblog/matome/static` |

#### 3-5. Reload して公開
Web タブ上部の緑色の「**Reload yuta1728.pythonanywhere.com**」ボタンを押す。

ブラウザで `https://yuta1728.pythonanywhere.com` にアクセスし、トップページが表示されれば公開成功。

---

## 5. 動作確認

### 5-1. トップページ
`https://yuta1728.pythonanywhere.com` が表示されること。

### 5-2. 管理者ログイン
ログイン URL は隠蔽されている。以下の手順でアクセスする。

1. ブラウザで合言葉付き URL を開く（`.env` の値を使用）:
   ```
   https://yuta1728.pythonanywhere.com/<ADMIN_LOGIN_PATH>?key=<ADMIN_GATE_KEY>
   ```
2. 合言葉が正しければ Cookie が発行され、`?key=` なしの URL にリダイレクトされる
3. `ADMIN_USERNAME` と `ADMIN_PASSWORD` でログイン

ログイン後、記事投稿・画像アップロード（再起動しても消えない）・地図/YouTube 埋め込みが動作するか確認する。

---

## 6. 公開後の更新・反映の運用方法

### 基本原則

**「PCで修正 → GitHubにpush → サーバーでpull → Reload」** が全ケース共通の流れ。

```
[自分のPC]              [GitHub]           [PythonAnywhere]
コード修正 ──push──▶ リポジトリ ──git pull──▶ サーバーに反映 → Reload
```

> ⚠️ **コードを変えただけでは反映されない。最後に必ず Web タブの「Reload」を押す**こと。Reload でアプリが再読み込みされて初めて変更が有効になる。

### ケース①：コードを修正しただけ（最も多い）

`templates/`（HTML）、`views/`（Python）、`static/`（CSS）などの変更のみ。

**PC側:**
```bash
git add .
git commit -m "修正内容"
git push origin main
```

**PythonAnywhere（Bash コンソール）:**
```bash
cd ~/myblog/matome
git pull origin main
```

**最後に** Web タブで「**Reload**」。

### ケース②：ライブラリを追加した

`requirements-pythonanywhere.txt` にパッケージを追加した場合は、pull 後にインストールが必要。

```bash
cd ~/myblog/matome
git pull origin main
workon blog-venv
pip install -r requirements-pythonanywhere.txt
```

**最後に** Web タブで「**Reload**」。

> `pip install` は既存分は飛ばして新規分だけ入れるため、毎回実行しても問題ない。

### ケース③：データベースの構造を変えた（models.py 変更）

`init_db.py`（`db.create_all()`）は「無いテーブルを作る」だけで、**既存テーブルへのカラム追加は行わない**。カラム追加などをした場合、動作確認用途であれば古い DB を作り直すのが手軽（**投稿データは消える**）。

```bash
cd ~/myblog/matome
git pull origin main
rm instance/blog.db          # 古いDBを削除（データ消去）
workon blog-venv
python init_db.py            # テーブルと管理者ユーザーを作り直す
```

**最後に** Web タブで「**Reload**」。

> データを残したままカラムを追加したい場合は Alembic（`flask db migrate` / `flask db upgrade`）を使うが、設定が複雑なため、今回の目的では作り直しで十分。

### 更新方法 早見表

| 変更内容 | pull 後に必要な作業 | 最後 |
|----------|---------------------|------|
| HTML / CSS / Python コードのみ | なし | Reload |
| ライブラリ追加 | `pip install -r requirements-pythonanywhere.txt` | Reload |
| models.py（DB 構造） | `rm instance/blog.db` → `python init_db.py` | Reload |

---

## 7. トラブルシューティング

| 症状 | 確認・対処 |
|------|-----------|
| 更新が反映されない | Web タブの **Reload を押し忘れていないか**（最頻出）。CSS はブラウザキャッシュ対策で `Ctrl + Shift + R` |
| `requirements...txt が無い` | `cd ~/myblog/matome` に居るか確認（プロジェクト本体は `matome/` の中） |
| `.env` が無い / 設定が効かない | `cat .env` で存在と内容を確認。`.env` は clone に含まれないためサーバー上で手動作成する |
| ページを開くとエラー画面 | Web タブの「**Error log**」を開き、**末尾（最新）**のトレースバックを確認 |
| ログインできない | `.env` の `ADMIN_USERNAME` / `ADMIN_PASSWORD` と、`init_db.py` を実行済みか確認 |
| push したのに pull で変わらない | PC 側で `git status` が clean（コミット漏れなし）か、`git push` 済みか確認 |

**ログの場所（Web タブ「Log files」）:**
- **Error log**: アプリの例外・トレースバック（最重要）
- **Server log**: 起動時メッセージ
- **Access log**: アクセス記録

---

## 8. 無料枠の注意点・公開の終了

- **アプリの延長**: 無料枠の Web アプリは Web タブの「Run until 3 months from today」（現在は約1か月）のボタンを定期的に押さないと失効する。期限が近づくとメール通知が届く。
- **CPU時間**: 1日あたりの CPU 秒数に上限あり。動作確認レベルなら問題なし。
- **外部ネット接続**: 無料枠はサーバーからの外部通信が制限される。ただし本アプリのアバター（DiceBear）・地図・YouTube 埋め込みはすべて**閲覧者のブラウザ側で読み込まれる**ため、この制限の影響を受けない。
- **公開の終了**: 一時公開が目的のため、確認が済んだら Web タブで **Disable**（無効化）または Web アプリ自体を削除して公開を終える。

---

## 9. 初回デプロイ チェックリスト

- [ ] `app.py` / `config.py` を修正版に置き換えた
- [ ] `init_db.py` / `requirements-pythonanywhere.txt` を追加した
- [ ] `.gitignore` に `.env` と `*.db` が含まれている
- [ ] GitHub に push した
- [ ] PythonAnywhere で `git clone`（`~/myblog`、本体は `matome/`）
- [ ] `cd ~/myblog/matome` で仮想環境 `blog-venv`（Python 3.10）を作成した
- [ ] `pip install -r requirements-pythonanywhere.txt` を実行した
- [ ] `.env` をサーバー上に作成した（`USE_SQLITE=1` / `FLASK_ENV=production` 含む）
- [ ] `python init_db.py` でテーブルと管理者ユーザーを作成した
- [ ] Web タブで Manual configuration（Python 3.10）を作成した
- [ ] Virtualenv パスを設定した（`/home/yuta1728/.virtualenvs/blog-venv`）
- [ ] WSGI ファイルを編集した（`project_home` に `matome` を含む）
- [ ] Static files（`/static/` → `.../matome/static`）を設定した
- [ ] Reload した
- [ ] トップページとログインが動作した