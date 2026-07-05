# models.py
#
# 【役割】
# データベースのテーブル構造を Python クラスで定義するファイル（ORM モデル）。
# SQLAlchemy が各クラスを DB のテーブルに対応させる。
#
# テーブル構成:
#   user         ← User クラス     （管理者情報）
#   post         ← Post クラス     （ブログ記事）
#   hashtag      ← Hashtag クラス  （ハッシュタグ）
#   post_hashtags ← post_hashtags  （Post と Hashtag の中間テーブル）

from extensions import db          # extensions.py で作成した db インスタンスを使う
from flask_login import UserMixin  # ログイン機能に必要なメソッドを User に追加するミックスイン
from datetime import datetime
import pytz                        # タイムゾーン指定（Asia/Tokyo）に使用


# ===================================================================
# 中間テーブル: post_hashtags
# ===================================================================
# Post と Hashtag は「多対多」の関係（1つの記事に複数タグ、1つのタグが複数記事に付く）。
# SQLAlchemy では多対多を表現するために「中間テーブル」が必要。
#
# db.Table() で定義すると「モデルクラスを持たない純粋な関連テーブル」になる。
# Post モデルの hashtags リレーションが secondary=post_hashtags を参照することで
# Post ↔ Hashtag 間の JOIN が自動で行われる。
# -------------------------------------------------------------------
post_hashtags = db.Table(
    'post_hashtags',
    # post_id: post テーブルの id を外部キーとして参照
    db.Column('post_id',    db.Integer, db.ForeignKey('post.id'),    primary_key=True),
    # hashtag_id: hashtag テーブルの id を外部キーとして参照
    db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtag.id'), primary_key=True)
    # 2カラムの組み合わせが主キー → 同じ (post_id, hashtag_id) の重複を防ぐ
)


# ===================================================================
# Hashtag モデル
# ===================================================================
class Hashtag(db.Model):
    __tablename__ = 'hashtag'  # DB 上のテーブル名を明示的に指定

    id   = db.Column(db.Integer, primary_key=True)
    # name: '#' を除いたタグ文字列で保存（例: "Flask", "Python"）
    #   unique=True → 同じ名前のタグは 1 件だけ存在できる
    #   nullable=False → 必須項目
    name = db.Column(db.String(100), nullable=False, unique=True)

    # posts リレーションは Post モデル側の backref で自動定義される（下記参照）


# ===================================================================
# Post モデル（ブログ記事）
# ===================================================================
class Post(db.Model):
    # __tablename__ を省略すると SQLAlchemy がクラス名を小文字化した 'post' をテーブル名にする

    # --- 基本カラム ---
    id         = db.Column(db.Integer, primary_key=True)  # 記事の一意な識別子（自動採番）
    title      = db.Column(db.TEXT, nullable=False)        # 記事タイトル（必須）
    body       = db.Column(db.TEXT, nullable=False)        # 記事本文（マークダウン形式、必須）
    genre      = db.Column(db.String(100), nullable=False, default='未分類')  # ジャンル名

    # --- 日時カラム ---
    # created_at: 投稿日時。lambda を使ってインスタンス生成時の時刻を設定する。
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(pytz.timezone('Asia/Tokyo')))

    # updated_at: 更新日時。
    #   nullable=True にすることで「まだ一度も更新されていない」状態を NULL で表現する。
    #   これにより detail.html の「更新日時 != 投稿日時」という条件判定が
    #   秒単位のズレで誤表示されるバグを防ぐ。
    #   - 新規投稿時: NULL（テンプレート側で「更新なし」として扱う）
    #   - 編集保存時: admin.py の update() で現在時刻をセット
    updated_at = db.Column(db.DateTime, nullable=True)

    # --- ユーザー紐付け ---
    # user_id: user テーブルの id への外部キー（どの管理者が書いた記事か）
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # --- 画像関連カラム ---
    # img_name: アップロード画像のファイル名をカンマ区切りで保存
    #   例: "uuid1.jpg,uuid2.png"
    #   複数画像に対応するため 1 カラムにまとめて格納している
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

    # img_captions: 各画像のキャプションをタブ区切りで保存
    #   例: "東京タワー全景\t夜景のアップ"
    #   img_name のカンマ区切りと順番が対応する（img_name[0] → captions[0]）
    img_captions  = db.Column(db.Text, nullable=True)

    # --- 公開設定 ---
    # True = 全体公開 / False = 非公開（管理者だけ閲覧可）
    is_published = db.Column(db.Boolean, nullable=False, default=True)

    # --- リレーション ---
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


# ===================================================================
# User モデル（管理者）
# ===================================================================
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