CREATE TABLE post (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    body VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    img_name VARCHAR(100),
    CONSTRAINT fk_user
        FOREIGN KEY(user_id) 
        REFERENCES "user"(id)
);


-- # 投稿のデータベース（postクラス）
-- class Post(db.Model):
--     id = db.Column(db.Integer, primary_key=True)
--     # primary_keyは主キー。
--     title = db.Column(db.String(100), nullable=False)
--     # unique=Trueを入れる場合は、100文字以内で、被りがあってはダメの意味。nullable=Falseは空文字はダメ。
--     body = db.Column(db.String(500), nullable=False)
--     created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.timezone('Asia/Tokyo')))
--     # default=lambda: datetime.nowは、データベースに投稿が保存される瞬間の東京の日時をデータベースに入れる
--     user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
--     # 投稿の項目名（user_id）に、↓のテーブルにあるUserクラスのidを保存する。投稿したユーザーのid
--     img_name = db.Column(db.String(100), nullable=True)
--     # 画像のデータベース項目。画像が無くても投稿には、問題ないため、nullableはtrueにしている。