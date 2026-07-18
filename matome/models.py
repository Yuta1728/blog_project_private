# ======================================================================
# models.py — データベースのテーブル定義（ORM モデル）
# ======================================================================
#
# 【役割】
#   データベースのテーブル構造を Python クラスで定義するファイル。
#   SQLAlchemy が各クラスを DB のテーブルに対応させる。
#
# 【このファイルの構成（目次）】
#   [1] post_hashtags : Post ↔ Hashtag の多対多を実現する中間テーブル
#   [2] Hashtag       : ハッシュタグ
#   [3] Post          : ブログ記事
#   [4] User          : 管理者
#
# 【テーブル構成と関係図】
#
#   user (User)                     hashtag (Hashtag)
#   ┌──────────┐                    ┌──────────┐
#   │ id       │                    │ id       │
#   │ username │                    │ name     │
#   │ password │                    └────┬─────┘
#   │ nickname │                         │ 多対多
#   └────┬─────┘                         │ (post_hashtags 経由)
#        │ 1対多                          │
#        │ (user.posts)                  │
#        ▼                               ▼
#   post (Post) ◄────────────── post_hashtags（中間テーブル）
#   ┌──────────────┐            ┌─────────────────────┐
#   │ id / title   │            │ post_id  (FK)        │
#   │ body / genre │            │ hashtag_id (FK)      │
#   │ img_name ... │            └─────────────────────┘
#   └──────────────┘
#
# ======================================================================

from extensions import db          # extensions.py で作成した db インスタンスを使う
from flask_login import UserMixin  # ログイン機能に必要なメソッドを User に追加するミックスイン
from datetime import datetime
import pytz                        # タイムゾーン指定（Asia/Tokyo）に使用


# ======================================================================
# [1] 中間テーブル: post_hashtags
# ======================================================================
# Post と Hashtag は「多対多」の関係（1つの記事に複数タグ、1つのタグが複数記事に付く）。
# SQLAlchemy では多対多を表現するために「中間テーブル」が必要。
#
# db.Table() で定義すると「モデルクラスを持たない純粋な関連テーブル」になる。
# Post モデルの hashtags リレーションが secondary=post_hashtags を参照することで
# Post ↔ Hashtag 間の JOIN が自動で行われる。
#
# ----------------------------------------------------------------------
# 【パフォーマンス改善（improvement.md 第2版 項目 A-1）】
#   hashtag_id 単体のインデックスを追加した理由
# ----------------------------------------------------------------------
# 従来この中間テーブルは (post_id, hashtag_id) の複合主キーしか持っていなかった。
# 複合インデックスは「先頭カラムから順に使う」性質があるため、
# post_id を起点にした検索（＝記事からタグを引く方向）には効くが、
# hashtag_id を起点にした検索（＝タグから記事を引く方向）には効かない。
#
# その結果、以下の「タグ側から記事を引く」経路がすべて
# 中間テーブルの全表スキャンになっていた。
#
#   - index() のハッシュタグ絞り込み
#       query.join(Post.hashtags).filter(Hashtag.name == ...)
#   - index() のジャンル内タグ一覧
#       db.session.query(Hashtag).join(Hashtag.posts)
#   - 統計のハッシュタグ数カウント
#       count(distinct Hashtag.id) ... join(Hashtag.posts)
#   - _get_related_posts() の STEP 1 / STEP 2
#       Post.hashtags.any(Hashtag.name.in_(...))
#   - delete_orphaned_hashtags() の孤立タグ判定
#       ~Hashtag.posts.any()
#
# これらは「記事数 × タグ数」に比例して重くなるため、
# hashtag_id 単体のインデックス ix_post_hashtags_hashtag_id を張り、
# 逆方向の検索でもインデックス走査で済むようにする。
#
# なお多対多の中間テーブルでは、複合主キーの逆順
# （hashtag_id, post_id）の複合インデックスを張るのが定石だが、
# 単体インデックスでも「hashtag_id で該当行を絞り込む」目的は十分果たせる
# （絞り込んだ後に post_id を主キー経由で引く形になる）ため、
# ここではシンプルな単体インデックスを採用している。
#
# ※ DB 側への反映はマイグレーション
#    migrations/versions/add_post_hashtags_index.py が行う。
post_hashtags = db.Table(
    'post_hashtags',
    # post_id: post テーブルの id を外部キーとして参照
    db.Column('post_id',    db.Integer, db.ForeignKey('post.id'),    primary_key=True),
    # hashtag_id: hashtag テーブルの id を外部キーとして参照
    db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtag.id'), primary_key=True),
    # 2カラムの組み合わせが主キー → 同じ (post_id, hashtag_id) の重複を防ぐ
    #
    # 「タグ → 記事」方向の検索用インデックス（上記コメント参照）
    db.Index('ix_post_hashtags_hashtag_id', 'hashtag_id'),
)


# ======================================================================
# [2] Hashtag モデル
# ======================================================================
class Hashtag(db.Model):
    __tablename__ = 'hashtag'  # DB 上のテーブル名を明示的に指定

    id   = db.Column(db.Integer, primary_key=True)
    # name: '#' を除いたタグ文字列で保存（例: "Flask", "Python"）
    #   unique=True    → 同じ名前のタグは 1 件だけ存在できる
    #                    （unique 制約は多くの DB で暗黙的にインデックスを作るため、
    #                      タグ名での検索・重複チェックは索引が効く）
    #   nullable=False → 必須項目
    name = db.Column(db.String(100), nullable=False, unique=True)

    # posts リレーションは Post モデル側の backref で自動定義される（[3] 参照）


# ======================================================================
# [3] Post モデル（ブログ記事）
# ======================================================================
class Post(db.Model):
    # __tablename__ を省略すると SQLAlchemy がクラス名を小文字化した 'post' をテーブル名にする

    # ------------------------------------------------------------------
    # (3-0) テーブルレベルのオプション（複合インデックス）
    # ------------------------------------------------------------------
    # 【パフォーマンス改善】単一カラムのインデックス（各カラムの index=True）に加えて、
    # トップページの主要クエリに合わせた複合インデックスを 1 本用意する。
    #
    # index.py の index() は
    #     WHERE is_published = True （+ 自分の記事）
    #     ORDER BY created_at DESC
    #     LIMIT/OFFSET（ページネーション）
    # という形で毎回呼ばれる。
    # (is_published, created_at) の複合インデックスがあると、
    # 「公開記事を新しい順に並べて先頭 N 件」を
    # インデックスの走査だけで取得でき、全表スキャン＋ソートを避けられる。
    #
    # カラムの並び順は「等値で絞るカラム（is_published）を先、
    # 範囲・並べ替えに使うカラム（created_at）を後」にするのが定石。
    #
    # インデックスは (is_published ASC, created_at ASC) の昇順で作るが、
    # PostgreSQL / SQLite いずれもインデックスを逆順に走査できるため、
    # ORDER BY created_at DESC のクエリでもこのインデックスがそのまま使える。
    __table_args__ = (
        db.Index('ix_post_is_published_created_at', 'is_published', 'created_at'),
    )

    # ------------------------------------------------------------------
    # (3-1) 基本カラム
    # ------------------------------------------------------------------
    id         = db.Column(db.Integer, primary_key=True)  # 記事の一意な識別子（自動採番）
    title      = db.Column(db.TEXT, nullable=False)        # 記事タイトル（必須）
    body       = db.Column(db.TEXT, nullable=False)        # 記事本文（マークダウン形式、必須）

    # genre: ジャンル名。
    #   【パフォーマンス改善】index=True を付与。
    #   index() / genre_list() のジャンル絞り込み（WHERE genre = ?）や
    #   DISTINCT 取得で使うため、単体インデックスで全表スキャンを避ける。
    genre      = db.Column(db.String(100), nullable=False, default='未分類', index=True)

    # ------------------------------------------------------------------
    # (3-2) 日時カラム
    # ------------------------------------------------------------------
    # created_at: 投稿日時。lambda を使ってインスタンス生成時の時刻を設定する。
    #   【パフォーマンス改善】index=True を付与。
    #   一覧・関連記事・統計のほぼすべてが ORDER BY created_at DESC を伴うため、
    #   並べ替えコストを下げる目的で単体インデックスを張る。
    #   （公開記事を新しい順に取る主経路は上の複合インデックスがカバーするが、
    #     マイページ等「公開状態で絞らない並べ替え」では単体側が効く）
    created_at = db.Column(db.DateTime, nullable=False, index=True,
                           default=lambda: datetime.now(pytz.timezone('Asia/Tokyo')))

    # updated_at: 更新日時。
    #   nullable=True にすることで「まだ一度も更新されていない」状態を NULL で表現する。
    #   これにより detail.html の「更新日時 != 投稿日時」という条件判定が
    #   秒単位のズレで誤表示されるバグを防ぐ。
    #   - 新規投稿時: NULL（テンプレート側で「更新なし」として扱う）
    #   - 編集保存時: admin.py の update() で現在時刻をセット
    updated_at = db.Column(db.DateTime, nullable=True)

    # ------------------------------------------------------------------
    # (3-3) ユーザー紐付け
    # ------------------------------------------------------------------
    # user_id: user テーブルの id への外部キー（どの管理者が書いた記事か）
    #   【パフォーマンス改善】index=True を付与。
    #   マイページ（WHERE user_id = ?）や、詳細ページの権限チェック、
    #   ログイン中ユーザーの記事を含める一覧クエリで使う。
    #   外部キーでも DB によっては自動索引が張られないため明示する。
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # ------------------------------------------------------------------
    # (3-4) 画像関連カラム
    # ------------------------------------------------------------------
    # img_name: アップロード画像のファイル名をカンマ区切りで保存
    #   例: "uuid1.jpg,uuid2.png"
    #   複数画像に対応するため 1 カラムにまとめて格納している
    #   （記事本文の [imgN] タグに対応する「本文中の画像」であり、
    #     サムネイルとは無関係。以前は先頭画像がサムネイルに流用されていたが
    #     現在は thumbnail_img で独立管理する）
    #
    #   【バグ修正】String(100) → Text に変更
    #   UUID 化したファイル名は 1 件あたり約 40 文字（UUID 36 文字 + 拡張子）あり、
    #   3 枚以上アップロードするとカンマ区切り文字列が 100 文字を超えて
    #   PostgreSQL で "value too long for type character varying(100)"
    #   エラーになっていた。枚数上限を設けない設計のため可変長の Text にする。
    #   （migrations/versions/change_img_name_to_text.py で DB 側も変更）
    img_name      = db.Column(db.Text, nullable=True)

    # default_thumb: 画像未アップロード時に使うデフォルトサムネイルのファイル名
    #   例: "thumb_option1.jpg"（static/img/thbnails/ 以下に配置済みの画像）
    default_thumb = db.Column(db.String(100), nullable=True)

    # thumbnail_img: サムネイル専用にアップロードされた画像のファイル名
    #   例: "uuid.jpg"（static/img/posts/ 以下に UUID 名で保存）
    #
    #   【機能追加】サムネイル画像の個別アップロードに対応するため新設。
    #   以前は「本文画像（img_name）の先頭」がそのままサムネイルに使われていたが、
    #   本文中に載せたい画像とサムネイルにしたい画像は必ずしも一致しないため、
    #   サムネイル専用の 1 枚をこのカラムで独立して管理する。
    #
    #   サムネイル表示の優先順位（index.html / detail.html / mypage.html）:
    #     1. thumbnail_img（アップロードされた専用サムネイル）
    #     2. default_thumb（プリセットから選択したデフォルトサムネイル）
    #     3. system-default.jpg（システム共通のデフォルト）
    thumbnail_img = db.Column(db.String(100), nullable=True)

    # img_captions: 各画像のキャプションをタブ区切りで保存
    #   例: "東京タワー全景\t夜景のアップ"
    #   img_name のカンマ区切りと順番が対応する（img_name[0] → captions[0]）
    img_captions  = db.Column(db.Text, nullable=True)

    # ------------------------------------------------------------------
    # (3-4.5) レンダリング済み本文のキャッシュカラム
    # ------------------------------------------------------------------
    # 【パフォーマンス改善（improvement.md 項目 5）】
    # 従来 detail() は本文（Markdown + [imgN]/[map:]/[youtube:] などの独自タグ）を
    # アクセスのたびに変換していた。本文は投稿・編集時にしか変わらないため、
    # 変換結果をここにキャッシュしておき、詳細表示ではそのまま出力する。
    #
    #   body_html : Markdown 変換 + 独自タグ置換まで済ませた本文 HTML。
    #               投稿時（admin.create）・編集時（admin.update）に
    #               rendering.render_post_body() で生成して保存する。
    #   toc_html  : 記事冒頭に表示する目次 HTML。
    #               本文中に [toc] マーカーがある場合は None
    #               （その位置に目次が展開済みのため冒頭には表示しない）。
    #
    # どちらも nullable=True。
    #   ・新規投稿・編集では必ず埋まる。
    #   ・この機能の導入前に作成された既存記事は body_html が NULL のため、
    #     detail() 側で「NULL ならその場で生成 + 遅延保存（バックフィル）」する。
    #     この判定は body_html の NULL/非 NULL で行うため、
    #     toc_html が NULL（＝目次なし）でも影響しない。
    body_html = db.Column(db.Text, nullable=True)
    toc_html  = db.Column(db.Text, nullable=True)

    # ------------------------------------------------------------------
    # (3-5) 公開設定
    # ------------------------------------------------------------------
    # True = 全体公開 / False = 非公開（管理者だけ閲覧可）
    #   【パフォーマンス改善】index=True を付与。
    #   ほぼすべての公開ページが WHERE is_published = True で絞るため、
    #   単体インデックスを張る。トップの主経路は上の複合インデックス
    #   (is_published, created_at) がカバーするが、統計カウントや
    #   ジャンル内タグ集計など「並べ替えを伴わない公開状態フィルタ」では
    #   この単体インデックスが効く。
    #
    #   ※ is_published は真偽 2 値のため選択性（カーディナリティ）は低いが、
    #     非公開記事が少ない運用では「公開記事を絞る」用途で十分機能する。
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # ------------------------------------------------------------------
    # (3-6) リレーション
    # ------------------------------------------------------------------
    # user: Post → User への多対一リレーション
    #   backref='posts' により User インスタンスから user.posts で
    #   その管理者の全記事リストが取得できる
    user = db.relationship('User', backref=db.backref('posts', lazy=True))

    # hashtags: Post ↔ Hashtag の多対多リレーション
    #   secondary=post_hashtags → 中間テーブルを経由して結合
    #   lazy='selectin' → Post の id リストを IN 句で一括取得するロード戦略。
    #                      一覧ページで複数の Post をまとめてロードする際に
    #                      N+1 問題（記事ごとに個別クエリが走る問題）を防ぐ。
    #   backref → Hashtag インスタンスから hashtag.posts で
    #             そのタグが付いた全記事リストが取得できる
    hashtags = db.relationship(
        'Hashtag',
        secondary=post_hashtags,
        lazy='selectin',
        backref=db.backref('posts', lazy=True)
    )


# ======================================================================
# [4] User モデル（管理者）
# ======================================================================
class User(UserMixin, db.Model):
    # UserMixin が提供するメソッド:
    #   is_authenticated → ログイン済みかどうか（常に True を返す）
    #   is_active        → アカウントが有効か（常に True を返す）
    #   is_anonymous     → 匿名ユーザーかどうか（常に False を返す）
    #   get_id()         → Flask-Login がセッションに保存する一意のID文字列を返す

    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True)   # ログイン時に使うユーザー名（重複不可）
    password = db.Column(db.String(200))               # Werkzeug でハッシュ化したパスワード
    nickname = db.Column(db.String(60), nullable=True) # 表示名（省略可）。マイページから変更可能