/* ============================================================
   static/js/editor-link.js
   【対象ページ】 create.html（新規投稿）／ update.html（記事編集）共通
   ============================================================
   「🔗 リンクカード挿入モーダル」の挙動をまとめた追加スクリプト。

   既存の editor.js（地図・YouTube モーダル等）には手を加えず、
   このファイルを editor.js の「後」に読み込むことでリンク機能を足す。
   onclick 属性（openLinkModal 等）から呼べるよう、関数は
   editor.js と同じくトップレベルのグローバル関数として定義する。

   【本文に挿入されるタグの形式】
       [link:URL]                     … URL だけ（カードにはドメイン名を表示）
       [link:URL|タイトル]            … タイトル付き
       [link:URL|タイトル|説明文]     … タイトル + 説明文付き
   区切り文字は「|」。タイトル・説明に「|」「]」改行が混ざると
   タグが壊れるため、挿入前に半角スペースへ置換して無害化する。

   ※ サーバー側 rendering.py の _replace_link() が、このタグを
     リンクカードの HTML（<a class="post-link-card" ...>）へ変換する。
     片方の仕様を変えたらもう片方も合わせること。
   ============================================================ */

/* URL からドメイン名（先頭の www. は除去）を取り出す。
   不正な URL の場合は空文字を返す。 */
function _linkExtractDomain(url) {
    try {
        var host = new URL(url).hostname;
        return host.replace(/^www\./i, '');
    } catch (e) {
        return '';
    }
}

/* http:// または https:// で始まる URL かどうかを判定する。 */
function _linkIsValidUrl(url) {
    return /^https?:\/\/\S+$/i.test(url.trim());
}

/* タイトル・説明文に含まれるタグ区切り文字（| ] 改行）を
   半角スペースに置き換えて、[link:...] タグが壊れないようにする。 */
function _linkSanitize(text) {
    return text.replace(/[|\]\r\n]/g, ' ').replace(/\s+/g, ' ').trim();
}

function openLinkModal() {
    // モーダル本体が DOM に無い場合は、原因を明示して安全に中断する
    // （_link_modal.html の include 忘れなどを早期に発見できるようにする）
    var modal = document.getElementById('link-modal');
    if (!modal) {
        console.error('[editor-link.js] #link-modal が見つかりません。_link_modal.html が include されているか確認してください。');
        return;
    }
    var ta = document.getElementById('bodyTextarea');
    window._linkInsertPos = { start: ta.selectionStart, end: ta.selectionEnd };

    document.getElementById('link-url-input').value   = '';
    document.getElementById('link-title-input').value = '';
    document.getElementById('link-desc-input').value  = '';
    document.getElementById('link-preview-area').innerHTML =
        '<p class="map-preview-placeholder">URL を入力するとプレビューが表示されます</p>';
    document.getElementById('link-insert-btn').disabled = true;

    document.getElementById('link-modal-overlay').classList.add('open');
    document.getElementById('link-modal').classList.add('open');
    setTimeout(function () { document.getElementById('link-url-input').focus(); }, 80);
}

function closeLinkModal() {
    var overlay = document.getElementById('link-modal-overlay');
    var modal   = document.getElementById('link-modal');
    if (overlay) overlay.classList.remove('open');
    if (modal)   modal.classList.remove('open');
}

/* 入力内容からプレビューカードを組み立てる。
   innerHTML による文字列組み立てを避け、DOM API（createElement +
   textContent）で構築することで自己 XSS の経路を作らない。 */
function updateLinkPreview() {
    var url       = document.getElementById('link-url-input').value.trim();
    var title     = document.getElementById('link-title-input').value.trim();
    var desc      = document.getElementById('link-desc-input').value.trim();
    var previewEl = document.getElementById('link-preview-area');
    var insertBtn = document.getElementById('link-insert-btn');

    if (!_linkIsValidUrl(url)) {
        previewEl.textContent = '';
        var ph = document.createElement('p');
        ph.className   = 'map-preview-placeholder';
        ph.textContent = 'URL を入力するとプレビューが表示されます';
        previewEl.appendChild(ph);
        insertBtn.disabled = true;
        return;
    }
    insertBtn.disabled = false;

    var domain = _linkExtractDomain(url);

    // カード本体（<a> ではなく <div> で見た目だけ再現。クリックは無効）
    var card = document.createElement('div');
    card.className = 'post-link-card post-link-card--preview';

    var body = document.createElement('span');
    body.className = 'post-link-card-body';

    var titleEl = document.createElement('span');
    titleEl.className   = 'post-link-card-title';
    titleEl.textContent = title || domain;   // タイトル省略時はドメインを表示
    body.appendChild(titleEl);

    if (desc) {
        var descEl = document.createElement('span');
        descEl.className   = 'post-link-card-desc';
        descEl.textContent = desc;
        body.appendChild(descEl);
    }

    var domainEl = document.createElement('span');
    domainEl.className = 'post-link-card-domain';

    var favicon = document.createElement('img');
    favicon.className = 'post-link-card-favicon';
    favicon.src       = 'https://www.google.com/s2/favicons?domain=' + encodeURIComponent(domain) + '&sz=64';
    favicon.alt       = '';
    favicon.width     = 16;
    favicon.height    = 16;
    favicon.onerror   = function () { this.style.display = 'none'; };
    domainEl.appendChild(favicon);
    domainEl.appendChild(document.createTextNode(domain));
    body.appendChild(domainEl);

    card.appendChild(body);

    previewEl.textContent = '';
    previewEl.appendChild(card);
}

/* 入力内容を [link:URL|タイトル|説明] タグにして本文へ挿入する。 */
function insertLinkTag() {
    var url   = document.getElementById('link-url-input').value.trim();
    if (!_linkIsValidUrl(url)) return;

    var title = _linkSanitize(document.getElementById('link-title-input').value);
    var desc  = _linkSanitize(document.getElementById('link-desc-input').value);

    // タグ本体を組み立てる。
    //   説明があるのにタイトルが空のときは「URL||説明」と空フィールドを挟み、
    //   サーバー側の分割（URL / タイトル / 説明）の順番がズレないようにする。
    var inner = url;
    if (title || desc) { inner += '|' + title; }
    if (desc)          { inner += '|' + desc; }

    var ta        = document.getElementById('bodyTextarea');
    var pos       = window._linkInsertPos || { start: ta.value.length, end: ta.value.length };
    var val       = ta.value;
    var lineStart = val.lastIndexOf('\n', pos.start - 1) + 1;
    // 行頭でなければ改行を足して、タグを必ず独立した行に置く（YouTube/地図と同じ方針）
    var tag       = (pos.start === lineStart ? '' : '\n') + '[link:' + inner + ']\n';

    ta.value   = val.substring(0, pos.start) + tag + val.substring(pos.end);
    var newPos = pos.start + tag.length;
    ta.setSelectionRange(newPos, newPos);
    ta.focus();
    closeLinkModal();
}

/* Escape キーでリンクモーダルを閉じる
   （editor.js 側の Escape ハンドラとは独立して動く） */
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeLinkModal(); }
});