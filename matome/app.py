# ======================================================================
# app.py — Flask アプリケーションのエントリーポイント
# ======================================================================
#
# 【役割】
#   Flask アプリを生成・設定する起点となるファイル。
#   create_app() 関数でアプリを組み立てる「Application Factory パターン」を採用。
#
#   Application Factory パターンのメリット:
#     - テスト時に設定を変えた別アプリを簡単に作れる
#     - extensions.py と組み合わせることで循環インポートを避けられる
#
# 【このファイルの構成（目次）】
#   [1] import / Blueprint の読み込み
#   [2] _is_production()      : 本番環境かどうかの判定ヘルパー
#   [3] _configure_logging()  : アプリケーションログの設定
#   [3.5] _register_static_url_helper(): static_url（キャッシュバスティング）の登録
#   [4] _register_cli_commands(): 管理コマンドの登録
#        (4-1) rerender-posts        : 本文 HTML の再生成
#        (4-2) clean-orphan-images   : 孤児画像ファイルの掃除
#   [5] create_app()          : アプリ生成ファクトリ関数
#        (5-1) 本番判定
#        (5-2) ログ設定
#        (5-3) ProxyFix の適用（リバースプロキシ対応）
#        (5-4) SECRET_KEY の設定
#        (5-5) セッション Cookie の属性設定
#        (5-6) アップロードサイズ制限
#        (5-7) データベース接続 URL の設定（PostgreSQL / SQLite 両対応）
#        (5-7.5) static_url の登録
#        (5-8) 拡張機能の初期化（db / migrate / login_manager）
#        (5-9) CSRF 保護の適用
#        (5-10) Flask-Login の詳細設定（unauthorized_handler / user_loader）
#        (5-11) セキュリティヘッダーの付与
#        (5-12) カスタムエラーハンドラー（404 / 500 / 413）
#        (5-13) Blueprint の登録
#        (5-14) 管理コマンドの登録
#   [6] 直接実行時のエントリポイント（python app.py）
#
# ======================================================================


# ======================================================================
# [1] import / Blueprint の読み込み
# ======================================================================

import os
import sys
import logging
import click                                       # CLI コマンドのオプション定義に使用
from urllib.parse import urlparse                  # 413 の遷移先判定（Open Redirect 対策）に使用
from flask import (Flask, flash, redirect, url_for, abort,
                   render_template, request)
from flask.logging import default_handler          # Flask が既定で付ける StreamHandler
from flask_login import current_user               # 413 の遷移先をログイン状態で分岐
from flask_wtf.csrf import CSRFProtect  # 全フォームへの CSRF トークン強制適用
from werkzeug.middleware.proxy_fix import ProxyFix  # リバースプロキシ配下での HTTPS 判定補正
from extensions import db, login_manager, migrate
from models import User, Post
from rendering import render_post_body, RENDER_VERSION
import config

# Blueprint: 機能ごとにルートをまとめたモジュール（views/ 配下で定義）
from views.auth  import auth_bp   # ログイン・ログアウト関連
from views.blog  import blog_bp   # 一般公開ページ（一覧・詳細・ジャンル）
from views.admin import admin_bp  # 管理者専用ページ（投稿・編集・削除・マイページ）


# ======================================================================
# [2] 本番環境判定ヘルパー
# ======================================================================

def _is_production() -> bool:
    """
    現在の実行環境が「本番」かどうかを判定する。
    create_app() の各設定と __main__ ブロックの両方から参照するため、
    判定式をこの 1 か所に集約している。

    判定条件:
      - DATABASE_URL が設定されている（PaaS の PostgreSQL 等）か
      - FLASK_ENV=production が設定されている
    のいずれかであれば本番とみなす。

    【PythonAnywhere での注意】
      SQLite 運用（USE_SQLITE=1）では DATABASE_URL を設定しないため、
      必ず環境変数に FLASK_ENV=production を設定して本番扱いにすること。
      これにより SECRET_KEY の必須化・Secure Cookie が有効になる。
    """
    return (
        os.getenv("DATABASE_URL") is not None
        or os.getenv("FLASK_ENV") == "production"
    )


# ======================================================================
# [3] ログ設定
# ======================================================================

def _configure_logging(app: Flask, is_production: bool) -> None:
    """
    アプリケーションログ（app.logger）の出力先とフォーマットを設定する。

    各ビューは
        current_app.logger.exception('...')
    を呼ぶだけで、メッセージとトレースバックがこの設定先へ流れる。
    例外を捕捉して flash で通知する箇所でも、サーバー側に原因
    （トレースバック）を残せるようにするのが目的。

    【出力先を stderr にしている理由】
    PythonAnywhere は WSGI プロセスの stderr をそのまま「Error log」に
    書き出す。ローカル開発でもコンソールに出るため、追加設定なしに
    本番・開発の双方でログを確認できる。ファイル出力が必要になった場合は、
    ここに RotatingFileHandler を追加すればよい（呼び出し側は変更不要）。

    【ログレベル】
      環境変数 LOG_LEVEL があればそれを優先。
      無ければ 本番 = INFO / 開発 = DEBUG。
      logger.exception() は ERROR レベルなので、
      どの設定でも障害の記録は必ず残る。

    @param app:           設定対象の Flask アプリ
    @param is_production: 本番環境かどうか（既定レベルの決定に使う）
    """
    # ------------------------------------------------------------------
    # STEP 1. 出力レベルの決定
    # ------------------------------------------------------------------
    level_name = os.getenv('LOG_LEVEL', 'INFO' if is_production else 'DEBUG').upper()
    # 不正な値（タイポなど）が入っていても落ちないよう INFO にフォールバックする
    level = getattr(logging, level_name, logging.INFO)

    # ------------------------------------------------------------------
    # STEP 2. Flask 既定のハンドラを外す
    # ------------------------------------------------------------------
    # app.logger は初回アクセス時に Flask が default_handler を自動で付ける。
    # そのまま自前のハンドラを追加すると同じログが 2 行出てしまうため、
    # 既定のものを取り除いてから登録する。
    app.logger.removeHandler(default_handler)

    # ------------------------------------------------------------------
    # STEP 3. 自前のハンドラを登録（多重登録の防止つき）
    # ------------------------------------------------------------------
    # create_app() はテスト等で複数回呼ばれることがある。app.logger は
    # アプリ名ごとの共有ロガーのため、素直に addHandler すると
    # 呼ばれるたびにハンドラが増え、ログが 2 行・3 行と重複していく。
    # 目印の属性を付けておき、既に自前ハンドラがあれば付け替える。
    for handler in list(app.logger.handlers):
        if getattr(handler, '_mitoblog_handler', False):
            app.logger.removeHandler(handler)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    stream_handler._mitoblog_handler = True   # 多重登録判定用の目印

    app.logger.addHandler(stream_handler)
    app.logger.setLevel(level)

    # ルートロガーへ伝播させない（伝播すると環境によっては二重出力になる）
    app.logger.propagate = False

    app.logger.info('ログ設定を初期化しました (level=%s, production=%s)',
                    level_name, is_production)


# ======================================================================
# [3.5] 静的ファイルのキャッシュバスティング
# ======================================================================

def _register_static_url_helper(app: Flask) -> None:
    """
    テンプレートから使う static_url() を登録し、静的ファイルのキャッシュ期間を延ばす。

    テンプレートは静的ファイルを static_url('css/index.css') の形で参照する。
    static_url は Flask/Jinja の標準関数ではなくこのアプリ独自の関数のため、
    ここで @app.template_global として登録して初めてテンプレートから使える
    （登録しないと 'static_url' is undefined というエラーになる）。

    【static_url が何をするか】
    ファイルの更新時刻（mtime）を ?v=... というクエリとして URL に付ける。
        /static/css/index.css?v=1721500000
    ファイルを更新すると mtime が変わって URL も変わるため、ブラウザは
    「別ファイル」とみなして新しい内容を取得する。これにより静的ファイルを
    長期間キャッシュさせても「更新したのに古い CSS が残る」問題が起きない
    （＝Ctrl+Shift+R での強制リロードが不要になる）。

    あわせて SEND_FILE_MAX_AGE_DEFAULT を 1 年に設定し、
    静的ファイルに長期キャッシュを効かせる（?v= が付くので安全）。

    @param app: 対象の Flask アプリ
    """
    # 静的ファイルのブラウザキャッシュ期間を 1 年に延ばす。
    # URL に ?v=mtime が付くため、更新時は URL が変わって即反映される。
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 60 * 60 * 24 * 365  # 1 年（秒）

    @app.template_global()
    def static_url(filename: str) -> str:
        """
        テンプレート用ヘルパー。url_for('static', ...) に ?v=mtime を付けて返す。

        使い方（テンプレート側）:
            href="{{ static_url('css/index.css') }}"

        - ファイルが存在すれば mtime（更新時刻の整数秒）を v として付与する。
        - 何らかの理由でファイルが見つからない場合は v=0 とし、
          少なくとも url_for と同等の URL を返して 500 を避ける
          （存在しないパスは元々 404 になるだけで、ここでは落とさない）。
        """
        try:
            path = os.path.join(app.static_folder, filename)
            version = int(os.path.getmtime(path)) if os.path.exists(path) else 0
        except OSError:
            # 稀な I/O エラーでもテンプレート描画を止めない
            version = 0
        return url_for('static', filename=filename, v=version)


# ======================================================================
# [4] 管理コマンドの登録
# ======================================================================

def _register_cli_commands(app: Flask) -> None:
    """
    `flask <コマンド名>` で実行できる管理コマンドを登録する。

    登録するコマンド:
      (4-1) rerender-posts       … 本文 HTML の再生成
      (4-2) clean-orphan-images  … 孤児画像ファイルの掃除
    """

    # ------------------------------------------------------------------
    # (4-1) 本文 HTML の再生成
    # ------------------------------------------------------------------
    # rendering.py を変更して RENDER_VERSION を上げた後、既存記事の
    # キャッシュ HTML（body_html / toc_html）をまとめて作り直すためのコマンド。
    @app.cli.command('rerender-posts')
    @click.option('--all', 'rerender_all', is_flag=True, default=False,
                  help='バージョンに関係なく全記事を再生成する。')
    @click.option('--dry-run', 'dry_run', is_flag=True, default=False,
                  help='対象を表示するだけで DB には保存しない。')
    def rerender_posts(rerender_all: bool, dry_run: bool):
        """記事本文のキャッシュ HTML（body_html / toc_html）を再生成する。"""

        # STEP 1. 全記事を取得して対象を絞り込む
        # 「render_version != RENDER_VERSION」を SQL で書くと NULL 行が漏れるため、
        # 判定は Python 側で明示的に行う。
        posts = Post.query.order_by(Post.id).all()

        targets = [
            p for p in posts
            if rerender_all
            or p.body_html is None
            or p.render_version != RENDER_VERSION
        ]

        click.echo(f'全記事: {len(posts)} 件 / 再生成の対象: {len(targets)} 件 '
                   f'(RENDER_VERSION = {RENDER_VERSION})')

        if not targets:
            click.echo('再生成が必要な記事はありません。')
            return

        if dry_run:
            for p in targets:
                click.echo(f'  [dry-run] post_id={p.id} '
                           f'version={p.render_version} title={p.title[:30]!r}')
            click.echo('--dry-run のため保存は行いませんでした。')
            return

        # STEP 2. 1 件ずつ再生成して render_version を更新
        for p in targets:
            p.body_html, p.toc_html = render_post_body(
                p.body, p.img_name, p.img_captions
            )
            p.render_version = RENDER_VERSION
            # updated_at は「記事内容の更新日時」なので、
            # 表示上の HTML を作り直しただけのここでは触らない。

        # STEP 3. まとめて commit
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('本文 HTML の一括再生成に失敗しました。')
            raise click.ClickException(
                '再生成の保存に失敗しました。詳細はログを確認してください。'
            )

        click.echo(f'{len(targets)} 件の記事を再生成しました。')

    # ------------------------------------------------------------------
    # (4-2) 孤児画像ファイルの掃除
    # ------------------------------------------------------------------
    @app.cli.command('clean-orphan-images')
    @click.option('--delete', 'do_delete', is_flag=True, default=False,
                  help='実際にファイルを削除する（付けないと一覧表示のみ）。')
    def clean_orphan_images(do_delete: bool):
        """
        static/img/posts/ 内の「どの記事からも参照されていない」孤児画像を掃除する。

        【孤児画像が発生するケース】
        DB commit 失敗時の後片付けは実装済みだが、次のケースでは
        参照されない画像ファイルがディスク上に残り続ける。
          ・commit と _delete_images() の間でプロセスが異常終了した
          ・バグや手動操作で img_name から参照が外れた
          ・static/img/posts/ に手動配置した旧ファイル
            （日本語名のスクリーンショット等）
        無料枠の限られたディスクをじわじわ食い潰すため、
        参照の無いファイルを列挙・削除できるようにする。

        【対象ディレクトリについて】
        本文画像（img_name）とサムネイル専用画像（thumbnail_img）は
        いずれも static/img/posts/ に保存される。
        一方、プリセットのデフォルトサムネイル（default_thumb）は
        static/img/thbnails/ にあり、このコマンドの対象外
        （＝誤って消さない）。

        【安全設計】
        既定は「一覧表示のみ（ドライラン）」。--delete を付けたときだけ
        実際に削除する。削除に失敗しても 1 件ずつログに残して続行する。

        使い方:
            flask clean-orphan-images            … 孤児を一覧表示するだけ
            flask clean-orphan-images --delete   … 実際に削除する
        """
        posts_dir = os.path.join(app.static_folder, 'img', 'posts')
        if not os.path.isdir(posts_dir):
            click.echo(f'ディレクトリが見つかりません: {posts_dir}')
            return

        # STEP 1. DB が参照しているファイル名を集める
        #   img_name（カンマ区切り）と thumbnail_img の両方を対象にする。
        #   with_entities で必要な 2 カラムだけを取得して軽量化する。
        referenced: set[str] = set()
        rows = Post.query.with_entities(Post.img_name, Post.thumbnail_img).all()
        for img_name, thumbnail_img in rows:
            if img_name:
                referenced.update(x.strip() for x in img_name.split(',') if x.strip())
            if thumbnail_img and thumbnail_img.strip():
                referenced.add(thumbnail_img.strip())

        # STEP 2. 実ファイルを走査して孤児を判定
        orphans = []
        for entry in os.listdir(posts_dir):
            full = os.path.join(posts_dir, entry)
            if not os.path.isfile(full):
                continue          # サブディレクトリ等はスキップ
            if entry not in referenced:
                orphans.append(entry)

        # STEP 3. 結果表示 / 削除
        if not orphans:
            click.echo(f'孤児画像はありません（DB 参照 {len(referenced)} 件）。')
            return

        click.echo(f'孤児画像: {len(orphans)} 件（DB 参照 {len(referenced)} 件）')
        for f in orphans:
            click.echo(f'  orphan: {f}')

        if not do_delete:
            click.echo('--delete を付けると実際に削除します。')
            return

        deleted = 0
        for f in orphans:
            try:
                os.remove(os.path.join(posts_dir, f))
                deleted += 1
            except OSError:
                app.logger.exception('孤児画像の削除に失敗しました (file=%s)', f)

        click.echo(f'{deleted} / {len(orphans)} 件を削除しました。')
        app.logger.info('孤児画像を掃除しました (deleted=%d, total=%d)',
                        deleted, len(orphans))


# ======================================================================
# [5] create_app() : アプリ生成ファクトリ関数
# ======================================================================

def create_app():
    """
    Flask アプリインスタンスを生成して返すファクトリ関数。
    """

    # ------------------------------------------------------------------
    # STEP 1. Flask インスタンスを生成
    # ------------------------------------------------------------------
    app = Flask(__name__)

    # ------------------------------------------------------------------
    # STEP 2. 本番環境かどうかを判定（以降の設定で共用する）
    # ------------------------------------------------------------------
    is_production = _is_production()

    # ------------------------------------------------------------------
    # STEP 3. ログ設定（できるだけ早い段階で有効化する）
    # ------------------------------------------------------------------
    # 以降の初期化処理（DB 接続設定など）で問題が起きたときも
    # ログに残るよう、他の設定より先に済ませておく。
    _configure_logging(app, is_production)

    # ------------------------------------------------------------------
    # STEP 4. ProxyFix の適用（リバースプロキシ配下での HTTPS 判定）
    # ------------------------------------------------------------------
    # Render / Heroku / PythonAnywhere などでは、HTTPS はリバースプロキシで
    # 終端され、Flask アプリ自体には HTTP で届く。そのままだと
    # request.is_secure が本番でも False と判定されてしまうため、
    # ProxyFix で X-Forwarded-Proto / X-Forwarded-Host を信頼して補正する。
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ------------------------------------------------------------------
    # STEP 5. SECRET_KEY の設定（セッション・CSRF トークンの署名に使用）
    # ------------------------------------------------------------------
    # 本番では未設定を許さない（起動時に停止させる）。開発ではローカル用の
    # 固定値でフォールバックする。
    secret_key = os.getenv("SECRET_KEY")

    if not secret_key:
        if is_production:
            raise ValueError("【重大なエラー】本番環境の環境変数 'SECRET_KEY' が設定されていません。")
        else:
            secret_key = "dev-secret-key-for-local-use"

    app.config['SECRET_KEY'] = secret_key

    # ------------------------------------------------------------------
    # STEP 6. セッション Cookie の属性を明示的に設定（セキュリティ）
    # ------------------------------------------------------------------
    # HttpOnly で JS からの読み取りを防ぎ、SameSite=Lax で外部サイトからの
    # 送信を制限する。Secure は本番（HTTPS）でのみ有効にする。
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE']   = is_production

    # ------------------------------------------------------------------
    # STEP 7. ファイルアップロードサイズ制限（30MB）
    # ------------------------------------------------------------------
    app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB

    # ------------------------------------------------------------------
    # STEP 8. データベース接続 URL の設定（PostgreSQL / SQLite 両対応）
    # ------------------------------------------------------------------
    # 優先順位:
    #   (1) DATABASE_URL が設定されていれば最優先（Postgres でも SQLite でも可）
    #   (2) USE_SQLITE=1 なら、プロジェクト内 instance/blog.db を SQLite として使う
    #       （PythonAnywhere 無料枠向け。永続ディスクに DB ファイルが残る）
    #   (3) どちらもなければローカル開発（docker-compose の PostgreSQL）に接続
    #
    # 【PythonAnywhere 無料枠での使い方】
    #   環境変数に USE_SQLITE=1 を設定するだけでよい。
    #   DB ファイルの絶対パスは app.py の位置から自動計算するので、
    #   長い sqlite:////home/... のようなパスを手で書く必要はない。
    database_url = os.getenv("DATABASE_URL")
    use_sqlite   = os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes")

    if database_url:
        # (1) 明示指定を最優先
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.logger.info('DB 接続先: DATABASE_URL（明示指定）を使用します。')

    elif use_sqlite:
        # (2) SQLite（PythonAnywhere など）
        basedir      = os.path.abspath(os.path.dirname(__file__))
        instance_dir = os.path.join(basedir, 'instance')
        os.makedirs(instance_dir, exist_ok=True)   # instance/ がなければ作成
        sqlite_path  = os.path.join(instance_dir, 'blog.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_path}"
        app.logger.info('DB 接続先: SQLite (%s)', sqlite_path)

    else:
        # (3) ローカル開発用フォールバック（docker-compose の PostgreSQL）
        local_db_url = (
            f"postgresql+psycopg://{config.postgre_user}:{config.postgre_password}"
            f"@localhost:15432/{config.postgre_DB}"
        )
        app.config['SQLALCHEMY_DATABASE_URI'] = local_db_url
        app.logger.info('DB 接続先: ローカル PostgreSQL (localhost:15432)')

    # モデル変更のたびにイベントを発行する機能（使わないのでオフにしてメモリ節約）
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ------------------------------------------------------------------
    # STEP 8.5. 静的ファイルのキャッシュバスティング（static_url 登録）
    # ------------------------------------------------------------------
    # テンプレートが static_url('...') を呼べるようにする。
    # これを登録しないと base.html などで
    #   UndefinedError: 'static_url' is undefined
    # になる。
    _register_static_url_helper(app)

    # ------------------------------------------------------------------
    # STEP 9. 拡張機能の初期化（extensions.py で作ったインスタンスを app に紐付け）
    # ------------------------------------------------------------------
    db.init_app(app)             # SQLAlchemy を app に接続
    migrate.init_app(app, db)    # Alembic マイグレーションを app + db に接続
    login_manager.init_app(app)  # Flask-Login を app に接続

    # ------------------------------------------------------------------
    # STEP 10. CSRF 保護の適用
    # ------------------------------------------------------------------
    csrf = CSRFProtect()
    csrf.init_app(app)

    # ------------------------------------------------------------------
    # STEP 11. Flask-Login の詳細設定
    # ------------------------------------------------------------------
    login_manager.login_view = None

    @login_manager.unauthorized_handler
    def unauthorized():
        # 未ログイン状態で @login_required なページへアクセスされた場合、
        # ログインページへ誘導せず 404 Not Found を返して存在を偽装する。
        abort(404)

    @login_manager.user_loader
    def load_user(user_id):
        # セッションに保存された user_id から User を 1 件取得する（無ければ None）。
        # db.session.get() は主キー取得の推奨 API。
        return db.session.get(User, int(user_id))

    # ------------------------------------------------------------------
    # STEP 12. セキュリティヘッダーの付与
    # ------------------------------------------------------------------
    # レスポンスごとに、MIME スニッフィング防止・クリックジャッキング防止・
    # リファラ制限のヘッダーを付ける（既に付いていれば上書きしない）。
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    # ------------------------------------------------------------------
    # STEP 13. カスタムエラーハンドラー（404 / 500 / 413）
    # ------------------------------------------------------------------
    # 404 / 500 は専用テンプレートを返す。このアプリは「認証の存在隠蔽」で
    # 404 を多用するため、その 404 も見た目を整えたページで返す。
    # 413（アップロードのサイズ超過）は、ログイン状態を見て遷移先を分岐する
    # （未ログインだと admin.mypage は login_required により 404 になるため）。

    # (13-1) 404 Not Found
    @app.errorhandler(404)
    def page_not_found(error):
        # 未ログインでの @login_required アクセス（unauthorized_handler → abort(404)）も
        # ここに来る。存在隠蔽の意図を保ったまま、見た目だけ整える。
        return render_template('404.html'), 404

    # (13-2) 500 Internal Server Error
    @app.errorhandler(500)
    def internal_server_error(error):
        # 例外発生時はセッションが中途半端な状態のことがあるため、必ず戻す。
        # これ以降テンプレート描画で DB を触っても安全にしておく。
        db.session.rollback()
        # errorhandler の中では例外情報がまだ有効なので、
        # exception() でトレースバックまで記録できる。
        app.logger.exception('500 Internal Server Error が発生しました。')
        return render_template('500.html'), 500

    # (13-3) 413 Request Entity Too Large
    @app.errorhandler(413)
    def request_entity_too_large(error):
        app.logger.warning('アップロードサイズ超過を検出しました (limit=%s bytes)',
                           app.config.get('MAX_CONTENT_LENGTH'))
        flash("アップロードされたファイルの合計サイズが30MBを超えています。", "danger")

        # ログイン済みならマイページへ戻す。
        # 未ログインだと admin.mypage は login_required により 404 になるため、
        # 直前ページ（同一オリジンのみ）かトップへ戻す。
        if current_user.is_authenticated:
            return redirect(url_for('admin.mypage'))

        referrer = request.referrer
        if referrer:
            ref = urlparse(referrer)
            req = urlparse(request.url)
            same_origin = (ref.scheme == req.scheme and ref.netloc == req.netloc)
            if same_origin:
                return redirect(referrer)

        return redirect(url_for('blog.index'))

    # ------------------------------------------------------------------
    # STEP 14. Blueprint の登録
    # ------------------------------------------------------------------
    app.register_blueprint(auth_bp)   # /login, /logout 系
    app.register_blueprint(blog_bp)   # /, /about, /howto, /genre, /<id>/detail 系
    app.register_blueprint(admin_bp)  # /create, /<id>/update, /<id>/delete, /mypage 系

    # ------------------------------------------------------------------
    # STEP 15. 管理コマンドの登録（flask rerender-posts / clean-orphan-images）
    # ------------------------------------------------------------------
    _register_cli_commands(app)

    app.logger.info('アプリケーションの初期化が完了しました。')

    return app


# ======================================================================
# [6] 直接実行時のエントリポイント（python app.py で起動）
# ======================================================================
#
# 【重要】PythonAnywhere では app.run() は使われない。
#   PythonAnywhere は WSGI ファイルから create_app() を呼び出して
#   application 変数として公開する方式のため、この __main__ ブロックは
#   ローカル開発でのみ実行される（サーバー上では import されるだけ）。

if __name__ == '__main__':
    app = create_app()

    # デバッグモードは「本番でない」かつ FLASK_DEBUG=1/true のときだけ有効にする。
    debug_mode = (
        not _is_production()
        and os.getenv("FLASK_DEBUG", "").lower() in ("1", "true")
    )

    app.run(debug=debug_mode)