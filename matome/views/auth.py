# views/auth.py
#
# 【役割】
# 管理者のログイン・ログアウト機能を担うビューファイル。
#
# セキュリティ設計のポイント:
#   1. ログインページ URL を .env で隠蔽（秘密の URL = Security through obscurity）
#   2. ゲートキー方式（案A）: 合言葉 Cookie を持たない訪問者には
#      ログインページの存在自体を隠す（404 を返す）
#   3. ブルートフォース攻撃対策（連続失敗でセッションロックアウト）
#   4. パスワードはハッシュ値と照合（平文比較は行わない）
#   5. ログアウト後はトップページへリダイレクトし、
#      推測可能な URL（/logout）にログイン画面を紐付けない
#
# 【突破に必要な要素（多層防御）】
#   ① 秘密の URL（ADMIN_LOGIN_PATH）
#   ② ゲートキー（ADMIN_GATE_KEY による Cookie）
#   ③ ユーザー名（ADMIN_USERNAME）
#   ④ パスワード
#   → ①〜④ がすべて揃わない限り管理画面には到達できない。

import os
import time  # ロックアウト時間計算に使用
from flask import (Blueprint, render_template, request, redirect,
                   flash, session, abort, make_response)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash  # ハッシュ済みパスワードとの照合
from extensions import db
from models import User
import config

# Blueprint 定義: 'auth' という名前空間でルートを管理
# url_for('auth.secret_login') のように参照される
auth_bp = Blueprint('auth', __name__)

# ===================================================================
# ブルートフォース対策用定数
# ===================================================================
_MAX_ATTEMPTS    = 5    # この回数を超えてログイン失敗するとロックアウト
_LOCKOUT_SECONDS = 300  # ロック継続時間（秒）= 5分

# ===================================================================
# ゲートキー方式（案A）用定数
# ===================================================================
# ADMIN_GATE_KEY: ログインページを表示するための「合言葉」。
#   .env に長いランダム文字列を設定する。
#   生成例: python -c "import secrets; print(secrets.token_urlsafe(32))"
#
# 仕組み:
#   1. 管理者は「秘密URL?key=合言葉」をブックマークしておく
#   2. 初回アクセス時にサーバーが合言葉を検証し、Cookie を発行して
#      key なしの URL へリダイレクトする
#   3. 以降 _GATE_COOKIE_MAX_AGE の期間は Cookie だけでアクセス可能
#   4. Cookie を持たない第三者には 404 を返し、ページの存在自体を隠す
_GATE_KEY            = os.getenv("ADMIN_GATE_KEY")
_GATE_COOKIE_NAME    = 'admin_gate'
_GATE_COOKIE_MAX_AGE = 60 * 60 * 24 * 90  # 90日


# ===================================================================
# ゲートキー検証ヘルパー
# ===================================================================
def _check_gate():
    """
    ゲートキーによるアクセス制御を行う。

    戻り値:
      - Response オブジェクト: Cookie 発行のためのリダイレクトが必要な場合
      - None: ゲートを通過（ログイン処理へ進んで良い）

    通過できない場合はこの関数内で abort(404) する。

    【フェイルクローズ設計】
    ADMIN_GATE_KEY が未設定（設定忘れ・タイポ）の場合は、
    「無条件で通す」のではなく「無条件で 404」にする。
    設定ミスでゲートが無効化されて無防備になる事故を防ぐため。
    """
    # ゲートキー未設定 → 安全側に倒して常に 404
    if not _GATE_KEY:
        abort(404)

    # -------------------------------------------------------------------
    # ステップ 1: クエリパラメータで合言葉が来た場合
    # Cookie を発行して「key なしの URL」へリダイレクトする。
    #
    # リダイレクトする理由:
    #   ?key=xxx 付きの URL のままログイン画面を表示すると、
    #   その後のブラウザ履歴・アクセスログ・Referer に
    #   合言葉入りの URL が残り続けてしまう。
    #   即座に key なし URL へ付け替えることで露出を最小化する。
    # -------------------------------------------------------------------
    if request.args.get('key') == _GATE_KEY:
        resp = make_response(redirect(f'/{config.ADMIN_LOGIN_PATH}'))
        resp.set_cookie(
            _GATE_COOKIE_NAME,
            _GATE_KEY,
            httponly=True,                 # JavaScript から読み取れないようにする（XSS 対策）
            secure=request.is_secure,      # HTTPS 接続時のみ secure 属性を付与
                                           # （本番は HTTPS なので常に True、
                                           #   ローカル開発の http://localhost でも動作するよう動的に判定）
            samesite='Lax',                # 外部サイトからのリクエストに Cookie が乗らないようにする
            max_age=_GATE_COOKIE_MAX_AGE,  # 90日間有効
        )
        return resp

    # -------------------------------------------------------------------
    # ステップ 2: Cookie の検証
    # 正しいゲート Cookie を持っていない訪問者には 404 を返し、
    # 「そんなページは存在しない」ように見せる。
    # -------------------------------------------------------------------
    if request.cookies.get(_GATE_COOKIE_NAME) != _GATE_KEY:
        abort(404)

    # ゲート通過
    return None


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
    # ===================================================================
    # 【案A】ゲートキー検証（最優先で実行）
    # ===================================================================
    # 秘密 URL を知っているだけではログイン画面は表示されない。
    # 合言葉（?key=xxx）またはゲート Cookie を持たない訪問者には
    # 404 を返してページの存在自体を隠す。
    gate_response = _check_gate()
    if gate_response is not None:
        # 合言葉付きアクセスだった場合: Cookie 発行のリダイレクトを返す
        return gate_response

    # すでにログイン済みの場合はマイページへリダイレクト（二重ログイン防止）
    if current_user.is_authenticated:
        return redirect('/mypage')

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
@login_required  # 未ログイン時は app.py の unauthorized_handler により 404 を返す
def logout():
    # -------------------------------------------------------------------
    # ログアウト後はトップページへリダイレクトする。
    # ログイン画面を直接レンダリングすると、推測可能な URL（/logout）に
    # ログイン画面の HTML が紐付いてしまうため、リダイレクトのみ行う。
    #
    # なお、ゲート Cookie（admin_gate）はログアウトしても削除しない。
    # ログアウトは「認証の解除」であり「ゲート通過状態の解除」ではないため、
    # 同じブラウザからの再ログインは ?key= なしの秘密 URL で行える。
    # ゲート状態も破棄したい場合はブラウザの Cookie を削除する。
    # -------------------------------------------------------------------
    logout_user()
    flash('ログアウトしました。')
    return redirect('/')