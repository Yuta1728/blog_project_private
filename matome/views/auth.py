# views/auth.py
from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from extensions import db
from models import User
import config

auth_bp = Blueprint('auth', __name__)

# 個人専用ログイン機能
@auth_bp.route(f'/{config.ADMIN_LOGIN_PATH}', methods=['GET', 'POST'])
def secret_login():
    if current_user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=config.ADMIN_USERNAME).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("管理者としてログインしました。")
            return redirect('/mypage')
        else:
            flash("ユーザー名またはパスワードが正しくありません。")
            return redirect(f'/{config.ADMIN_LOGIN_PATH}')

    return render_template('login.html')

# ログアウト機能
@auth_bp.route('/logout')
@login_required  
def logout():
    logout_user()
    flash("ログアウトしました。")
    return render_template('login.html')