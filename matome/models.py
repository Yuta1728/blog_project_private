# models.py
from extensions import db
from flask_login import UserMixin
from datetime import datetime
import pytz

# ===== Post ↔ Hashtag 中間テーブル =====
post_hashtags = db.Table(
    'post_hashtags',
    db.Column('post_id',    db.Integer, db.ForeignKey('post.id'),    primary_key=True),
    db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtag.id'), primary_key=True)
)


class Hashtag(db.Model):
    __tablename__ = 'hashtag'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)   # '#' を除いた文字列で保存


class Post(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.TEXT, nullable=False)
    body         = db.Column(db.TEXT, nullable=False)
    genre        = db.Column(db.String(100), nullable=False, default='未分類')
    created_at   = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.timezone('Asia/Tokyo')))
    updated_at   = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.timezone('Asia/Tokyo')))
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    img_name     = db.Column(db.String(100), nullable=True)
    default_thumb = db.Column(db.String(100), nullable=True)

    # ユーザーIDとの紐付け
    user = db.relationship('User', backref=db.backref('posts', lazy=True))

    # 公開・非公開設定（デフォルトは True = 公開）
    is_published = db.Column(db.Boolean, nullable=False, default=True)

    # ===== ハッシュタグとの多対多リレーション =====
    hashtags = db.relationship(
        'Hashtag',
        secondary=post_hashtags,
        lazy='subquery',
        backref=db.backref('posts', lazy=True)
    )


class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True)
    password = db.Column(db.String(200))
    nickname = db.Column(db.String(60), nullable=True)