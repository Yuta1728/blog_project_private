# views/blog.py
#
# 【役割】
# 一般公開ページ（誰でも閲覧できるページ）のルートとロジックを担うビューファイル。
#
# 担当ページ:
#   /            → トップ（記事一覧）
#   /about       → 管理者自己紹介ページ
#   /howto       → このブログの使い方ページ
#   /<id>/detail → 記事詳細ページ
#   /genre       → ジャンル一覧ページ

from flask import Blueprint, render_template, request, redirect, flash
from flask_login import current_user
import markdown    # マークダウン → HTML 変換ライブラリ
import re          # 正規表現（[img1], [map:xxx] の置換に使用）
from sqlalchemy import func
from extensions import db
from models import Post, Hashtag, User
from constants import DEFAULT_GENRES
import config

blog_bp = Blueprint('blog', __name__)


# ===================================================================
# トップページ（記事一覧）
# ===================================================================
@blog_bp.route('/', methods=['GET'])
def index():
    """
    記事の一覧を表示する。
    クエリパラメータで絞り込み・検索が可能：
      ?genre=xxx      → ジャンルで絞り込み
      ?search=xxx     → タイトル・ハッシュタグをキーワード検索
      ?hashtag=xxx    → ハッシュタグで絞り込み
    """
    # URL クエリパラメータの取得
    selected_genre   = request.args.get('genre')
    search_word      = request.args.get('search')
    selected_hashtag = request.args.get('hashtag')

    # -------------------------------------------------------------------
    # 表示対象記事の決定
    # 管理者ログイン中: 公開記事 + 自分の非公開記事 を表示
    # 未ログイン:       公開記事のみ表示
    # -------------------------------------------------------------------
    if current_user.is_authenticated:
        query = Post.query.filter(
            (Post.is_published == True) | (Post.user_id == current_user.id)
        )
    else:
        query = Post.query.filter(Post.is_published == True)

    # -------------------------------------------------------------------
    # キーワード検索フィルター
    # タイトルまたはハッシュタグ名がキーワードを含む記事を返す。
    # any() を使うことで EXISTS サブクエリになり、
    # join() との混在による重複行・カーテシアン積を防いでいる。
    # ilike() は大文字・小文字を区別しない LIKE 検索。
    # -------------------------------------------------------------------
    if search_word:
        keyword = f'%{search_word.strip()}%'
        query = query.filter(
            Post.title.ilike(keyword) |
            Post.hashtags.any(Hashtag.name.ilike(keyword))
        )

    # -------------------------------------------------------------------
    # ジャンルフィルター
    # -------------------------------------------------------------------
    if selected_genre:
        query = query.filter(Post.genre == selected_genre)

    # -------------------------------------------------------------------
    # ハッシュタグフィルター
    # JOIN を使って hashtag テーブルと結合し、指定タグの記事だけに絞る。
    # search フィルターの any() とは異なり join() を使うが、
    # search と hashtag が同時に指定されるケースは UI 設計上ないため問題なし。
    # -------------------------------------------------------------------
    if selected_hashtag:
        query = query.join(Post.hashtags).filter(Hashtag.name == selected_hashtag)

    # 最終的なクエリ実行: 作成日時の降順（新しい記事が先頭）
    posts = query.order_by(Post.created_at.desc()).all()

    # -------------------------------------------------------------------
    # ジャンル内ハッシュタグ一覧（絞り込みバー用）
    # ジャンルが選択されているときのみ、そのジャンルに属する記事の
    # ハッシュタグ一覧を取得してフィルターバーに表示する。
    # DB 側で JOIN + DISTINCT + ORDER BY を一括処理して N+1 問題を防ぐ。
    # -------------------------------------------------------------------
    hashtags_in_genre = []
    if selected_genre:
        pub_filter = [] if current_user.is_authenticated else [Post.is_published == True]
        hashtags_in_genre = (
            db.session.query(Hashtag)
            .join(Hashtag.posts)           # hashtag → post_hashtags → post と JOIN
            .filter(Post.genre == selected_genre, *pub_filter)
            .distinct()                    # 同じタグが複数記事に付いていても 1 件だけ返す
            .order_by(Hashtag.name)        # 名前順で並べる
            .all()
        )

    # -------------------------------------------------------------------
    # 統計情報（トップページのみ表示）
    # ジャンル・検索・タグ絞り込みがない = トップ表示のときだけ計算する。
    # -------------------------------------------------------------------
    stats      = None
    admin_user = None
    if not selected_genre and not search_word and not selected_hashtag:

        # 公開記事の総数
        post_count = Post.query.filter(Post.is_published == True).count()

        # 公開記事に付いているハッシュタグの種類数
        # func.count(func.distinct()) で 1 クエリにまとめて効率化
        hashtag_count = (
            db.session.query(func.count(func.distinct(Hashtag.id)))
            .join(Hashtag.posts)
            .filter(Post.is_published == True)
            .scalar()  # 単一の数値だけ取得（リストではなく int が返る）
        )

        # 最終更新日: updated_at の最大値を持つ記事の日付
        # with_entities(Post.updated_at) で updated_at カラムのみ取得し
        # 全カラムを転送する無駄を省いている
        latest = (
            Post.query
            .filter(Post.is_published == True)
            .order_by(Post.updated_at.desc())
            .with_entities(Post.updated_at)
            .first()
        )
        last_updated = latest.updated_at.strftime('%Y/%m/%d') if latest else '---'

        stats = {
            'post_count':    post_count,
            'hashtag_count': hashtag_count,
            'last_updated':  last_updated,
        }

        # ヒーローセクションに管理者の表示名を出すために取得
        admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()

    return render_template(
        'index.html',
        posts             = posts,
        selected_genre    = selected_genre,
        search_word       = search_word,
        selected_hashtag  = selected_hashtag,
        hashtags_in_genre = hashtags_in_genre,
        stats             = stats,
        admin_user        = admin_user,
    )


# ===================================================================
# 自己紹介ページ
# ===================================================================
@blog_bp.route('/about')
def about():
    # テンプレートで管理者のニックネームを表示するために User オブジェクトを渡す
    admin_user = User.query.filter_by(username=config.ADMIN_USERNAME).first()
    return render_template('about.html', admin_user=admin_user)


# ===================================================================
# 使い方ページ
# ===================================================================
@blog_bp.route('/howto')
def howto():
    return render_template('howto.html')


# ===================================================================
# 記事詳細ページ
# ===================================================================
@blog_bp.route('/<int:id>/detail', methods=['GET'])
def detail(id):
    """
    記事を取得し、マークダウン変換・画像埋め込み・地図埋め込みを行って表示する。
    非公開記事は管理者のみ閲覧可能。
    """
    # DB から記事を取得（存在しない id の場合は None が返る）
    post = db.session.get(Post, id)

    if not post:
        flash("指定された記事が見つかりません。")
        return redirect('/')

    # 非公開記事へのアクセス制御
    # 非公開 かつ（未ログイン または 他人の記事）の場合はアクセス拒否
    if not post.is_published:
        if not current_user.is_authenticated or post.user_id != current_user.id:
            flash("この記事は非公開に設定されているため閲覧できません。")
            return redirect('/')

    body_content   = post.body
    # [toc] マーカーが本文に含まれているか事前にチェック
    # （マークダウン変換後に md.toc を使うかどうかの判定に使う）
    has_toc_marker = '[toc]' in body_content

    # -------------------------------------------------------------------
    # 空行の正規化（マークダウン変換前処理）
    # 連続する空行を適切な <br> タグや改行に変換して
    # 意図した段落間隔がレンダリングされるようにする
    # -------------------------------------------------------------------
    body_content = _expand_blank_lines(body_content)

    # -------------------------------------------------------------------
    # マークダウン → HTML 変換
    # 使用拡張:
    #   toc    → ## / ### 見出しから目次を自動生成し [toc] マーカーを目次 HTML に置換
    #   nl2br  → 改行文字を <br> タグに変換（通常のマークダウンは改行を無視する）
    # toc_depth='2-3' → H2 と H3 だけを目次に含める（H1 は記事タイトルと被るため除外）
    # -------------------------------------------------------------------
    md = markdown.Markdown(
        extensions=['toc', 'nl2br'],
        extension_configs={'toc': {'toc_depth': '2-3', 'marker': '[toc]'}}
    )

    display_body = md.convert(body_content)  # マークダウン → HTML 文字列

    # [toc] マーカーがなかった場合は md.toc（生成された目次 HTML）を別途渡す
    # テンプレート側で記事本文の上に目次ブロックとして表示する
    toc_html = None if has_toc_marker else md.toc

    # -------------------------------------------------------------------
    # 画像タグの埋め込み（[img1], [img2] → <img> タグ or <figure> タグ）
    # -------------------------------------------------------------------
    if post.img_name:
        images   = post.img_name.split(',')          # カンマ区切りのファイル名リストに分割
        captions = post.img_captions.split('\t') if post.img_captions else []  # タブ区切りキャプション

        for index, img_file in enumerate(images):
            # ディレクトリトラバーサル対策: ファイル名に / や \ が含まれていても無害化
            # DB に保存済みの値だが、念のため除去する（多層防御）
            img_file = re.sub(r'[/\\]', '', img_file.strip())
            caption  = captions[index].strip() if index < len(captions) else ''

            if caption:
                # キャプションあり → <figure> + <figcaption> で意味的にマークアップ
                img_tag = (
                    f'<figure class="post-figure">'
                    f'<img src="/static/img/posts/{img_file}" alt="{caption}" style="max-width:100%; height:auto;">'
                    f'<figcaption class="post-figcaption">{caption}</figcaption>'
                    f'</figure>'
                )
            else:
                # キャプションなし → シンプルな <img> タグで表示
                img_tag = (
                    f'<span style="display:block; text-align:center; margin: 15px 0;">'
                    f'<img src="/static/img/posts/{img_file}" style="max-width:100%; height:auto;">'
                    f'</span>'
                )

            # 本文中の [img1], [img2] ... をそれぞれ対応する <img> タグに置換
            display_body = display_body.replace(f'[img{index+1}]', img_tag)

    # 画像が少ない場合など、余った [imgN] マーカーを除去（空文字に置換）
    display_body = re.sub(r'\[img\d+\]', '', display_body)

    # -------------------------------------------------------------------
    # 地図タグの変換（[map:場所名] → Google Maps iframe）
    # _replace_map() ヘルパーに変換処理を委譲
    # -------------------------------------------------------------------
    display_body = re.sub(r'\[map:([^\]]+)\]', _replace_map, display_body)

    return render_template('detail.html', post=post, display_body=display_body, toc_html=toc_html)


# ===================================================================
# ジャンル一覧ページ
# ===================================================================
@blog_bp.route('/genre', methods=['GET'])
def genre_list():
    """
    constants.py の DEFAULT_GENRES をアルファベット順（五十音順）に並べて表示する。
    '未分類' は特別扱いでリストの末尾に移動する。
    """
    genres_list = sorted(DEFAULT_GENRES)
    if '未分類' in genres_list:
        genres_list.remove('未分類')
        genres_list.append('未分類')  # 末尾に移動
    return render_template('genre.html', genres=genres_list)


# ===================================================================
# 内部ヘルパー関数群
# ===================================================================

def _is_structural_line(s: str) -> bool:
    """
    指定した行が「構造的な行」かどうかを判定する。
    構造的な行: マークダウンの見出し（#）、コードブロック（```）、TOC マーカー（[toc]）
    _expand_blank_lines() が空行の扱いを決定するために使用する。
    """
    stripped = s.strip()
    return (
        stripped.startswith('#') or   # ## 見出し など
        stripped.startswith('```') or # コードブロックの開始・終了
        stripped == '[toc]'           # 目次マーカー
    )


def _expand_blank_lines(text: str) -> str:
    """
    記事本文（マークダウン）中の連続する空行を適切に処理する前処理関数。

    【目的】
    通常のマークダウンでは複数の空行を入れても段落区切りは 1 つにまとめられる。
    このブログでは「意図的に段落間を広げる」ために複数の空行を書くと
    <br> タグに変換して間隔を広げる仕様にしている。

    【処理ロジック】
    - 空行が 1 行だけ: 通常の段落区切りなのでそのまま維持
    - 連続する空行が 2 行以上 かつ 前後が構造的な行（見出し等）でない場合:
      最初の空行 + 残りの空行を <br> に変換して見た目の間隔を再現する
    - 前後が構造的な行の場合: そのまま維持（マークダウンの文法を壊さないため）

    @param text: マークダウン本文の文字列
    @return: 空行を正規化した文字列
    """
    lines  = text.split('\n')
    result = []
    i      = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == '':
            # --- 連続する空行をまとめて処理 ---
            blank_count = 0
            while i < len(lines) and lines[i].strip() == '':
                blank_count += 1
                i += 1

            prev_line = result[-1] if result else ''
            next_line = lines[i] if i < len(lines) else ''

            if (_is_structural_line(prev_line) or
                    _is_structural_line(next_line) or
                    blank_count == 1):
                # 構造的な行の隣 or 空行が 1 つだけ → そのまま維持
                result.extend([''] * blank_count)
            else:
                # 2 行以上の連続空行 → 最初の 1 行は通常の改行、残りは <br>
                result.append('')
                result.extend(['<br>'] * (blank_count - 1))
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def _replace_map(m: re.Match) -> str:
    """
    正規表現のマッチオブジェクトを受け取り、
    [map:場所名] を Google Maps の iframe 埋め込み HTML に変換する。

    re.sub() のコールバックとして使用される（blog.py の detail() 内で呼び出し）。

    例:
      入力: [map:東京スカイツリー]
      出力: <div class="post-map-wrapper">
               <div class="post-map-label">📍 東京スカイツリー</div>
               <iframe src="https://maps.google.com/maps?q=東京スカイツリー&output=embed&hl=ja" ...></iframe>
            </div>

    @param m: re.Match オブジェクト（グループ 1 が場所名）
    @return: Google Maps iframe を含む HTML 文字列
    """
    place   = m.group(1).strip()           # [map:XXX] の XXX 部分を取得
    encoded = place.replace(' ', '+')       # URL 用に空白を + に変換（シンプルな URL エンコード）

    return (
        f'<div class="post-map-wrapper">'
        f'<div class="post-map-label">📍 {place}</div>'
        f'<iframe class="post-map-iframe"'
        f' src="https://maps.google.com/maps?q={encoded}&output=embed&hl=ja"'
        f' loading="lazy" allowfullscreen></iframe>'  # loading="lazy" で初期表示を高速化
        f'</div>'
    )