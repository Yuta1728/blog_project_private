# views/auth.py
#
# 【役割】
# 管理者のログイン・ログアウト機能を担うビューファイル。
#
# セキュリティ設計のポイント:
#   1. ログインページ URL を .env で隠蔽（秘密の URL = Security through obscurity）
#   2. ブルートフォース攻撃対策（連続失敗でセッションロックアウト）
#   3. パスワードはハッシュ値と照合（平文比較は行わない）

from flask import Blueprint, render_template, request, redirect, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash  # ハッシュ済みパスワードとの照合
from extensions import db
from models import User
import config
import time  # ロックアウト時間計算に使用

# Blueprint 定義: 'auth' という名前空間でルートを管理
# url_for('auth.secret_login') のように参照される
auth_bp = Blueprint('auth', __name__)

# ===================================================================
# ブルートフォース対策用定数
# ===================================================================
_MAX_ATTEMPTS    = 5    # この回数を超えてログイン失敗するとロックアウト
_LOCKOUT_SECONDS = 300  # ロック継続時間（秒）= 5分


# ===================================================================
# ロックアウト判定ヘルパー関数
# ===================================================================
def _is_locked_out() -> bool:
    """
    セッションに記録された失敗回数・タイムスタンプを確認し、
    現在ロックアウト中かどうかを返す。

    【仕組み】
    session['login_attempts'] : 連続失敗回数（int）
    session['login_locked_at']: ロック開始時刻（Unix タイムスタンプ）

    Flask のセッションはサーバー側で署名済み Cookie として保存されるため
    クライアントから改ざんできない。また外部ストレージ（Redis など）不要で
    シンプルに実装できる。

    【本番運用での注意】
    セッションベースのロックは「ブラウザを変える」と回避できる。
    より強固にするには Flask-Limiter + Redis による IP ベースの制限を推奨。
    """
    attempts  = session.get('login_attempts', 0)
    locked_at = session.get('login_locked_at')

    if locked_at:
        elapsed   = time.time() - locked_at
        remaining = int(_LOCKOUT_SECONDS - elapsed)

        if elapsed < _LOCKOUT_SECONDS:
            # まだロック中 → 残り時間をユーザーに通知してリダイレクト
            flash(f'ログイン試行が多すぎます。{remaining} 秒後に再試行してください。', 'danger')
            return True
        else:
            # ロック時間が経過したのでセッションをリセットしてロック解除
            session.pop('login_attempts', None)
            session.pop('login_locked_at', None)

    return False  # ロック中ではない


# ===================================================================
# ログインビュー
# ===================================================================
# URL は config.ADMIN_LOGIN_PATH の値を使って動的に設定される（秘密のパス）
# 例: ADMIN_LOGIN_PATH=secret-xyz なら /secret-xyz でアクセス可能になる
@auth_bp.route(f'/{config.ADMIN_LOGIN_PATH}', methods=['GET', 'POST'])
def secret_login():
    # すでにログイン済みの場合はトップページへリダイレクト（二重ログイン防止）
    if current_user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        # ロックアウト中であればフラッシュを出してリダイレクト（認証処理を行わない）
        if _is_locked_out():
            return redirect(f'/{config.ADMIN_LOGIN_PATH}')

        # フォームから入力値を取得
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # DB から管理者ユーザーを検索
        # config.ADMIN_USERNAME と一致するユーザーのみ検索対象
        # （このアプリは単一管理者を想定しているため）
        user = User.query.filter_by(username=config.ADMIN_USERNAME).first()

        # check_password_hash: DB に保存されたハッシュ値と入力パスワードを安全に比較
        # （平文パスワードは保存されておらず、ハッシュ値からは元のパスワードを復元できない）
        if user and check_password_hash(user.password, password):
            # ===== 認証成功 =====
            # ロックアウト用のセッション変数をクリア（次回以降の失敗カウントをリセット）
            session.pop('login_attempts', None)
            session.pop('login_locked_at', None)

            # Flask-Login のセッションにユーザー情報を記録
            # これにより以降のリクエストで current_user が User オブジェクトになる
            login_user(user)

            flash('管理者としてログインしました。')
            return redirect('/mypage')

        else:
            # ===== 認証失敗 =====
            # 失敗回数をセッションに記録（セッションがなければ 0 から始める）
            attempts = session.get('login_attempts', 0) + 1
            session['login_attempts'] = attempts

            if attempts >= _MAX_ATTEMPTS:
                # 上限回数に達したらロック開始時刻を記録してロックアウト
                session['login_locked_at'] = time.time()
                flash(f'ログイン試行が {_MAX_ATTEMPTS} 回を超えました。'
                      f'{_LOCKOUT_SECONDS // 60} 分間ロックされます。', 'danger')
            else:
                # まだ余裕があれば汎用エラーメッセージを表示
                # 「ユーザー名が違う」「パスワードが違う」と個別に教えると
                # 攻撃者に存在するユーザー名を特定されるリスクがあるため
                # 意図的に「どちらが違うか」を明かさない書き方にしている
                flash('ユーザー名またはパスワードが正しくありません。')

            return redirect(f'/{config.ADMIN_LOGIN_PATH}')

    # GET リクエスト: ログインフォームを表示するだけ
    return render_template('login.html')


# ===================================================================
# ログアウトビュー
# ===================================================================
@auth_bp.route('/logout')
@login_required  # 未ログイン状態でのアクセスを拒否（login_manager.login_view へリダイレクト）
def logout():
    # Flask-Login のセッションからユーザー情報を削除する
    # これにより current_user が AnonymousUser に戻る
    logout_user()
    flash('ログアウトしました。')
    # ログアウト後はログインフォームを表示（リダイレクトではなく直接レンダリング）
    return render_template('login.html')