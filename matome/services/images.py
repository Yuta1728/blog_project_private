# ======================================================================
# services/images.py — 画像の検証・最適化・保存・削除（ドメインロジック層）
# ======================================================================
#
# 【役割】
#   アップロード画像に関する処理をまとめたサービスモジュール。
#   従来 views/admin.py に直書きされていた画像ヘルパー群をここへ移し、
#   ビューは「HTTP の入出力」に専念できるようにした。
#
# 【重いライブラリ（Pillow / filetype）を「関数の中」で import する理由】
#   Pillow（PIL）は読み込みコストの大きいライブラリで、モジュールの
#   トップレベルで import すると「その import を含むモジュールが読まれた
#   瞬間」にメモリへ展開される。
#
#   ビュー（views/admin.py）は全 Blueprint 登録の一環としてアプリ起動時に
#   必ず import されるため、画像処理ヘルパーがビューに同居していると、
#   「閲覧しかしないワーカー」でも起動時に Pillow を丸ごと抱えてしまう。
#   個人ブログは投稿よりも閲覧が大多数のため、これは無駄が大きい。
#
#   このモジュールでは Pillow / filetype の import を「実際に画像を処理する
#   関数の内側」へ置いた。これにより
#     ・アプリ起動時（import 時）には Pillow / filetype を読み込まない
#     ・画像がアップロードされたリクエストで初めて読み込む
#   となり、起動時間とベースメモリ（無料枠で効く）を節約できる。
#
#   標準ライブラリの os / uuid、および current_app は軽量なので、
#   トップレベルで import している。
#
# 【このファイルの構成（目次）】
#   [1] 定数（拡張子・MIME ホワイトリスト / 画像最適化パラメータ）
#   [2] _resample()                : Pillow のリサンプリング定数を遅延解決
#   [3] allowed_file()             : 拡張子チェック
#   [4] validate_image()           : 拡張子 + MIME の多層検証
#   [5] _optimize_body_image_save(): 本文画像を Pillow で縮小・再圧縮して保存
#   [6] save_images()              : 検証 + 最適化保存（アトミック保証）
#   [7] delete_images()            : 実ファイルの物理削除
#   [8] save_thumbnail()           : サムネイル専用画像を WebP 縮小版で保存
#
# 【公開 API（views/admin.py から呼ぶ関数）】
#   save_images / delete_images / save_thumbnail
#   （validate_image / allowed_file はテスト等からも使える公開ユーティリティ）
# ======================================================================

import os
import uuid
from flask import current_app


# ======================================================================
# [1] 定数: アップロード検証用ホワイトリスト + 画像最適化パラメータ
# ======================================================================

# 拡張子チェック（第 1 層の防御）: ファイル名の末尾を確認
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# MIME タイプチェック（第 2 層の防御）: ファイルの先頭バイトを読んで実際の形式を確認
# 拡張子を偽装した悪意あるファイル（例: malware.exe を image.jpg にリネーム）を弾く
ALLOWED_MIME_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}

# ---- 画像最適化パラメータ --------------------------------------------
# 本文画像: 長辺がこの値（px）を超える場合のみ、この値まで縮小する（拡大はしない）
#
# 本文画像は 1 サイズしか配信しないため、スマホでも同じ画像を読み込む。
# 記事本文の最大表示幅は detail.css の .detail-container（max-width: 860px）と
# 左右パディングから実質 740px 程度で、高精細ディスプレイ（2 倍解像度）を
# 考慮しても 1200px あれば足りる。上限を大きくしすぎると、モバイル回線で
# 転送量が無駄に増えて体感速度に響く。
#
# ※ この値を変えても、既にアップロード済みの画像は縮小し直されない
#   （次回アップロードする画像から適用される）。
BODY_IMAGE_MAX_EDGE = 1200
# サムネイル専用画像: 幅がこの値（px）を超える場合のみ、この幅まで縮小して WebP 化する
THUMBNAIL_MAX_WIDTH = 400
# 再エンコード時の品質（0〜100。大きいほど高画質・大サイズ）
JPEG_QUALITY       = 85
WEBP_QUALITY_BODY  = 82
WEBP_QUALITY_THUMB = 80


# ======================================================================
# [2] Pillow のリサンプリング定数を遅延解決してキャッシュ
# ======================================================================
# Pillow を import した瞬間にモジュールが重くなるため、リサンプリング定数の
# 解決も「実際に画像を処理する時」まで遅らせる。初回呼び出し時に一度だけ
# PIL を読んで値を決定し、以降はキャッシュした値を返す。
#
# Pillow 9.1 以降は Image.Resampling 名前空間、それ以前はトップレベル定数。
_RESAMPLE = None


def _resample():
    """Pillow の高品質リサンプリング定数（LANCZOS）を遅延解決して返す。"""
    global _RESAMPLE
    if _RESAMPLE is None:
        from PIL import Image
        try:
            _RESAMPLE = Image.Resampling.LANCZOS
        except AttributeError:  # Pillow < 9.1 用のフォールバック
            _RESAMPLE = Image.LANCZOS
    return _RESAMPLE


# ======================================================================
# [3] 拡張子チェック
# ======================================================================
def allowed_file(filename: str) -> bool:
    """
    ファイル名の拡張子がホワイトリストに含まれているかチェックする。
    '.' を含み、かつ最後の '.' 以降が許可リストにあれば True を返す。
    （例: 'photo.jpg' → True, 'script.php' → False）
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ======================================================================
# [4] 拡張子 + MIME の多層検証
# ======================================================================
def validate_image(file) -> None:
    """
    アップロードされた 1 ファイルを検証する（多層防御）。

    第 1 層: allowed_file() で拡張子チェック
    第 2 層: filetype.guess() で先頭バイトから MIME タイプを判定（拡張子偽装の検出）

    問題があれば ValueError を送出する。検証後はストリーム位置を先頭へ戻すので、
    続けて Pillow の Image.open() / file.save() が読み込める状態になる。

    検証で弾いた事実は warning として記録する。多くはユーザーの操作ミス
    （対応外の形式を選んだ）だが、偽装ファイルのアップロードが繰り返される
    場合に攻撃の兆候として検知できるようにするため。
    """
    # 第 1 層: 拡張子
    if not allowed_file(file.filename):
        current_app.logger.warning(
            '許可されていない拡張子のアップロードを拒否しました (filename=%r)', file.filename
        )
        raise ValueError('許可されていない拡張子が含まれています。(PNG, JPG, GIF, WebP のみ)')

    # 第 2 層: 先頭バイトから MIME タイプを判定
    header = file.stream.read(2048)
    file.stream.seek(0)  # ストリーム位置をリセット（後続の読み込みに備える）

    # filetype は画像アップロード時にしか使わないため、ここで遅延 import する
    # （アプリ起動時にはロードしない）。
    import filetype
    kind = filetype.guess(header)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        current_app.logger.warning(
            '内容が画像でないファイルのアップロードを拒否しました '
            '(filename=%r, detected_mime=%s)',
            file.filename, kind.mime if kind else 'unknown'
        )
        raise ValueError('ファイルの内容が不正です。画像偽装の可能性があります。')


# ======================================================================
# [5] 本文画像を Pillow で最適化して保存
# ======================================================================
def _optimize_body_image_save(file, save_path: str, ext: str) -> None:
    """
    本文画像 1 枚を Pillow で最適化し、save_path に保存する。

    最適化の内容:
      ・EXIF の向き情報を画素に反映（スマホ写真の回転ズレ対策）
      ・長辺が BODY_IMAGE_MAX_EDGE を超える場合のみ、その値まで縮小
      ・元の形式を尊重して再エンコード（JPEG は品質指定、PNG/WebP は最適化）
      ・アニメーション GIF は劣化・静止化を避けるため原本をそのまま保存

    @param file:      werkzeug の FileStorage（検証済み）
    @param save_path: 保存先の絶対パス
    @param ext:       小文字の拡張子（'.jpg' など）
    @raises ValueError: 画像処理に失敗した場合
    """
    # Pillow は実際に画像を変換する時だけ読み込む（アプリ起動時にはロードしない）。
    # import 自体の失敗（未インストール等）は下の except で握り潰さず表面化させたいため、
    # try の外に置く。
    from PIL import Image, ImageOps

    ext = ext.lower()
    try:
        img = Image.open(file.stream)

        # アニメーション GIF は原本を保存してフレーム・ループを保持する
        if getattr(img, 'is_animated', False):
            file.stream.seek(0)
            file.save(save_path)
            return

        # 撮影時の回転情報を画素に焼き込む（未指定の画像では実質何もしない）
        img = ImageOps.exif_transpose(img)

        # 長辺を上限まで縮小（超えていなければそのまま）
        img.thumbnail((BODY_IMAGE_MAX_EDGE, BODY_IMAGE_MAX_EDGE), _resample())

        # 形式ごとに再エンコード
        if ext in ('.jpg', '.jpeg'):
            img = img.convert('RGB')  # JPEG は透過を持てないため RGB 化
            img.save(save_path, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif ext == '.png':
            img.save(save_path, 'PNG', optimize=True)   # 透過（RGBA/P）を保持
        elif ext == '.webp':
            img.save(save_path, 'WEBP', quality=WEBP_QUALITY_BODY, method=6)
        elif ext == '.gif':
            img.save(save_path, 'GIF')                  # 静止 GIF
        else:
            img.save(save_path)
    except ValueError:
        # 既に ValueError のものはそのまま上位へ
        raise
    except Exception:
        # Pillow 由来の各種例外（壊れた画像・巨大画像など）は
        # ユーザー向けの ValueError に正規化する。
        # ただし正規化するとユーザーには「別の画像でお試しください」としか
        # 出ないため、原因（どの形式のどんな画像で Pillow が何を投げたか）を
        # 追えるよう、ここでトレースバックを記録しておく。
        current_app.logger.exception(
            '本文画像の変換に失敗しました (filename=%r, ext=%s, save_path=%s)',
            getattr(file, 'filename', None), ext, save_path
        )
        raise ValueError('画像の処理中にエラーが発生しました。別の画像でお試しください。')


# ======================================================================
# [6] 検証 + 最適化保存（アトミック保証）
# ======================================================================
def save_images(files: list) -> list[str]:
    """
    アップロードされた本文画像を検証・最適化・保存し、
    保存したファイル名のリストを返す。

    途中でエラーが出た場合はそれまでに保存したファイルを掃除してから
    例外を再送出する（全成功のときだけファイルを残す）。

    @param files: request.files.getlist('img[]') のファイルオブジェクトのリスト
    @return: 保存したファイル名のリスト
    @raises ValueError: 検証エラー・画像処理エラー時
    """
    filename_list = []

    try:
        for file in files:
            # ファイルが選択されていない場合はスキップ
            if not file or file.filename == '':
                continue

            # 拡張子 + MIME 検証（失敗時は ValueError）
            validate_image(file)

            # 拡張子は検証済みの元ファイル名から直接取得する
            ext = '.' + file.filename.rsplit('.', 1)[1].lower()

            # UUID でファイル名をランダム化し、掃除対象へ先行登録
            filename  = f"{uuid.uuid4()}{ext}"
            filename_list.append(filename)
            save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)

            # 縮小・再圧縮して保存
            _optimize_body_image_save(file, save_path, ext)

    except Exception:
        # 途中まで保存したファイルをここで掃除する。
        # 「何枚保存した時点で中断し、何を消したか」を記録しておくと、
        # ディスク上のファイルと DB の食い違いを追うときの手がかりになる。
        # 例外そのものの詳細は送出元（validate_image / _optimize_body_image_save）で
        # 既に記録済みのため、ここでは後始末の事実だけを warning で残す。
        if filename_list:
            current_app.logger.warning(
                '本文画像の保存が中断されたため、保存済みの %d 件を削除します: %s',
                len(filename_list), ','.join(filename_list)
            )
            delete_images(','.join(filename_list))
        raise

    # 全成功: 保存したファイル名のリストを返す
    return filename_list


# ======================================================================
# [7] 実ファイルの物理削除
# ======================================================================
def delete_images(img_name_str: str) -> None:
    """
    カンマ区切りファイル名をもとに static/img/posts/ 以下の実ファイルを物理削除する。
    必ず「DB の commit が成功した後」に呼ぶこと。

    【1 ファイルの削除失敗で全体を止めない】
    この関数は「DB の更新が成功した後の後片付け」として呼ばれる。
    削除に失敗しても DB 側の変更（記事の保存・削除）は既に確定しているため、
    巻き戻すべきではない。また複数ファイルを消すとき、1 件目の失敗で
    2 件目以降を止めると消し残しが増える。

    そこで 1 ファイルずつ try で囲み、失敗はログに残して次へ進む。
    消し残したファイル（孤児ファイル）はディスクを少し消費するだけで
    表示には影響しない（`flask clean-orphan-images` で一括掃除できる）。

    @param img_name_str: post.img_name の値（例: "uuid1.jpg,uuid2.png"）
    """
    if not img_name_str:
        return

    for img_file in img_name_str.split(','):
        img_path = os.path.join(current_app.static_folder, 'img', 'posts', img_file.strip())
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except OSError:
            # 削除できなくても処理は続行する（DB の状態は既に確定しているため）
            current_app.logger.exception(
                '画像ファイルの削除に失敗しました。孤児ファイルとして残ります (path=%s)',
                img_path
            )


# ======================================================================
# [8] サムネイル専用画像を WebP 縮小版で保存
# ======================================================================
def save_thumbnail(file) -> str | None:
    """
    サムネイル専用にアップロードされた 1 枚の画像を検証し、
    幅 THUMBNAIL_MAX_WIDTH の軽量な WebP に変換して保存する。
    保存したファイル名（.webp）を返す。ファイル未選択なら None。

    @param file: request.files.get('thumbnail_img') のファイルオブジェクト
    @return: 保存したファイル名（.webp。未選択なら None）
    @raises ValueError: 検証エラー・画像処理エラー時
    """
    if not file or file.filename == '':
        return None

    # 拡張子 + MIME 検証（失敗時は ValueError。ここではまだファイル未生成）
    validate_image(file)

    # Pillow は実際に変換する時だけ読み込む（ファイル未選択なら上で return 済み）。
    from PIL import Image, ImageOps

    filename  = f"{uuid.uuid4()}.webp"   # サムネイルは形式を WebP に統一
    save_path = os.path.join(current_app.static_folder, 'img', 'posts', filename)

    try:
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)

        # WebP は RGB / RGBA を扱えるため、透過を保持したまま変換する
        if img.mode in ('P', 'LA'):
            img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')

        # 幅が上限を超える場合のみ、アスペクト比を保って縮小（拡大しない）
        w, h = img.size
        if w > THUMBNAIL_MAX_WIDTH:
            new_h = max(1, round(h * THUMBNAIL_MAX_WIDTH / w))
            img = img.resize((THUMBNAIL_MAX_WIDTH, new_h), _resample())

        img.save(save_path, 'WEBP', quality=WEBP_QUALITY_THUMB, method=6)

    except ValueError:
        delete_images(filename)  # 半端なファイルがあれば掃除
        raise
    except Exception:
        # 本文画像と同じく、Pillow の例外を ValueError に丸める前に
        # トレースバックを残しておく。
        current_app.logger.exception(
            'サムネイル画像の変換に失敗しました (filename=%r, save_path=%s)',
            getattr(file, 'filename', None), save_path
        )
        delete_images(filename)
        raise ValueError('サムネイル画像の処理中にエラーが発生しました。別の画像でお試しください。')

    return filename