# ======================================================================
# rendering.py — 記事本文（Markdown + 独自タグ）→ HTML 変換の共通モジュール
# ======================================================================
#
# 【役割・追加の背景】
#   従来 views/blog.py の detail() は、記事本文（Markdown + 独自タグ）を
#   「アクセスのたびに」markdown.convert() で変換し、さらに
#   [imgN] / [map:] / [youtube:] の置換を毎回行っていた。
#   本文は投稿・編集時にしか変化しないため、閲覧ごとに同じ変換を
#   繰り返すのは無駄が大きい（improvement.md の項目 5）。
#
#   そこで「変換ロジック」をこのモジュールに切り出し、
#     ・投稿時（views/admin.py の create）
#     ・編集時（views/admin.py の update）
#   にだけ render_post_body() を呼んで結果を Post.body_html / Post.toc_html に
#   保存し、詳細表示（detail）は保存済み HTML をそのまま出力する。
#
#   変換に必要な入力は body / img_name / img_captions のみで、
#   リクエストやログイン状態に依存しないため、事前生成しても
#   detail() の出力は従来とまったく同じになる。
#
# 【このファイルの構成（目次）】
#   [1] render_post_body()       : 本文 → (body_html, toc_html) を生成（公開 API）
#   [2] 内部ヘルパー関数群
#        (2-1) _is_structural_line()  : 構造行（見出し等）の判定
#        (2-2) _expand_blank_lines()  : 連続空行の <br> 展開
#        (2-3) _replace_map()         : [map:] タグ → Google マップ iframe
#        (2-4) _extract_youtube_id()  : YouTube URL から動画 ID を抽出
#        (2-5) _replace_youtube()     : [youtube:] タグ → ファサード埋め込み
#
#   ※ (2-1)〜(2-5) は元々 views/blog.py に定義されていたものを、
#     ロジックを変えずにそのまま移設したもの。blog.py はこのモジュールを
#     import して利用する。
# ======================================================================

import re
import markdown
from urllib.parse import quote  # 地図 URL の正しいエンコードに使用
from markupsafe import escape   # HTML 直組み立て時のエスケープに使用


# ======================================================================
# [1] 公開 API: 本文 → (body_html, toc_html) を生成
# ======================================================================

def render_post_body(body: str, img_name: str | None = None,
                     img_captions: str | None = None) -> tuple[str, str | None]:
    """
    記事本文（Markdown + 独自タグ）を HTML へ変換し、
    (本文 HTML, 目次 HTML) のタプルを返す。

    返り値:
      body_html : Markdown 変換 + [imgN]/[map:]/[youtube:] 置換まで済ませた本文 HTML
      toc_html  : 記事冒頭に表示する目次 HTML。
                  本文中に [toc] マーカーがある場合は None
                  （その位置に目次が展開済みのため、冒頭には表示しない）。

    【この関数の入力は body / img_name / img_captions のみ】
    リクエストや current_user に依存しないため、投稿・編集時に一度だけ
    呼び出して結果を保存しておけば、詳細表示のたびに再変換する必要がない。

    【処理の流れ】
      STEP 1. 本文の連続空行を <br> に展開（_expand_blank_lines）
      STEP 2. Markdown → HTML 変換（toc / nl2br 拡張）
      STEP 3. [toc] マーカーがなければ記事冒頭用の目次 HTML を用意
      STEP 4. [imgN] タグを <img> / <figure> に置換（キャプションはエスケープ）
      STEP 5. 未使用の [imgN] タグを除去
      STEP 6. [map:] タグを Google マップ iframe に置換
      STEP 7. [youtube:] タグをファサード埋め込みに置換
      STEP 8. (body_html, toc_html) を返す
    """
    # ------------------------------------------------------------------
    # STEP 1. 本文の前処理（連続空行の展開）
    # ------------------------------------------------------------------
    body_content   = body or ''
    has_toc_marker = '[toc]' in body_content
    body_content   = _expand_blank_lines(body_content)

    # ------------------------------------------------------------------
    # STEP 2. Markdown → HTML 変換
    # ------------------------------------------------------------------
    md = markdown.Markdown(
        extensions=['toc', 'nl2br'],
        extension_configs={'toc': {'toc_depth': '2-3', 'marker': '[toc]'}}
    )
    display_body = md.convert(body_content)

    # ------------------------------------------------------------------
    # STEP 3. 目次の扱い
    # ------------------------------------------------------------------
    # 本文中に [toc] があれば変換時にその位置へ展開済みなので None、
    # なければ記事冒頭に表示するための目次 HTML を返す。
    toc_html = None if has_toc_marker else md.toc

    # ------------------------------------------------------------------
    # STEP 4. 画像タグの埋め込み（[img1], [img2] → <img> / <figure>）
    # ------------------------------------------------------------------
    # キャプションは display_body（| safe で出力される HTML）に直接連結される
    # ため、markupsafe.escape() で HTML 特殊文字を無害化してから埋め込む。
    if img_name:
        images   = img_name.split(',')
        captions = img_captions.split('\t') if img_captions else []

        for index, img_file in enumerate(images):
            img_file    = re.sub(r'[/\\]', '', img_file.strip())
            raw_caption = captions[index].strip() if index < len(captions) else ''
            caption     = escape(raw_caption)  # HTML 特殊文字（< > & " '）を無害化

            if caption:
                # キャプションあり → <figure> + <figcaption>
                img_tag = (
                    f'<figure class="post-figure">'
                    f'<img src="/static/img/posts/{img_file}" alt="{caption}" style="max-width:100%; height:auto;">'
                    f'<figcaption class="post-figcaption">{caption}</figcaption>'
                    f'</figure>'
                )
            else:
                # キャプションなし → 中央寄せの <img> のみ
                img_tag = (
                    f'<span style="display:block; text-align:center; margin: 15px 0;">'
                    f'<img src="/static/img/posts/{img_file}" style="max-width:100%; height:auto;">'
                    f'</span>'
                )

            display_body = display_body.replace(f'[img{index+1}]', img_tag)

    # ------------------------------------------------------------------
    # STEP 5. 未使用の [imgN] タグを除去
    # ------------------------------------------------------------------
    display_body = re.sub(r'<p>\[img\d+\]</p>\n?', '', display_body)
    display_body = re.sub(r'\[img\d+\]', '', display_body)

    # ------------------------------------------------------------------
    # STEP 6. 地図タグの変換（[map:場所名] → Google Maps iframe）
    # ------------------------------------------------------------------
    display_body = re.sub(r'\[map:([^\]]+)\]', _replace_map, display_body)

    # ------------------------------------------------------------------
    # STEP 7. YouTube タグの変換
    # ------------------------------------------------------------------
    display_body = re.sub(
        r'(?:<p>)?\[youtube:([^\]]+)\](?:</p>)?',
        _replace_youtube,
        display_body
    )

    # ------------------------------------------------------------------
    # STEP 8. 生成結果を返す
    # ------------------------------------------------------------------
    return display_body, toc_html


# ======================================================================
# [2] 内部ヘルパー関数群（views/blog.py から移設・ロジック不変）
# ======================================================================

# ----------------------------------------------------------------------
# (2-1) 構造行の判定
# ----------------------------------------------------------------------
def _is_structural_line(s: str) -> bool:
    """
    Markdown の「構造行」（空行展開の対象外にすべき行）かどうかを判定する。

    構造行 = 見出し（#）・コードブロック（```）・目次マーカー（[toc]）。
    これらの直前直後の空行は Markdown の構文上の意味を持つため、
    _expand_blank_lines() で <br> に置き換えてはいけない。
    """
    stripped = s.strip()
    return (
        stripped.startswith('#') or
        stripped.startswith('```') or
        stripped == '[toc]'
    )


# ----------------------------------------------------------------------
# (2-2) 連続空行の <br> 展開
# ----------------------------------------------------------------------
def _expand_blank_lines(text: str) -> str:
    """
    本文中の「2 行以上の連続空行」を <br> に展開する。

    通常の Markdown では空行を何行連ねても段落区切り 1 つに潰されるが、
    ブログでは「意図的に行間を空ける」表現ができるようにしたい。
    そこで連続空行の 2 行目以降を <br> に置き換えて行間を保持する。

    【処理の流れ】
      STEP 1. 本文を行単位に分割し、先頭から走査
      STEP 2. 空行の連続をまとめてカウント
      STEP 3. 前後が構造行（見出し等）or 空行 1 行だけなら、そのまま維持
      STEP 4. それ以外は「空行 1 行 + <br> ×（連続数 - 1）」に変換
      STEP 5. 行を結合して返す
    """
    lines  = text.split('\n')
    result = []
    i      = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == '':
            blank_count = 0
            while i < len(lines) and lines[i].strip() == '':
                blank_count += 1
                i += 1

            prev_line = result[-1] if result else ''
            next_line = lines[i] if i < len(lines) else ''

            if (_is_structural_line(prev_line) or
                    _is_structural_line(next_line) or
                    blank_count == 1):
                result.extend([''] * blank_count)
            else:
                result.append('')
                result.extend(['<br>'] * (blank_count - 1))
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


# ----------------------------------------------------------------------
# (2-3) 地図タグの変換
# ----------------------------------------------------------------------
def _replace_map(m: re.Match) -> str:
    """
    [map:場所名] を Google Maps の iframe 埋め込みに変換する。

    ラベル表示用の場所名は escape()、iframe の src に埋め込む URL は
    quote() でそれぞれ用途別にエンコードし、属性値の突き破りや
    クエリパラメータ注入を防ぐ。
    """
    place = m.group(1).strip()

    place_label = escape(place)          # HTML 出力用（ラベル・表示テキスト）
    encoded     = quote(place, safe='')  # URL クエリ用（すべての予約文字をエンコード）

    return (
        f'<div class="post-map-wrapper">'
        f'<div class="post-map-label">📍 {place_label}</div>'
        f'<iframe class="post-map-iframe"'
        f' src="https://maps.google.com/maps?q={encoded}&output=embed&hl=ja"'
        f' loading="lazy" allowfullscreen></iframe>'
        f'</div>'
    )


# ----------------------------------------------------------------------
# (2-4) YouTube 動画 ID の抽出
# ----------------------------------------------------------------------
def _extract_youtube_id(raw: str) -> str | None:
    """
    YouTube の URL / 動画 ID 文字列から 11 文字の動画 ID を抽出する。

    対応形式（順に判定し、最初にマッチしたものを返す）:
      通常 URL / 短縮 URL / ショート / 埋め込み URL / 動画 ID 単体
    どれにも該当しなければ None。
    """
    raw = raw.strip()

    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.search(r'/shorts/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.search(r'/embed/([A-Za-z0-9_-]{11})', raw)
    if m:
        return m.group(1)

    m = re.fullmatch(r'[A-Za-z0-9_-]{11}', raw)
    if m:
        return raw

    return None


# ----------------------------------------------------------------------
# (2-5) YouTube タグの変換
# ----------------------------------------------------------------------
def _replace_youtube(m: re.Match) -> str:
    """
    [youtube:URL] をファサード形式の埋め込みに変換する。

    ファサード形式 = 最初はサムネイル + 再生ボタンだけを表示し、
    クリック時に初めて iframe を生成する軽量な埋め込み方式
    （実際の iframe 生成は detail.html の ytPlay() が行う）。

    動画 ID を認識できなかった場合のエラーメッセージ内のユーザー入力は
    escape() で無害化する。
    """
    raw      = m.group(1)
    video_id = _extract_youtube_id(raw)

    if not video_id:
        return f'<p style="color:#c0392b;">[youtube: 動画IDを認識できませんでした → {escape(raw)}]</p>'

    thumb_url = f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'
    embed_url = f'https://www.youtube.com/embed/{video_id}?autoplay=1'

    return (
        f'<div class="post-youtube-wrapper" data-embed-url="{embed_url}">'
        f'  <div class="post-youtube-facade" onclick="ytPlay(this)">'
        f'    <img class="post-youtube-thumb"'
        f'         src="{thumb_url}"'
        f'         alt="YouTube動画のサムネイル"'
        f'         loading="lazy">'
        f'    <button class="post-youtube-play-btn" aria-label="動画を再生">'
        f'      <svg viewBox="0 0 68 48" width="68" height="48">'
        f'        <path class="yt-btn-bg" d="M66.5 7.7a8.5 8.5 0 0 0-6-6C55.8.3 34 .3 34 .3S12.2.3 7.5 1.7a8.5 8.5 0 0 0-6 6C.1 11.4 0 24 0 24s.1 12.6 1.5 16.3a8.5 8.5 0 0 0 6 6C12.2 47.7 34 47.7 34 47.7s21.8 0 26.5-1.4a8.5 8.5 0 0 0 6-6C67.9 36.6 68 24 68 24s-.1-12.6-1.5-16.3z"/>'
        f'        <path class="yt-btn-icon" d="M45 24 27 14v20"/>'
        f'      </svg>'
        f'    </button>'
        f'  </div>'
        f'</div>'
    )