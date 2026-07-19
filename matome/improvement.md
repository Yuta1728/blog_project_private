# システム改善計画書 (improvement.md) — 第2版

既存の改善計画（項目 1〜8）は対応済みのため、本書ではコードベースを再調査して**新たに特定した問題点**を中心にまとめる。あわせて、前版で未対応のまま残っている項目も末尾に引き継ぐ。

各項目は「**現状 → 影響 → 対処方法**」の形式で記載する。

---

## 調査サマリ

| 分類 | 主な指摘 |
| --- | --- |
| DB・クエリ | 中間テーブルの索引不足、不要な統計クエリ、SQLAlchemy 2.0 非推奨の真偽値フィルタ、`post.user` の N+1 |
| 読み込み速度 | 全ページで不要な CSS/JS を配信、静的ファイルのキャッシュバスティング欠如、外部アバター依存、本文画像がスマホに過大 |
| 重複コード | エディタ UI（ツールバー・サムネイル欄）の二重定義、ページネーションの二重定義、CSS の同名クラス二重定義、死んだ CSS ファイル |
| 堅牢性 | 例外の握り潰しでログが残らない、巨大画像による DoS、孤児ファイルの掃除なし、DB 接続プール設定なし |
| 運用・SEO | `<title>` 固定、OGP なし、テストなし、requirements の二重管理 |

---

# 優先度：高

## A-1. 中間テーブル `post_hashtags` に `hashtag_id` 単体の索引がない【済】

**現状**
`models.py` の `post_hashtags` は `(post_id, hashtag_id)` の複合主キーのみを持つ。複合索引は**先頭カラム（post_id）からしか使えない**ため、`hashtag_id` を起点にした検索では索引が効かない。

**影響**
以下の「タグ側から記事を引く」経路がすべて中間テーブルの全表スキャンになる。記事数×タグ数に比例して重くなる。

- `index()` のハッシュタグ絞り込み（`query.join(Post.hashtags).filter(Hashtag.name == ...)`）
- `index()` のジャンル内タグ一覧（`db.session.query(Hashtag).join(Hashtag.posts)`）
- 統計のハッシュタグ数カウント
- `_get_related_posts()` の STEP 1・STEP 2（`Post.hashtags.any(...)`）
- `delete_orphaned_hashtags()` の `~Hashtag.posts.any()`

**対処方法**
`post_hashtags` の定義に `hashtag_id` 単体の索引を追加し、マイグレーションを作成する。

```python
post_hashtags = db.Table(
    'post_hashtags',
    db.Column('post_id',    db.Integer, db.ForeignKey('post.id'),    primary_key=True),
    db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtag.id'), primary_key=True),
    db.Index('ix_post_hashtags_hashtag_id', 'hashtag_id'),
)
```

> 一般に多対多の中間テーブルは「両方向から引かれる」ため、複合主キーの逆順（`hashtag_id, post_id`）の索引を張るのが定石。上記の単体索引でも実用上は十分効く。

**対応内容**
- `models.py` の `post_hashtags` に `db.Index('ix_post_hashtags_hashtag_id', 'hashtag_id')` を追加。
- マイグレーション `migrations/versions/add_post_hashtags_index.py` を追加（`down_revision = 'add_trgm_search_index'`）。`CREATE INDEX` はテーブル再構築を伴わないため `batch_alter_table` は使わず `op.create_index` を直接使用（SQLite / PostgreSQL とも動作）。

---

## A-2. 2 ページ目以降でも統計クエリを実行している（完全な無駄）【済】

**現状**
`views/blog.py` の `index()` STEP 7 は、絞り込みがなければ**ページ番号に関係なく**統計 3 クエリ＋管理者取得 1 クエリを実行している。

```python
if not selected_genre and not search_word and not selected_hashtag:
    post_count    = ...   # COUNT
    hashtag_count = ...   # JOIN + COUNT DISTINCT
    last_activity = ...   # MAX(COALESCE(...))
    admin_user    = ...   # SELECT user
```

一方 `index.html` 側は `pagination.page == 1` のときしか `stats.html` / `hero.html` を描画しない。

**影響**
2 ページ目以降のトップページで、**表示されないデータのために毎回 4 本の追加クエリ**が走る。うち `hashtag_count` は JOIN + COUNT DISTINCT で最も重い部類。

**対処方法**
条件に「1 ページ目であること」を加える。ページ番号の取得を STEP 7 より前に移動する。

```python
page = request.args.get('page', 1, type=int)
...
is_top_first_page = (
    not selected_genre and not search_word
    and not selected_hashtag and pagination.page == 1
)
if is_top_first_page:
    ...
```

**対応内容**
- `views/blog.py` の `index()` で、ページ番号の取得を他のクエリパラメータと同じ STEP 1 へ移動。
- 表示判定を `show_top_sections = (not has_filter) and pagination.page == 1` の 1 つのフラグに集約し、統計 3 クエリ＋管理者取得 1 クエリをこのフラグ配下に移動。
- 判定に `request.args` の生値ではなく `pagination.page` を使用（`paginate(error_out=False)` は 0 や負数を 1 に丸めるため、テンプレートの `pagination.page == 1` と確実に一致する）。
- `show_top_sections` をテンプレートにも渡し、`index.html` が 3 か所で重複していた条件式を差し替え。ビューがクエリを打つ条件と画面表示が構造的にずれないようにした。
- あわせて 1 ページあたりの件数を `POSTS_PER_PAGE = 4` として定数化（`views/admin.py` と同じ扱い）。

**さらに（任意・未実施）**
統計は「秒単位の正確さ」を必要としない。`flask-caching` などで 5〜10 分キャッシュすれば、トップページ 1 ページ目のクエリ本数もさらに削減できる。

---

## A-3. 真偽値リテラルを `filter()` に渡している（SQLAlchemy 2.0 で非推奨）【済】

**現状**

```python
# views/blog.py index() STEP 6
pub_condition = (Post.is_published == True) if not current_user.is_authenticated else True
... .filter(pub_condition, ...)

# views/blog.py _get_related_posts() STEP 1
Post.hashtags.any(Hashtag.name.in_(tag_names)) if tag_names else False,
```

Python の `True` / `False` をそのまま SQL 式として渡している。

**影響**
SQLAlchemy 1.4 以降は非推奨警告の対象で、将来のバージョンで `ArgumentError` になる可能性がある。加えて `filter(False)` は「常に 0 件」を意味するため、タグなし記事の関連記事 STEP 1 で**無意味なクエリを 1 本発行している**（結果は必ず空）。

**対処方法**
`sqlalchemy.true()` / `false()` を使う。さらに STEP 1 は「タグがあるときだけ実行する」よう分岐させ、無駄な 1 クエリを削る。

```python
from sqlalchemy import true, false

pub_condition = (Post.is_published == True) if not current_user.is_authenticated else true()

# _get_related_posts
if remaining > 0 and tag_names:      # ← tag_names のチェックを外側に出す
    step1 = (...)
```

---

## A-4. 巨大ピクセル画像による DoS（Decompression Bomb）

**現状**
`MAX_CONTENT_LENGTH` は 30MB に制限されているが、これは**ファイルサイズ**の制限にすぎない。PNG や WebP は圧縮率が高いため、数百 KB のファイルが展開後に数億ピクセルになりうる（例：50000×50000px の単色 PNG）。`_optimize_body_image_save()` はサイズ検証なしに `Image.open()` → `thumbnail()` を実行する。

**影響**
1 リクエストでメモリを数 GB 消費し、ワーカープロセスが停止する。無料枠ホスティングでは致命的。

**対処方法**
Pillow の上限を明示し、展開前にピクセル数を検証する。

```python
# admin.py 冒頭
Image.MAX_IMAGE_PIXELS = 50_000_000   # 約 5000万px を上限に

MAX_PIXELS = 40_000_000

def _guard_image_size(img):
    w, h = img.size
    if w * h > MAX_PIXELS:
        raise ValueError('画像の解像度が大きすぎます。縮小してからアップロードしてください。')
```

`_optimize_body_image_save()` / `_save_thumbnail()` の `Image.open()` 直後に `_guard_image_size(img)` を挿入する（`Image.open()` は遅延読み込みのため、この時点ではまだ画素を展開していない）。

---

## A-5. 例外を握り潰していてログが残らない【済】

**現状**
以下の箇所が `except Exception:` で例外を捨てている。

| 箇所 | 内容 |
| --- | --- |
| `views/blog.py` `detail()` | body_html の遅延バックフィル失敗 |
| `views/admin.py` `create()` / `update()` / `delete()` | commit 失敗 |
| `views/admin.py` `_optimize_body_image_save()` | Pillow の全例外を ValueError に正規化 |

ユーザーには「エラーが発生しました」と出るが、**サーバー側に原因が一切残らない**。

**影響**
本番で投稿できない・画像が保存できない等の障害が起きた際、原因調査が不可能になる。PythonAnywhere の Error log にも何も出ない。

**対処方法**
`current_app.logger.exception()` を必ず挟む。

```python
except Exception:
    db.session.rollback()
    current_app.logger.exception('記事の保存に失敗しました (user_id=%s)', current_user.id)
    ...
```

あわせて `app.py` にログ設定（フォーマット・レベル）を追加する。

---

## A-6. 全ページで不要な CSS / JS を配信している

**現状**

- `base.html` は全ページで `mobile-editor.css` を読み込むが、対象要素（`#md-toolbar` / `#bodyTextarea`）は **create / update にしか存在しない**。
- 同様に `hashtag.css` の入力欄関連スタイルは create / update 専用。
- `base.html` の `<script>` に、スマホ編集ツールバー用の **約 250 行の JavaScript がインライン**で埋め込まれている。これも create / update 以外では冒頭の `if (!textarea || !toolbar) return;` で即終了するだけ。

**影響**
全ページで不要な CSS/JS をダウンロード・パースしている。インライン JS は**外部ファイルと違ってブラウザキャッシュが効かず、全ページの HTML に毎回含まれる**ため、記事一覧などの HTML サイズを常時押し上げている。

**対処方法**

1. `mobile-editor.css` を `create.html` / `update.html` の `{% block extra_css %}` へ移動する。
2. `base.html` のスマホエディタ用 JS を `static/js/mobile-editor.js` として切り出し、`create.html` / `update.html` の末尾でのみ読み込む（`editor.js` と同じ扱いにする）。
3. 同様に、テーマ切り替えとドロワー開閉の JS も `static/js/base.js` に切り出す（全ページ共通だが、外部ファイル化すればキャッシュが効く）。

> `<head>` のダークモード初期化スクリプトだけは、チラつき防止のためインラインのまま残す（数行なので影響は無視できる）。

---

## A-7. 静的ファイルにキャッシュバスティングがない

**現状**
CSS / JS はすべて `url_for('static', filename='css/index.css')` で出力され、クエリもハッシュも付かない。

**影響**
「更新してもブラウザに古い CSS が残る」と「キャッシュを短くすると毎回再取得になる」のトレードオフから抜け出せない。デプロイ手順書にも「CSS は `Ctrl + Shift + R`」と書かざるを得なくなっている。

**対処方法**
ファイルの更新時刻（mtime）をクエリに付与するヘルパーを用意し、静的ファイルのキャッシュ期間を長くする。

```python
# app.py
import os

@app.template_global()
def static_url(filename):
    path = os.path.join(app.static_folder, filename)
    v = int(os.path.getmtime(path)) if os.path.exists(path) else 0
    return url_for('static', filename=filename, v=v)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 60 * 60 * 24 * 365   # 1年
```

テンプレート側は `href="{{ static_url('css/index.css') }}"` に置き換える。ファイルを更新すれば URL が変わるため、長期キャッシュしても即座に反映される。

---

# 優先度：中

## B-1. 記事詳細で `post.user` の N+1（追加 1 クエリ）

**現状**
`detail.html` が `post.user.nickname` を参照するが、`detail()` は `db.session.get(Post, id)` で取得するだけで `user` を eager load していない。

**影響**
記事表示のたびに `SELECT ... FROM user WHERE id = ?` が 1 本増える。単体では軽いが、`related_posts` の各要素で `rel.user` を参照する仕様に拡張した瞬間 N+1 になる。

**対処方法**

```python
post = (
    Post.query
    .options(db.joinedload(Post.user))
    .filter(Post.id == id)
    .first()
)
```

---

## B-2. `selectinload` の指定が冗長

**現状**
`models.py` の `Post.hashtags` は既に `lazy='selectin'` が指定されている。にもかかわらず `index()` と `mypage()` で `.options(db.selectinload(Post.hashtags))` を重ねている。

**影響**
動作上の実害はないが、「どちらが効いているのか」が読み手に伝わらず、後から `lazy` を変更した際の挙動が予測しにくい。

**対処方法**
どちらか一方に統一する。**推奨はクエリ側（`options`）に寄せ、モデルの `lazy` は既定の `select` に戻す**こと。関連記事など「タグを使わない取得」で無駄な追加クエリが走らなくなる。

---

## B-3. キャッシュ済み本文 HTML の無効化手段がない

**現状**
`Post.body_html` に変換結果を保存する仕組みは導入済みだが、**再生成のトリガーが「記事の編集」しかない**。

**影響**
`rendering.py` を修正（例：地図の枠デザイン変更、YouTube 埋め込みの改修、`loading="lazy"` の追加）しても、**既存記事は古い HTML のまま**表示され続ける。全記事を手で開いて再保存する必要がある。

**対処方法**
レンダラのバージョンを持たせ、不一致なら再生成する。

```python
# rendering.py
RENDER_VERSION = 3          # rendering.py を変更したら +1 する

# models.py
render_version = db.Column(db.Integer, nullable=True)

# detail()
if post.body_html is None or post.render_version != RENDER_VERSION:
    # 再生成 + 保存（既存の遅延バックフィルと同じ流れ）
```

あわせて、全記事を一括再生成する管理コマンド（`flask rerender-posts`）を用意しておくと運用が楽になる。

---

## B-4. 本文画像がスマートフォンに対して過大

**現状**
本文画像は長辺 1600px に縮小されるが、配信されるのは**その 1 サイズのみ**。スマホの表示幅は実質 350〜400px 程度で、`width: 100%` で縮めて表示している。

**影響**
モバイル回線で不要に大きな画像を転送している。記事あたり数枚あれば体感速度に直結する。

**対処方法**
アップロード時に複数サイズ（例：640 / 1280 / 1600px）を生成し、`srcset` で出し分ける。

```html
<img src=".../xxx-1600.webp"
     srcset=".../xxx-640.webp 640w, .../xxx-1280.webp 1280w, .../xxx-1600.webp 1600w"
     sizes="(max-width: 767px) 100vw, 720px"
     loading="lazy" decoding="async">
```

> 実装コストが高いため、まずは **本文画像の上限を 1600px → 1200px に下げる**だけでも効果が出る（記事の最大表示幅は 860px のため、2 倍解像度でも 1200px で足りる）。

---

## B-5. 記事本文の生 HTML がサニタイズされていない

**現状**
`markdown` ライブラリは既定で**本文中の生 HTML をそのまま通す**。`display_body | safe` で出力しているため、記事に `<script>` を書けば実行される。

**影響**
単一管理者運用のため現状は自己 XSS の域を出ないが、将来ユーザー投稿を許可した場合に即座に致命的な脆弱性になる。また、管理者アカウントが乗っ取られた場合の被害を拡大させる。

**対処方法**
`bleach` などで許可タグのホワイトリスト方式に変換する。ただし独自タグ（`[map:]` / `[youtube:]`）が生成する `iframe` は許可する必要があるため、**サニタイズは Markdown 変換直後、独自タグ置換の前**に行う。

```python
display_body = bleach.clean(md.convert(body_content),
                            tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
```

**副次効果**：サニタイズを入れると CSP（Content-Security-Policy）の導入も現実的になる。

---

## B-6. 孤児画像ファイルの掃除機構がない

**現状**
DB commit 失敗時の掃除は実装済みだが、以下のケースでは孤児ファイルが残る。

- プロセスが commit と `_delete_images()` の間で異常終了した
- 過去のバグ・手動操作で `img_name` から参照が外れた
- `static/img/posts/` に手動配置した旧ファイル（実際に日本語名のスクリーンショットが残存している）

**影響**
無料枠の限られたディスクを少しずつ食い潰す。

**対処方法**
「DB のどのレコードからも参照されていないファイル」を列挙・削除する管理コマンドを用意する。

```python
@app.cli.command('clean-orphan-images')
def clean_orphan_images():
    referenced = set()
    for p in Post.query.with_entities(Post.img_name, Post.thumbnail_img):
        if p.img_name:      referenced.update(x.strip() for x in p.img_name.split(','))
        if p.thumbnail_img: referenced.add(p.thumbnail_img)
    for f in os.listdir(posts_dir):
        if f not in referenced:
            print('orphan:', f)      # --delete オプション時のみ実際に削除
```

**関連**：`.gitignore` の `static/img/uploads/` のコメントアウトを解除（実際のパスは `static/img/posts/`）し、投稿画像が Git に混入しないようにする。既にコミット済みの日本語名画像も整理する。

---

## B-7. DB 接続プールの設定がない

**現状**
`SQLALCHEMY_ENGINE_OPTIONS` が未設定。

**影響**
PaaS の PostgreSQL は一定時間で接続を切断するため、アイドル後の最初のアクセスで `OperationalError`（server closed the connection unexpectedly）が発生しうる。

**対処方法**

```python
if not use_sqlite:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,     # 使用前に接続の生死を確認
        'pool_recycle': 280,       # 5分未満で張り直す
    }
```

---

## B-8. `img_captions` のタブ区切りが壊れうる

**現状**
キャプションはタブ文字（`\t`）区切りの 1 カラムに格納される。入力値からタブを除去する処理はない。

**影響**
コピー＆ペーストでタブが混入すると、以降のキャプションが 1 つずつずれる（画像とキャプションの対応が崩れる）。

**対処方法**
最小の対処は入力時のサニタイズ。

```python
caption = request.form.get(f'{prefix}{i}', '').replace('\t', ' ').strip()
```

**根本対処**：`img_name` / `img_captions` を JSON カラム、または画像専用テーブル（`post_image`：post_id / order / filename / caption / width / height）に正規化する。B-4 の `srcset` 対応や、本文画像の `width` / `height` 出力（前版の項目 8 の残課題）も同時に解決できる。

---

## B-9. エラーページ・エラーハンドラの不足

**現状**

- カスタムの 404 / 500 ページがない（Flask 標準の素っ気ない画面が出る）。認証の存在隠蔽で 404 を多用しているにもかかわらず、その 404 がデフォルト画面のまま。
- 413（サイズ超過）ハンドラが `admin.mypage` へリダイレクトするが、未ログイン状態だと `unauthorized_handler` により**404 になる**。

**対処方法**
`templates/404.html` / `500.html` を用意し、`@app.errorhandler` で返す。413 は「直前のページに戻す」か、ログイン状態を見て遷移先を分岐させる。

---

# 優先度：低

## C-1. `<title>` 固定・OGP メタタグなし（前版の項目 12 を含む）

`base.html` の `<title>` が `Mycreate1.MITOblog.jp` 固定で、記事タイトルが反映されない。`meta description` や OGP（`og:title` / `og:description` / `og:image`）もないため、SNS でシェアしてもタイトル・画像が出ない。

**対処方法**：`{% block title %}` / `{% block meta %}` を設け、`detail.html` で記事タイトル・本文冒頭・サムネイル URL を差し込む。`robots.txt` と `sitemap.xml` も検討。

---

## C-2. `requirements.txt` の二重管理

`requirements.txt` と `requirements-pythonanywhere.txt` の差分は psycopg 系 2 行だけだが、バージョン更新時に片方だけ更新される事故が起きる。

**対処方法**：ベースを 1 ファイルにし、環境別ファイルは `-r requirements.txt` で継承する構成にする。

```
# requirements-pythonanywhere.txt
-r requirements-base.txt
```

---

## C-3. ドキュメントとファイル名の不整合

`deploy_pythonanywhere.md` は `wsgi_pythonanywhere_sample.py` を追加したと記載しているが、リポジトリの実ファイル名は `wsgi_pythonanywhere.py`。

**対処方法**：どちらかに統一する。

---

## C-4. `goBack()` の例外処理

`detail.html` の `new URL(referrer)` は、referrer が不正な文字列の場合に例外を投げる。

**対処方法**：`try { ... } catch { history.back(); }` で包む。

---

## C-5. `hero.html` の自己紹介文がハードコード

トップページの自己紹介文がテンプレートに直書きされており、`about.html` の内容とも一致していない。管理画面から編集できない。

**対処方法**：`User` に `bio` カラムを追加してマイページから編集可能にする（少なくとも `constants.py` へ移して一元管理する）。

---

## C-6. 自動テストが存在しない

セキュリティ要件（ゲートキー・ロックアウト・権限チェック）や画像処理など、壊れると影響の大きい処理が手動確認のみで担保されている。

**対処方法**：`pytest` + `pytest-flask` で最小限のスモークテストから始める。

- 未ログインで `/create` `/mypage` → 404
- ゲートキーなしでログイン URL → 404、`?key=` 付き → Cookie 発行
- 非公開記事に第三者がアクセス → リダイレクト
- 記事投稿 → 一覧・詳細に反映
- 不正な拡張子・偽装 MIME のアップロードが弾かれる

---

# 重複コードの整理

機能追加のたびに「2 か所直す必要がある」箇所が残っている。バグの温床になるため、優先的に共通化したい。

## D-1. create.html / update.html のエディタ UI が丸ごと重複

**重複している範囲**

| 箇所 | 行数目安 | 差分 |
| --- | --- | --- |
| Markdown ツールバー（`#md-toolbar`） | 約 25 行 | `#img-btn-group` の初期内容のみ |
| ハッシュタグ入力欄 | 約 20 行 | `value` の有無 |
| 画像アップロードのボタン行・input | 約 20 行 | なし |
| サムネイル選択欄 | 約 20 行 | 既存サムネイル表示ブロックの有無 |
| デフォルトサムネイル `<select>`（11 オプション） | 約 15 行 | `selected` 判定の有無 |

**対処方法**
`_map_modal.html` / `_youtube_modal.html` と同じ要領で部分テンプレート化する。

```
templates/_editor_toolbar.html      {% include %} で共通化（img ボタンだけ引数で分岐）
templates/_thumbnail_fields.html    post を渡す（create では None）
```

## D-2. デフォルトサムネイルの選択肢が HTML にハードコード

`create.html` と `update.html` の両方に `thumb_option1.jpg`〜`thumb_option11.jpg` とラベル（趣味／旅行／…）が直書きされている。画像を 1 つ追加するたびに 2 ファイルを修正する必要がある。

**対処方法**：`constants.py` に定義を移し、ビューから渡してループ描画する。

```python
DEFAULT_THUMBNAILS = [
    ('thumb_option1.jpg', '趣味'),
    ('thumb_option2.jpg', '旅行'),
    ...
]
```

## D-3. ページネーション nav が index.html / mypage.html で重複

約 35 行のブロックが、リンク先の endpoint とアンカー名以外まったく同一。

**対処方法**：`_macros.html` にマクロ化する。

```jinja
{% macro pagination_nav(pagination, endpoint, anchor, params={}) %}
```

## D-4. DiceBear アバターの URL が 4 か所に重複

`hero.html` / `about.html` / `detail.html` の 3 テンプレートに、同じ URL 組み立てが `width`/`height` 違いで散在している。

**対処方法**：`_macros.html` に `avatar(user, size)` マクロを作る。引き継ぎ項目 17（外部依存の解消）とセットで対応すると、差し替えが 1 か所で済む。

## D-5. CSS の同名クラス二重定義

| クラス | 定義場所 |
| --- | --- |
| `.hero-section-title` | `index.css` と `top_sections.css` |
| `.posts-section-title` | `index.css` と `top_sections.css` |

読み込み順に依存して勝敗が決まる状態で、コメントにも「index.css が優先される」と注記されている。片方に統一すべき。

## D-6. 死んでいる CSS・未使用スタイル

| 対象 | 状況 |
| --- | --- |
| `static/css/load_more.css` | mypage のページネーション化に伴い、**どのテンプレートからも読み込まれていない** |
| `top_sections.css` の `.howto-section` 系 | コメントで「現状未使用」と明記されている |
| `detail.css` の `.detail-ul` 系 | 「後方互換用の予備クラス」＝未使用 |
| `auth.css` の `.footer-link` | 「現状未使用の予備クラス」 |

**対処方法**：削除する。学習用に残すなら `_archive/` などへ移し、配信対象から外す。

## D-7. YouTube ID 抽出ロジックの二重定義

`static/js/editor.js` の `extractYoutubeId()` と `rendering.py` の `_extract_youtube_id()` が同じ正規表現を持つ（コード内でも認識済み）。クライアント検証とサーバー検証は原理的に両方必要なため完全な統合はできないが、**正規表現パターンだけを 1 か所（JSON など）から供給する**か、少なくとも「片方を変えたら他方も」というテストを用意したい。

## D-8. 本番判定ロジックの重複

`app.py` 内で `is_production` の判定式が `create_app()` と `__main__` ブロックの 2 か所に書かれている。関数化して 1 か所にまとめる。

---

# 前版からの引き継ぎ（未対応項目）

以下は前版で挙げたまま未対応のもの。番号は前版のものを維持する。

### 9. ログインのユーザー名入力が `type="password"`
`login.html` のユーザー名欄が `type="password"` で、`autocomplete="username"` と不整合。意図的な目隠しでなければ `type="text"` に。目隠しが目的ならコメントで明記する。

### 10. 認証まわりのハードニング
ゲートキー／Cookie の比較が非定数時間の `==`。ブルートフォース対策もセッション単位のため、別ブラウザで回避可能。
**対処方法**：`secrets.compare_digest()` での比較、Flask-Limiter による IP ベースの制限。

### 11. 静的アセットのバンドル／バージョニング
→ **A-7 で改善案を具体化済み**。バンドル（CSS の結合）は、ページ固有 CSS を分けている現構成の利点を損なうため、まずはバージョニングのみで十分。

### 13. ラベルの `for=""` が空・不一致
`login.html` などで `<label for="">` が空。`for` と `id` を対応させる。

### 14. `sync_hashtags` の同名タグ同時作成レース
「検索 → なければ作成」の間の競合。単一管理者運用なら実害は低い。
**対処方法**：commit 時の `IntegrityError` を捕捉して再取得・リトライ。

### 15. 関連記事の 4 連続クエリ
`_get_related_posts` は最大 4 回クエリを発行し、`notin_` のリストが段階ごとに増える。
**対処方法**：A-3 でタグなし記事の 1 本を削減できる。さらに詰めるなら、`CASE` 式で優先度スコアを付けて 1 クエリ（`ORDER BY score DESC, created_at DESC LIMIT 4`）にまとめる。

### 16. 本文中 Markdown 画像に `loading="lazy"` がない
`rendering.py` が生成する `<img>` に遅延読み込みがない。記事下部の画像も初期ロードされる。
**対処方法**：`loading="lazy" decoding="async"` を付与する。**注意**：B-3（キャッシュ無効化）を先に入れないと既存記事には反映されない。

### 17. DiceBear アバターへの外部依存
ページごとに外部ドメインへリクエストが発生し、LCP・プライバシー・可用性に影響する。
**対処方法**：SVG をサーバー側で生成してローカル保存するか、静的なアバター画像に置き換える。D-4 のマクロ化と同時に対応すると差し替えが 1 か所で済む。

---

# 実施順の提案

| 段階 | 内容 | 狙い |
| --- | --- | --- |
| **第 1 段階**（低コスト・即効） | A-2（統計クエリ）／A-3（真偽値フィルタ）／A-1（索引追加）／A-5（ログ） | 表示速度と障害調査性を最小の変更で改善 |
| **第 2 段階**（読み込み速度） | A-6（CSS/JS の配信整理）／A-7（キャッシュバスティング）／16（lazy）／B-4 の簡易版（上限 1200px） | 体感速度・転送量の改善 |
| **第 3 段階**（堅牢性） | A-4（画像 DoS）／B-7（接続プール）／B-9（エラーページ）／10（認証ハードニング） | 本番運用の安定化 |
| **第 4 段階**（保守性） | D-1〜D-8（重複整理）／B-3（レンダラのバージョン管理）／C-6（テスト） | 今後の変更コストを下げる |
| **第 5 段階**（設計改善） | B-8（画像テーブルの正規化）／B-4（srcset）／B-5（サニタイズ）／C-1（SEO） | 機能拡張への備え |