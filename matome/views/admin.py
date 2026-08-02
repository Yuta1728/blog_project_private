# ======================================================================
# views/admin.py — 管理者専用ページ（ログイン必須）
# ======================================================================
#
# 【役割】
#   管理者専用ページのルートとロジックを担うビューファイル。
#
#   担当機能:
#     /create          → 新規記事投稿
#     /<id>/update     → 記事編集
#     /<id>/delete     → 記事削除
#     /mypage          → マイページ（投稿一覧・ニックネーム変更）
#
# 【ドメインロジックは services/ に分離している】
#   画像・ハッシュタグ・キャプションの処理は services パッケージへ切り出した。
#   ビューは「フォームを受け取り → サービスを呼び → 結果を返す」ことに専念する。
#     services/images.py   … save_images / delete_images / save_thumbnail など
#     services/hashtags.py … parse_hashtag_input / sync_hashtags /
#                            delete_orphaned_hashtags
#     services/captions.py … parse_img_captions
#
#   特に画像処理サービスは、重い Pillow / filetype を「関数の内側」で遅延
#   import する。そのため、このビューを import してもアプリ起動時には Pillow を
#   読み込まず、画像アップロードのリクエストで初めて読み込む
#   （起動時間・ベースメモリの節約になる）。
#
# 【このファイルの構成（目次）】
#   [1] 定数定義（一覧のページネーション設定）
#   [2] _get_genre_list()  : 投稿フォームのジャンル選択肢を生成
#   [3] create()  : 新規投稿ビュー
#   [4] update()  : 記事編集ビュー
#   [5] delete()  : 記事削除ビュー
#   [6] mypage()  : マイページビュー
#
# 【設計上のポイント】
#   ・本文 HTML の事前生成:
#     本文（Markdown + 独自タグ）の HTML 変換は閲覧のたびに行うと無駄なため、
#     投稿・編集時に rendering.render_post_body() で (body_html, toc_html) を
#     生成し、Post の同名カラムに保存する。本文・画像（img_name / img_captions）が
#     確定した後に生成することで、[imgN] 置換まで含めた最終形をキャッシュできる。
#     詳細表示（views/blog.py の detail）は保存済み HTML をそのまま出力する。
#   ・レンダラのバージョン記録:
#     生成した HTML と一緒に、生成に使った rendering.RENDER_VERSION を
#     Post.render_version として保存する。rendering.py を変更して
#     RENDER_VERSION を +1 すれば、既存記事も detail() 側で作り直される。
#   ・例外時のログ:
#     commit 失敗や画像処理エラーは except で捕まえ、ユーザーには flash で
#     通知する。あわせて各 except で current_app.logger を呼び、サーバー側に
#     原因（トレースバック）を残す。
#       ・logger.exception() … 想定外の失敗。トレースバックまで記録する
#       ・logger.warning()   … 想定内だが記録しておきたい事象（後始末など）
#     出力先は app.py の _configure_logging() が設定しており、
#     PythonAnywhere では Web タブの「Error log」から確認できる。
#
# ======================================================================

from flask import Blueprint, render_template, request, redirect, flash, current_app
from flask_login import current_user, login_required
from datetime import datetime
from urllib.parse import urlparse  # Open Redirect 対策のための URL パース
import pytz
from extensions import db
from models import Post
from constants import DEFAULT_GENRES
# 本文 → (body_html, toc_html) の事前生成と、そのレンダラのバージョン
from rendering import render_post_body, RENDER_VERSION
import config

# ドメインロジック層（services/）から必要な処理を取り込む。
# services.images は Pillow / filetype を関数内で遅延 import するため、
# ここで import してもアプリ起動時に Pillow は読み込まれない。
from services.images import save_images, delete_images, save_thumbnail
from services.hashtags import (parse_hashtag_input, sync_hashtags,
                               delete_orphaned_hashtags)
from services.captions import parse_img_captions

admin_bp = Blueprint('admin', __name__)


# ======================================================================
# [1] 定数定義: 一覧のページネーション設定
# ======================================================================
# マイページ（mypage）の 1 ページあたりの表示件数。
# トップページ（views/blog.py の POSTS_PER_PAGE）と同じ 4 件にそろえている。
POSTS_PER_PAGE = 4


# ======================================================================
# [2] ジャンルリスト生成ヘルパー（投稿フォームのジャンル選択肢）
# ======================================================================
def _get_genre_list(user_id: int, current_genre: str | None = None) -> list[str]:
    """
    投稿フォームのジャンル選択肢リストを生成する。

    プリセット（DEFAULT_GENRES）とユーザーが過去に使ったジャンルの和集合を作り、
    プリセット順 → 独自ジャンル辞書順で安定して並べて返す。

    @param user_id: 現在ログイン中のユーザー ID
    @param current_genre: 編集中の記事のジャンル名（update 時のみ指定）
    @return: ジャンル名のソート済みリスト
    """
    # ユーザーが過去に使ったジャンル名を DB から取得（重複なし）
    existing = (
        db.session.query(Post.genre)
        .filter(Post.user_id == user_id,
                Post.genre != '未分類',
                Post.genre != None,
                Post.genre != '')
        .distinct()
        .all()
    )
    user_genres_list = [g[0] for g in existing]

    # プリセット + ユーザー既存ジャンルの和集合を作成
    all_genres_set = set(DEFAULT_GENRES) | set(user_genres_list)

    # 編集中の記事のジャンルが選択肢にない場合も追加（データの整合性を保つ）
    if current_genre:
        all_genres_set.add(current_genre)

    # '未分類' は select の先頭に固定で置くので除外
    all_genres_set.discard('未分類')

    # 並べ替えて返す（プリセット順 → 独自ジャンル辞書順）
    return sorted(
        list(all_genres_set),
        key=lambda x: (0, DEFAULT_GENRES.index(x)) if x in DEFAULT_GENRES else (1, x)
    )


# ======================================================================
# [3] 新規投稿
# ======================================================================

@admin_bp.route('/create', methods=['GET', 'POST'])
@login_required  # 未ログイン時は app.py の unauthorized_handler により 404 を返す
def create():
    """
    新規記事の投稿フォーム表示（GET）と保存処理（POST）を行う。

    【処理の流れ】
      STEP 1. 管理者チェック（管理者以外はトップへ）
      STEP 2. [POST] フォーム入力値を取得・バリデーション
      STEP 3. [POST] ジャンル・デフォルトサムネイルを決定
      STEP 4. [POST] 本文画像を検証・最適化保存（失敗時はフラッシュしてリダイレクト）
      STEP 4.5. [POST] サムネイル専用画像を検証・最適化保存
      STEP 4.7. [POST] 本文 HTML・目次 HTML を事前生成（詳細表示の再変換を防ぐ）
      STEP 5. [POST] Post オブジェクトを作成してセッションに追加
      STEP 6. [POST] flush() で post.id を確定 → ハッシュタグを同期
      STEP 7. [POST] commit（失敗時は rollback + 保存済み画像を掃除 + ログ記録）
      STEP 8. [GET]  ジャンル選択肢を生成して投稿フォームを表示
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    if request.method == 'POST':
        # --------------------------------------------------------------
        # STEP 2. フォーム入力値の取得とバリデーション
        # --------------------------------------------------------------
        title          = request.form.get('title', '').strip()
        body           = request.form.get('body', '').strip()
        selected_genre = request.form.get('genre_select')           # プリセットから選択したジャンル
        new_genre      = request.form.get('genre_new', '').strip()  # 新規入力したジャンル名
        hashtag_input  = request.form.get('hashtag_input', '')

        if not title or not body:
            flash('タイトルと内容はどちらも入力必須です。', 'danger')
            return redirect('/create')

        # --------------------------------------------------------------
        # STEP 3. ジャンル・デフォルトサムネイルの決定
        # --------------------------------------------------------------
        # ジャンルの優先順位: 新規入力 > プリセット選択 > デフォルト（未分類）
        final_genre = new_genre if new_genre else (selected_genre or '未分類')

        # デフォルトサムネイル: フォームで 'none' が選ばれた場合は NULL
        selected_default_thumb = request.form.get('default_thumb_select')
        if selected_default_thumb == 'none':
            selected_default_thumb = None

        # --------------------------------------------------------------
        # STEP 4. 本文画像の保存（検証 + 最適化）
        # --------------------------------------------------------------
        try:
            filename_list = save_images(request.files.getlist('img[]'))
        except ValueError as e:
            # 検証エラーの詳細は services.images 側（validate_image /
            # _optimize_body_image_save）が記録済みのため、ここでは再度
            # ログを出さずユーザーへ通知するだけにする。
            flash(str(e), 'danger')
            return redirect('/create')

        # ファイル名をカンマ区切りで 1 つの文字列に結合して DB に保存
        img_name_str = ','.join(filename_list) if filename_list else None

        # キャプションをタブ区切りで 1 つの文字列に結合
        captions         = parse_img_captions(len(filename_list))
        img_captions_str = '\t'.join(captions) if captions else None

        # --------------------------------------------------------------
        # STEP 4.5. サムネイル専用画像の保存（検証 + WebP 縮小）
        # --------------------------------------------------------------
        try:
            thumbnail_name = save_thumbnail(request.files.get('thumbnail_img'))
        except ValueError as e:
            if img_name_str:
                delete_images(img_name_str)
            flash(str(e), 'danger')
            return redirect('/create')

        # 公開設定: hidden フィールド is_published の値が 'true' なら True
        is_published = request.form.get('is_published') == 'true'

        # --------------------------------------------------------------
        # STEP 4.7. 本文 HTML・目次 HTML を事前生成
        # --------------------------------------------------------------
        # 本文・画像（img_name / img_captions）が確定した後に生成する。
        # これにより [imgN] 置換なども含めた最終形をキャッシュでき、
        # 詳細表示（detail）ではこれをそのまま出力するだけになる。
        body_html, toc_html = render_post_body(body, img_name_str, img_captions_str)

        # --------------------------------------------------------------
        # STEP 5. Post オブジェクトを作成してセッションに追加
        # --------------------------------------------------------------
        # updated_at は新規投稿時 NULL のまま（「まだ更新されていない」を明示）。
        # render_version には「この HTML を生成したレンダラのバージョン」を
        # 記録する。rendering.py を変更して RENDER_VERSION を上げると、
        # この記事は detail() 側で自動的に再生成される。
        post = Post(
            title          = title,
            body           = body,
            body_html      = body_html,
            toc_html       = toc_html,
            render_version = RENDER_VERSION,
            user_id        = current_user.id,
            img_name       = img_name_str,
            default_thumb  = selected_default_thumb,
            thumbnail_img  = thumbnail_name,
            genre          = final_genre,
            is_published   = is_published,
            img_captions   = img_captions_str,
            updated_at     = None,
        )
        db.session.add(post)

        # --------------------------------------------------------------
        # STEP 6. flush で ID を確定してハッシュタグを同期
        # --------------------------------------------------------------
        db.session.flush()

        # ハッシュタグの同期
        sync_hashtags(post, parse_hashtag_input(hashtag_input))

        # --------------------------------------------------------------
        # STEP 7. commit（失敗時は rollback + 保存済み画像を掃除）
        # --------------------------------------------------------------
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            # 制約違反・接続断・カラム長超過など原因は多岐にわたるため、
            # 記事を特定できるようタイトルとユーザー ID を添えて記録する。
            current_app.logger.exception(
                '記事の保存に失敗しました (user_id=%s, title=%r, images=%s)',
                current_user.id, title, img_name_str
            )
            if img_name_str:
                delete_images(img_name_str)
            if thumbnail_name:
                delete_images(thumbnail_name)
            flash('投稿の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
            return redirect('/create')

        current_app.logger.info(
            '記事を新規投稿しました (post_id=%s, user_id=%s, published=%s)',
            post.id, current_user.id, is_published
        )
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 8. GET: 投稿フォームを表示
    # ------------------------------------------------------------------
    genres = _get_genre_list(current_user.id)
    return render_template('create.html', genres=genres)


# ======================================================================
# [4] 記事編集
# ======================================================================

@admin_bp.route('/<int:id>/update', methods=['GET', 'POST'])
@login_required
def update(id):
    """
    記事の編集フォーム表示（GET）と更新処理（POST）を行う。

    【処理の流れ】
      STEP 1. 管理者チェック + 記事の取得・権限チェック
      STEP 2. [GET]  既存データ（ジャンル・タグ・キャプション）を整えてフォーム表示
      STEP 3. [POST] タイトル・本文のバリデーションと基本項目の更新
      STEP 4. [POST] ハッシュタグの同期 + 孤立タグの削除予約
      STEP 5. [POST] 本文画像の更新（3 パターン: A 差し替え / B 個別削除 / C キャプションのみ）
      STEP 5.5. [POST] サムネイル専用画像の更新（差し替え / 削除 / 維持）
      STEP 5.7. [POST] 本文・画像の確定後に本文 HTML・目次 HTML を再生成
      STEP 6. [POST] 更新日時をセットして commit（失敗時はログ記録 + 掃除）
      STEP 7. [POST] commit 成功後に削除対象の旧ファイルを物理削除
      STEP 8. [POST] 記事詳細ページへリダイレクト
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック + 記事の取得・権限チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. GET: 編集フォームの初期値を設定して表示
    # ------------------------------------------------------------------
    if request.method == 'GET':
        genres = _get_genre_list(current_user.id, post.genre)

        # 既存ハッシュタグを "#Flask #Python" 形式の文字列に変換
        existing_hashtag_str = ' '.join(f'#{t.name}' for t in post.hashtags)

        # 既存キャプションをタブ区切りから配列に変換
        existing_captions = post.img_captions.split('\t') if post.img_captions else []

        return render_template('update.html', post=post, genres=genres,
                               existing_hashtag_str=existing_hashtag_str,
                               existing_captions=existing_captions)

    # ------------------------------------------------------------------
    # STEP 3. POST: バリデーションと基本項目の更新
    # ------------------------------------------------------------------
    # (3-1) タイトル・本文
    title = request.form.get('title', '').strip()
    body  = request.form.get('body', '').strip()
    if not title or not body:
        flash('タイトルと内容はどちらも入力必須です。', 'danger')
        return redirect(f'/{id}/update')

    post.title = title
    post.body  = body

    # (3-2) デフォルトサムネイルの更新
    selected_default_thumb = request.form.get('default_thumb_select')
    post.default_thumb = None if selected_default_thumb == 'none' else selected_default_thumb

    # (3-3) 公開設定の更新
    is_published_form = request.form.get('is_published')
    if is_published_form is not None:
        post.is_published = (is_published_form == 'true')

    # (3-4) ジャンルの更新
    new_genre      = request.form.get('genre_new', '').strip()
    selected_genre = request.form.get('genre_select')
    post.genre = new_genre if new_genre else (selected_genre or '未分類')

    # ------------------------------------------------------------------
    # STEP 4. ハッシュタグの同期 + 孤立タグの削除予約
    # ------------------------------------------------------------------
    sync_hashtags(post, parse_hashtag_input(request.form.get('hashtag_input', '')))
    delete_orphaned_hashtags()

    # ------------------------------------------------------------------
    # STEP 5. 本文画像の更新
    # ------------------------------------------------------------------
    # 3 つのパターンを扱う:
    #   A) 新しい画像が選択された          → 全画像を新画像で差し替え
    #   B) 新画像なし + 個別削除フラグあり → 指定された既存画像だけを削除
    #   C) 新画像なし + 削除フラグなし     → キャプションのみ更新
    files = request.files.getlist('img[]')
    old_img_name  = None   # commit 成功後に物理削除する画像
    new_filenames = []     # commit 失敗時に掃除する新規保存ファイル

    if files and files[0].filename != '':
        # --------------------------------------------------------------
        # (5-A) パターン A: 画像の全差し替え（検証 + 最適化保存）
        # --------------------------------------------------------------
        try:
            new_filenames = save_images(files)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(f'/{id}/update')

        old_img_name  = post.img_name           # 旧画像名を退避（commit 後に削除）
        post.img_name = ','.join(new_filenames)
        captions = parse_img_captions(len(new_filenames), prefix='new_img_caption_')
        post.img_captions = '\t'.join(captions) if captions else None

    elif post.img_name:
        # --------------------------------------------------------------
        # (5-B/C) パターン B / C: 既存画像の個別削除 + キャプション更新
        # --------------------------------------------------------------
        existing_imgs = post.img_name.split(',')
        kept_imgs     = []   # 残す画像ファイル名
        kept_captions = []   # 残す画像のキャプション
        removed_imgs  = []   # 削除予定の画像ファイル名

        for i, img in enumerate(existing_imgs, start=1):
            caption = request.form.get(f'img_caption_{i}', '').replace('\t', ' ').strip()

            # keep_img_N が '0' なら削除予定。
            # 送られてこない場合はデフォルト '1'（残す）扱い（安全側・後方互換）。
            if request.form.get(f'keep_img_{i}', '1') == '0':
                removed_imgs.append(img)
            else:
                kept_imgs.append(img)
                kept_captions.append(caption)

        if removed_imgs:
            # 削除対象を commit 成功後の物理削除キューに積む
            old_img_name = ','.join(removed_imgs)

        # 残った画像だけで DB 上の参照を再構築する。
        post.img_name     = ','.join(kept_imgs) if kept_imgs else None
        post.img_captions = '\t'.join(kept_captions) if kept_imgs else None

    # ------------------------------------------------------------------
    # STEP 5.5. サムネイル専用画像の更新
    # ------------------------------------------------------------------
    old_thumbnail_name  = None   # commit 成功後に物理削除する旧サムネイル
    new_thumbnail_saved = None   # commit 失敗時に掃除する新規保存サムネイル

    thumb_file = request.files.get('thumbnail_img')
    if thumb_file and thumb_file.filename != '':
        # --- サムネイルの差し替え（検証 + WebP 縮小） ---
        try:
            new_thumbnail_saved = save_thumbnail(thumb_file)
        except ValueError as e:
            # 本文画像で今回新規保存したものがあれば掃除してから戻る
            if new_filenames:
                delete_images(','.join(new_filenames))
            flash(str(e), 'danger')
            return redirect(f'/{id}/update')

        old_thumbnail_name = post.thumbnail_img   # 旧サムネイルを退避（commit 後に削除）
        post.thumbnail_img = new_thumbnail_saved

    elif request.form.get('keep_thumbnail', '1') == '0':
        # --- 現在のサムネイルを削除 ---
        old_thumbnail_name = post.thumbnail_img
        post.thumbnail_img = None

    # ------------------------------------------------------------------
    # STEP 5.7. 本文 HTML・目次 HTML の再生成
    # ------------------------------------------------------------------
    # 本文（post.body）と画像（post.img_name / post.img_captions）が
    # すべて確定した後に再生成し、キャッシュ列を更新する。
    # これにより次回以降の詳細表示は再変換なしで済む。
    #
    # 生成に使ったレンダラのバージョンも一緒に更新する
    # （古いバージョンで作られた記事を編集した場合、ここで最新版に揃う）。
    post.body_html, post.toc_html = render_post_body(
        post.body, post.img_name, post.img_captions
    )
    post.render_version = RENDER_VERSION

    # ------------------------------------------------------------------
    # STEP 6. 更新日時をセットして commit
    # ------------------------------------------------------------------
    post.updated_at = datetime.now(pytz.timezone('Asia/Tokyo'))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # 更新失敗の記録。どの記事の更新が落ちたかを追えるよう post_id を含める。
        current_app.logger.exception(
            '記事の更新に失敗しました (post_id=%s, user_id=%s, title=%r)',
            id, current_user.id, title
        )
        # commit 失敗 → 今回新規保存したファイルを掃除（DB は旧状態のまま無傷）
        if new_filenames:
            delete_images(','.join(new_filenames))
        if new_thumbnail_saved:
            delete_images(new_thumbnail_saved)
        flash('更新の保存中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect(f'/{id}/update')

    # ------------------------------------------------------------------
    # STEP 7. commit 成功 → ここで初めて削除対象のファイルを物理削除する
    # ------------------------------------------------------------------
    if old_img_name:
        delete_images(old_img_name)
    if old_thumbnail_name:
        delete_images(old_thumbnail_name)

    current_app.logger.info(
        '記事を更新しました (post_id=%s, user_id=%s)', id, current_user.id
    )

    # ------------------------------------------------------------------
    # STEP 8. 記事詳細ページへリダイレクト
    # ------------------------------------------------------------------
    return redirect(f'/{id}/detail')


# ======================================================================
# [5] 記事削除
# ======================================================================

@admin_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """
    記事を削除する（POST のみ受付）。
    URL を直接叩いただけでは削除できない（CSRF トークンも必要）。
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック + 記事の取得・権限チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    post = db.session.get(Post, id)
    if not post or post.user_id != current_user.id:
        flash("指定された記事が見つからないか、アクセス権限がありません。", 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. 削除対象の画像名を退避（本文画像 + サムネイル）
    # ------------------------------------------------------------------
    # 物理削除は DB commit 成功後に行う（不整合防止）。
    files_to_delete = []
    if post.img_name:
        files_to_delete.append(post.img_name)
    if post.thumbnail_img:
        files_to_delete.append(post.thumbnail_img)
    img_name_to_delete = ','.join(files_to_delete) if files_to_delete else None

    # 削除後はログに出せなくなるので、タイトルをここで控えておく
    deleted_title = post.title

    # ------------------------------------------------------------------
    # STEP 3. ハッシュタグのリレーションをクリア + 孤立タグの削除予約
    # ------------------------------------------------------------------
    post.hashtags = []
    db.session.flush()  # 中間テーブルの削除を反映させてから孤立判定する

    delete_orphaned_hashtags()

    # ------------------------------------------------------------------
    # STEP 4. 記事を削除予約して commit
    # ------------------------------------------------------------------
    db.session.delete(post)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # 削除失敗の記録。外部キー制約などで落ちた場合の調査に必要。
        current_app.logger.exception(
            '記事の削除に失敗しました (post_id=%s, user_id=%s, title=%r)',
            id, current_user.id, deleted_title
        )
        flash('削除中にエラーが発生しました。もう一度お試しください。', 'danger')
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 5. commit 成功 → ここで初めて関連画像ファイルを物理削除する
    # ------------------------------------------------------------------
    delete_images(img_name_to_delete)

    current_app.logger.info(
        '記事を削除しました (post_id=%s, user_id=%s, title=%r)',
        id, current_user.id, deleted_title
    )

    # ------------------------------------------------------------------
    # STEP 6. 削除後のリダイレクト先決定（Open Redirect 対策）
    # ------------------------------------------------------------------
    referrer = request.referrer
    if referrer:
        parsed_ref = urlparse(referrer)
        parsed_req = urlparse(request.url)
        same_origin = (
            parsed_ref.scheme == parsed_req.scheme and
            parsed_ref.netloc == parsed_req.netloc
        )
        if same_origin:
            return redirect(referrer)

    return redirect('/')  # referer がない or 別オリジンならトップへ


# ======================================================================
# [6] マイページ
# ======================================================================

@admin_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    """
    マイページの表示（GET）とニックネーム変更（POST）を行う。

    自分の投稿は index と同じくサーバーサイドページネーション（1 ページ
    POSTS_PER_PAGE 件）で取得し、selectinload(Post.hashtags) で N+1 を防ぐ。
    総投稿数は pagination.total（全件数）を total_count として渡す。

    【処理の流れ】
      STEP 1. 管理者チェック
      STEP 2. [POST] ニックネームを更新して commit → マイページへリダイレクト
      STEP 3. [GET]  自分の記事をページネーションで取得（selectinload 付き）
      STEP 4. [GET]  使用ジャンル一覧を生成（'未分類' は末尾へ）
      STEP 5. [GET]  mypage.html をレンダリング
    """
    # ------------------------------------------------------------------
    # STEP 1. 管理者チェック
    # ------------------------------------------------------------------
    if current_user.username != config.ADMIN_USERNAME:
        return redirect('/')

    # ------------------------------------------------------------------
    # STEP 2. POST: ニックネーム変更処理
    # ------------------------------------------------------------------
    if request.method == 'POST':
        new_nickname = request.form.get('nickname', '').strip()
        # 空欄の場合は None にして「ニックネームなし」に戻す
        current_user.nickname = new_nickname or None

        # commit が失敗したら rollback し、他のビューと同じく原因をログに残して
        # ユーザーへ通知する。
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                'ニックネームの更新に失敗しました (user_id=%s, nickname=%r)',
                current_user.id, new_nickname
            )
            flash('ニックネームの更新中にエラーが発生しました。もう一度お試しください。', 'danger')
            return redirect('/mypage')

        flash('ニックネームを更新しました！' if new_nickname else 'ニックネームを解除しました。', 'info')
        return redirect('/mypage')

    # ------------------------------------------------------------------
    # STEP 3. GET: 自分の記事をサーバーサイドページネーションで取得
    # ------------------------------------------------------------------
    # 記事カードがハッシュタグバッジを表示するため、selectinload で
    # 一括先読みして N+1 を防ぐ（先読みの指定はこの options に置いている）。
    page = request.args.get('page', 1, type=int)
    pagination = (
        Post.query
        .filter(Post.user_id == current_user.id)
        .options(db.selectinload(Post.hashtags))
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=POSTS_PER_PAGE, error_out=False)
    )
    user_posts = pagination.items  # 現在ページ分の記事だけ

    # ------------------------------------------------------------------
    # STEP 4. 使用ジャンル一覧の生成（サイドバー表示用）
    # ------------------------------------------------------------------
    user_genres_raw = (
        db.session.query(Post.genre)
        .filter(Post.user_id == current_user.id,
                Post.genre != None,
                Post.genre != '')
        .distinct()
        .all()
    )
    # 重複除去 + ソート（'未分類' を除いたもの）
    user_genres = sorted({g[0] for g in user_genres_raw if g[0] != '未分類'})
    # '未分類' が存在する場合のみ末尾に追加
    if any(g[0] == '未分類' for g in user_genres_raw):
        user_genres.append('未分類')

    # ------------------------------------------------------------------
    # STEP 5. テンプレートのレンダリング
    # ------------------------------------------------------------------
    return render_template(
        'mypage.html',
        posts       = user_posts,       # 現在ページ分の記事
        pagination  = pagination,       # ページ送りナビ生成用
        total_count = pagination.total, # 「総投稿数」表示用（全件数）
        user_genres = user_genres,
    )