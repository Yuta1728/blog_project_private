CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    username VARCHAR(30) UNIQUE,
    password VARCHAR(200)
);


-- # ユーザーIDパスワードのデータベース（Userクラス）
-- class User(UserMixin, db.Model):
--     id = db.Column(db.Integer, primary_key=True)
--     username = db.Column(db.String(30), unique=True) 
--     # ユーザー名は被らないようにuniqueを入れておく
--     password = db.Column(db.String(200))
