# views/auth.py
from flask import Blueprint, render_template, request, redirect, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from extensions import db
from models import User
import config
import time

auth_bp = Blueprint('auth', __name__)

# ===== ブルートフォース対策用定数 =====
_MAX_ATTEMPTS   = 5    # 許容失敗回数
_LOCKOUT_SECONDS = 300  # ロック時間（秒）


def _is_locked_out() -> bool:
    """
    セッションに記録された失敗回数・タイムスタンプを確認し、
    ロックアウト状態かどうかを返す。
    [新規追加] ブルートフォース攻撃への対策。
    Flask セッション（サーバー側署名済み Cookie）を使用するため
    外部ストレージ不要で導入できる。
    本番では Flask-Limiter + Redis による IP ベース制限を推奨。
    """
    attempts  = session.get('login_attempts', 0)
    locked_at = session.get('login_locked_at')

    if locked_at:
        elapsed = time.time() - locked_at
        if elapsed < _LOCKOUT_SECONDS:
            remaining = int(_LOCKOUT_SECONDS - elapsed)
            flash(f'ログイン試行が多すぎます。{remaining} 秒後に再試行してください。', 'danger')
            return True
        else:
            # ロック解除
            session.pop('login_attempts', None)
            session.pop('login_locked_at', None)

    return False


# ===== ログイン =====

@auth_bp.route(f'/{config.ADMIN_LOGIN_PATH}', methods=['GET', 'POST'])
def secret_login():
    if current_user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        if _is_locked_out():
            return redirect(f'/{config.ADMIN_LOGIN_PATH}')

        username = request.form.get('username', '')
        password = request.form.get('password', '')

        user = User.query.filter_by(username=config.ADMIN_USERNAME).first()

        if user and check_password_hash(user.password, password):
            # 認証成功 → セッションリセット
            session.pop('login_attempts', None)
            session.pop('login_locked_at', None)
            login_user(user)
            flash('管理者としてログインしました。')
            return redirect('/mypage')
        else:
            # 認証失敗 → 試行回数を記録
            attempts = session.get('login_attempts', 0) + 1
            session['login_attempts'] = attempts
            if attempts >= _MAX_ATTEMPTS:
                session['login_locked_at'] = time.time()
                flash(f'ログイン試行が {_MAX_ATTEMPTS} 回を超えました。'
                      f'{_LOCKOUT_SECONDS // 60} 分間ロックされます。', 'danger')
            else:
                flash('ユーザー名またはパスワードが正しくありません。')
            return redirect(f'/{config.ADMIN_LOGIN_PATH}')

    return render_template('login.html')


# ===== ログアウト =====

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。')
    return render_template('login.html')