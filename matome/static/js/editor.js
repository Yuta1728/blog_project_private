/* ============================================================
   static/js/editor.js
   【対象ページ】 create.html（新規投稿）／ update.html（記事編集）共通
   ============================================================
   以前は create.html と update.html にほぼ同一の JavaScript が
   それぞれ数百行ずつ重複して書かれていた。差異はごく一部だったため、
   共通ロジックをこのファイルに一本化し、両テンプレートから読み込む。

   【ページ固有の差異は window.EDITOR_CONFIG で受け取る】
     newImageCaptionPrefix : 新規画像キャプションの input name 接頭辞
       - create.html : 'img_caption_'
       - update.html : 'new_img_caption_'
         （編集時は「既存画像のキャプション欄（img_caption_N）」と
           名前が衝突しないよう、新規画像側を別接頭辞にしている）

   【読み込み方法】
     各テンプレートの末尾で、
       <script>window.EDITOR_CONFIG = { ... };</script>
       <script src="{{ url_for('static', filename='js/editor.js') }}"></script>
     の順に読み込む。<body> 末尾で読み込まれるため DOM は構築済み。

   【備考】
     onclick 属性から呼ばれる関数（handleStatusToggle など）は
     グローバル関数として定義する必要があるため、このファイルは
     全体を IIFE で包まず、トップレベルの関数宣言で定義している。
   ============================================================ */

/* 差異設定の取り込み（未設定時は新規投稿相当のデフォルト） */
var EDITOR_CONFIG          = window.EDITOR_CONFIG || {};
var NEW_IMG_CAPTION_PREFIX = EDITOR_CONFIG.newImageCaptionPrefix || 'img_caption_';


/* =========================================================
   公開設定トグル（🔒非公開 / 🔓全体公開）
   ========================================================= */
function handleStatusToggle() {
    var hiddenInput = document.getElementById('is_published');
    var btn  = document.getElementById('toggle_status_btn');
    var icon = btn.querySelector('.status-icon');
    var text = btn.querySelector('.status-text');

    if (hiddenInput.value === 'false') {
        hiddenInput.value = 'true';
        btn.classList.remove('private');
        btn.classList.add('published');
        icon.textContent = '🔓';
        text.textContent = '全体公開';
    } else {
        hiddenInput.value = 'false';
        btn.classList.remove('published');
        btn.classList.add('private');
        icon.textContent = '🔒';
        text.textContent = '非公開';
    }
}


/* =========================================================
   画像ファイル管理（追加・削除・プレビュー再描画）
   =========================================================
   _fileList : File オブジェクトの配列（正データ）
   _captions : キャプション文字列の配列（インデックス対応）

   input[name="img[]"] の files は DataTransfer で都度再構築して同期する。
   これにより既存の Flask バックエンド（request.files.getlist('img[]')）は
   一切変更せずに動作する。
   ========================================================= */
var _fileList = [];   // File オブジェクトを格納する配列
var _captions = [];   // キャプション文字列を格納する配列

/** input[name="img[]"] の files プロパティを _fileList と同期する。 */
function _syncInputFiles() {
    var dt    = new DataTransfer();
    var input = document.getElementById('imgUpload');
    _fileList.forEach(function(f) { dt.items.add(f); });
    input.files = dt.files;
}

/** 「複数まとめて選択」: _fileList を完全置き換えして再描画。 */
function onBulkSelect(input) {
    var newFiles = Array.from(input.files);
    if (newFiles.length === 0) return;
    _fileList = newFiles;
    _captions = new Array(newFiles.length).fill('');
    _syncInputFiles();
    renderPreviews();
}

/** 「1枚追加」: _fileList に追記して再描画。 */
function onOneSelect(input) {
    var newFiles = Array.from(input.files);
    if (newFiles.length === 0) return;
    _saveCaptions();
    newFiles.forEach(function(f) {
        _fileList.push(f);
        _captions.push('');
    });
    _syncInputFiles();
    renderPreviews();
    // 同じファイルを再度選べるよう input をリセット
    input.value = '';
}

/** 指定インデックスの画像を削除して再描画。 */
function deleteImage(index) {
    _saveCaptions();
    _fileList.splice(index, 1);
    _captions.splice(index, 1);
    _syncInputFiles();
    renderPreviews();
}

/**
 * DOM 上のキャプション入力欄の値を _captions に保存する。
 * 新規画像プレビューは常に #preview-list 内にあるため、
 * update.html の既存画像キャプション欄（#existing-img-list 内）と
 * 混ざらないよう、スコープを #preview-list に限定する。
 * （create.html でも新規プレビューは #preview-list 内にあるため同じ挙動）
 */
function _saveCaptions() {
    var inputs = document.querySelectorAll('#preview-list .preview-caption-input');
    inputs.forEach(function(el, i) {
        if (i < _captions.length) { _captions[i] = el.value; }
    });
}

/**
 * プレビューエリアを _fileList の内容で再描画する。
 * [imgN] ボタン・キャプション入力・削除ボタンもここで生成する。
 */
function renderPreviews() {
    var previewArea = document.getElementById('preview-area');
    var previewList = document.getElementById('preview-list');
    previewList.innerHTML = '';

    if (_fileList.length === 0) {
        previewArea.style.display = 'none';
        rebuildImgBtns(0);
        return;
    }
    previewArea.style.display = 'block';

    _fileList.forEach(function(file, index) {
        var reader = new FileReader();
        reader.onload = function(e) {
            var item = document.createElement('div');
            item.className = 'preview-item';
            item.style.width = '150px';

            // サムネイル
            var img = document.createElement('img');
            img.src = e.target.result;
            img.alt = file.name;

            // [imgN] ラベル
            var label = document.createElement('div');
            label.className = 'preview-label';
            label.textContent = '[img' + (index + 1) + ']';

            // ファイル名
            var filename = document.createElement('div');
            filename.className = 'preview-filename';
            filename.textContent = file.name;
            filename.title = file.name;

            // キャプション入力
            // 【重要】input name の接頭辞はページごとに異なる（EDITOR_CONFIG）。
            //   create: img_caption_N / update: new_img_caption_N
            var captionWrapper = document.createElement('div');
            captionWrapper.className = 'preview-caption-wrapper';
            var captionInput = document.createElement('input');
            captionInput.type        = 'text';
            captionInput.name        = NEW_IMG_CAPTION_PREFIX + (index + 1);
            captionInput.placeholder = '画像の説明（省略可）';
            captionInput.className   = 'preview-caption-input';
            captionInput.maxLength   = 100;
            captionInput.value       = _captions[index] || '';
            captionWrapper.appendChild(captionInput);

            // 削除ボタン（クロージャでインデックスを束縛）
            var deleteBtn = document.createElement('button');
            deleteBtn.type      = 'button';
            deleteBtn.className = 'preview-delete-btn';
            deleteBtn.textContent = '✕ この画像を削除';
            (function(i) {
                deleteBtn.onclick = function() { deleteImage(i); };
            })(index);

            item.appendChild(img);
            item.appendChild(label);
            item.appendChild(filename);
            item.appendChild(captionWrapper);
            item.appendChild(deleteBtn);
            previewList.appendChild(item);
        };
        reader.readAsDataURL(file);
    });

    rebuildImgBtns(_fileList.length);
}


/* =========================================================
   サムネイル専用画像のプレビュー・削除
   =========================================================
   ・onThumbnailSelect : 新しいサムネイル選択時のプレビュー
   ・clearThumbnail    : 選択した新規サムネイルを取り消す
   ・toggleThumbnailDelete : 現在のサムネイルを「削除予定」にする／取り消す
       （update.html のみ。hidden の keep_thumbnail を '0'/'1' で切り替える。
         対象要素が無い create.html では呼ばれないため無害）
   ========================================================= */
function onThumbnailSelect(input) {
    var file = input.files && input.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(e) {
        document.getElementById('thumbnail-preview-img').src = e.target.result;
        document.getElementById('thumbnail-preview-area').style.display = 'block';
    };
    reader.readAsDataURL(file);
}

function clearThumbnail() {
    var input = document.getElementById('thumbnailUpload');
    input.value = '';
    document.getElementById('thumbnail-preview-img').src = '';
    document.getElementById('thumbnail-preview-area').style.display = 'none';
}

function toggleThumbnailDelete() {
    var flag = document.getElementById('keep_thumbnail');
    var item = document.getElementById('current-thumbnail-item');
    var btn  = document.getElementById('thumbnail-delete-btn');
    if (!flag) return;

    if (flag.value === '0') {
        // 削除の取り消し
        flag.value = '1';
        item.style.opacity = '';
        btn.textContent = '✕ このサムネイルを削除';
    } else {
        // 削除予定としてマーク
        flag.value = '0';
        item.style.opacity = '0.45';
        btn.textContent = '↩ 削除を取り消す';
    }
}


/* =========================================================
   既存画像の個別削除（update.html のみ）
   =========================================================
   各既存画像カードの hidden keep_img_N（'1'=残す / '0'=削除予定）を
   トグルし、削除予定のカードをグレーアウトして可視化する。
   実際の削除はフォーム送信後にサーバー側で行う。
   対象要素が無い create.html では呼ばれないため無害。
   ========================================================= */
function toggleExistingDelete(btn) {
    var item    = btn.closest('.existing-img-item');
    var flag    = item.querySelector('.keep-img-flag');
    var caption = item.querySelector('.preview-caption-input');

    if (flag.value === '0') {
        // 削除の取り消し
        flag.value        = '1';
        item.style.opacity = '';
        caption.disabled  = false;
        btn.textContent   = '✕ この画像を削除';
    } else {
        // 削除予定としてマーク
        flag.value        = '0';
        item.style.opacity = '0.45';
        caption.disabled  = true;
        btn.textContent   = '↩ 削除を取り消す';
    }

    renumberExistingLabels();
}

/** 削除予定を除いた「更新後の番号」を [imgN] ラベルに反映する。 */
function renumberExistingLabels() {
    var items = document.querySelectorAll('.existing-img-item');
    var n = 0;
    items.forEach(function (item) {
        var label = item.querySelector('.preview-label');
        if (item.querySelector('.keep-img-flag').value === '0') {
            label.textContent = '（削除予定）';
        } else {
            n += 1;
            label.textContent = '[img' + n + ']（更新後）';
        }
    });
}


/* =========================================================
   ジャンル入力切替
   ========================================================= */
function toggleNewGenreInput() {
    var selectBox       = document.getElementById('genre_select');
    var newGenreWrapper = document.getElementById('new_genre_wrapper');
    var newGenreInput   = document.getElementById('genre_new');

    if (selectBox.value === '__NEW__') {
        newGenreWrapper.style.display = 'block';
        newGenreInput.required = true;
    } else {
        newGenreWrapper.style.display = 'none';
        newGenreInput.required = false;
        newGenreInput.value = '';
    }
}


/* =========================================================
   デフォルトサムネイルプレビュー
   ========================================================= */
function previewDefaultThumb(select) {
    var previewArea = document.getElementById('default-thumb-preview-area');
    var previewImg  = document.getElementById('default-thumb-preview-img');
    if (select.value === 'none') {
        previewArea.style.display = 'none';
        previewImg.src = '';
    } else {
        previewArea.style.display = 'block';
        previewImg.src = "/static/img/thbnails/" + select.value;
    }
}


/* =========================================================
   マークダウンツールバー共通ユーティリティ
   ========================================================= */
function mdInsertAt(ta, text, selectFrom, selectTo) {
    var start  = ta.selectionStart;
    var end    = ta.selectionEnd;
    var before = ta.value.substring(0, start);
    var after  = ta.value.substring(end);
    ta.value = before + text + after;
    var newPos = selectFrom !== undefined ? start + selectFrom : start + text.length;
    var newEnd = selectTo   !== undefined ? start + selectTo   : newPos;
    ta.setSelectionRange(newPos, newEnd);
    ta.focus();
}

function mdInsertLinePrefix(ta, prefix) {
    var start     = ta.selectionStart;
    var val       = ta.value;
    var lineStart = val.lastIndexOf('\n', start - 1) + 1;
    var before    = val.substring(0, lineStart);
    var after     = val.substring(lineStart);
    ta.value = before + prefix + after;
    var newPos = start + prefix.length;
    ta.setSelectionRange(newPos, newPos);
    ta.focus();
}

function mdInsertHeading2() { mdInsertLinePrefix(document.getElementById('bodyTextarea'), '## '); }
function mdInsertHeading3() { mdInsertLinePrefix(document.getElementById('bodyTextarea'), '### '); }

function mdWrapBold() {
    var ta       = document.getElementById('bodyTextarea');
    var start    = ta.selectionStart;
    var end      = ta.selectionEnd;
    var selected = ta.value.substring(start, end);
    if (selected.length > 0) {
        mdInsertAt(ta, '**' + selected + '**', 2, 2 + selected.length);
    } else {
        mdInsertAt(ta, '**太字テキスト**', 2, 6);
    }
}

function mdInsertToc() {
    var ta  = document.getElementById('bodyTextarea');
    var pos = ta.selectionStart;
    var val = ta.value;
    var before = val.substring(0, pos);
    var leadingNewlines = before.length === 0      ? ''
                        : before.endsWith('\n\n')  ? ''
                        : before.endsWith('\n')     ? '\n'
                        :                              '\n\n';
    var after = val.substring(pos);
    var trailingNewlines = after.length === 0       ? '\n'
                         : after.startsWith('\n\n') ? ''
                         : after.startsWith('\n')   ? '\n'
                         :                              '\n\n';
    mdInsertAt(ta, leadingNewlines + '[toc]' + trailingNewlines);
}

function mdInsertImg(n) { mdInsertAt(document.getElementById('bodyTextarea'), '[img' + n + ']'); }

/**
 * [imgN] 挿入ボタンを count 個ぶん再生成する。
 * ボタンには data-img-index を付与し、クリックは #img-btn-group 上の
 * 委譲リスナー（このファイル末尾で登録）でまとめて処理する。
 * これにより「create の直接 onclick」「update の初期サーバー描画ボタン」の
 * 両方を単一の仕組みで扱える。
 */
function rebuildImgBtns(count) {
    var group = document.getElementById('img-btn-group');
    group.innerHTML = '';
    for (var i = 1; i <= count; i++) {
        var btn = document.createElement('button');
        btn.type      = 'button';
        btn.className = 'md-btn md-btn-img';
        btn.textContent = '[img' + i + ']';
        btn.dataset.imgIndex = i;
        group.appendChild(btn);
    }
}


/* =========================================================
   箇条書きリスト挿入
   ========================================================= */
var LIST_PREFIXES = { bullet: '●  ' };

function mdInsertList(type) {
    var ta     = document.getElementById('bodyTextarea');
    var prefix = LIST_PREFIXES[type];
    if (!prefix) return;
    var start        = ta.selectionStart;
    var end          = ta.selectionEnd;
    var hasSelection = (start !== end);
    if (hasSelection) { _mdListWrapSelection(ta, prefix, start, end); }
    else              { _mdListInsertEmpty(ta, prefix, start); }
}

function _mdListInsertEmpty(ta, prefix, cursorPos) {
    var val       = ta.value;
    var lineStart = val.lastIndexOf('\n', cursorPos - 1) + 1;
    var lineEnd   = val.indexOf('\n', cursorPos);
    var currentLine = val.substring(lineStart, lineEnd === -1 ? val.length : lineEnd);
    if (currentLine.trim() === '') {
        ta.value = val.substring(0, cursorPos) + prefix + val.substring(cursorPos);
        var newPos = cursorPos + prefix.length;
        ta.setSelectionRange(newPos, newPos);
    } else if (!currentLine.startsWith(prefix)) {
        ta.value = val.substring(0, lineStart) + prefix + val.substring(lineStart);
        var newPos2 = cursorPos + prefix.length;
        ta.setSelectionRange(newPos2, newPos2);
    } else {
        ta.setSelectionRange(cursorPos, cursorPos);
    }
    ta.focus();
}

function _mdListWrapSelection(ta, prefix, start, end) {
    var val      = ta.value;
    var selText  = val.substring(start, end);
    var converted = selText.split('\n').map(function(line) {
        if (line.trim() === '')       return line;
        if (line.startsWith(prefix)) return line;
        return prefix + line;
    }).join('\n');
    ta.value = val.substring(0, start) + converted + val.substring(end);
    ta.setSelectionRange(start, start + converted.length);
    ta.focus();
}


/* =========================================================
   ハッシュタグ入力プレビュー
   =========================================================
   innerHTML による文字列組み立てを避け、DOM API
   （createElement + textContent）で構築することで
   自己 XSS の経路を作らない。
   ========================================================= */
function renderHashtagPreview(value) {
    var area   = document.getElementById('hashtag-preview');
    var tokens = value.trim().split(/[\s\u3000,、]+/).filter(Boolean);

    area.textContent = '';
    tokens.forEach(function(t) {
        var name = t.replace(/^#+/, '');
        if (!name) return;
        var span = document.createElement('span');
        span.className   = 'hashtag-badge-preview';
        span.textContent = '#' + name;
        area.appendChild(span);
    });
}


/* =========================================================
   地図挿入モーダル
   ========================================================= */
var _mapPreviewTimer = null;

function openMapModal() {
    // モーダル本体が DOM に無い場合は、原因を明示して安全に中断する
    // （_map_modal.html の include 忘れなどを早期に発見できるようにする）
    var modal = document.getElementById('map-modal');
    if (!modal) {
        console.error('[editor.js] #map-modal が見つかりません。_map_modal.html が include されているか確認してください。');
        return;
    }
    var ta = document.getElementById('bodyTextarea');
    window._mapInsertPos = { start: ta.selectionStart, end: ta.selectionEnd };
    document.getElementById('map-place-input').value = '';
    document.getElementById('map-preview-area').innerHTML =
        '<p class="map-preview-placeholder">場所を入力するとプレビューが表示されます</p>';
    document.getElementById('map-insert-btn').disabled = true;
    document.getElementById('map-modal-overlay').classList.add('open');
    document.getElementById('map-modal').classList.add('open');
    setTimeout(function() { document.getElementById('map-place-input').focus(); }, 80);
}
function closeMapModal() {
    document.getElementById('map-modal-overlay').classList.remove('open');
    document.getElementById('map-modal').classList.remove('open');
}
function updateMapPreview(value) {
    var insertBtn   = document.getElementById('map-insert-btn');
    var previewArea = document.getElementById('map-preview-area');
    clearTimeout(_mapPreviewTimer);
    var place = value.trim();
    if (!place) {
        previewArea.innerHTML = '<p class="map-preview-placeholder">場所を入力するとプレビューが表示されます</p>';
        insertBtn.disabled = true;
        return;
    }
    insertBtn.disabled = false;
    _mapPreviewTimer = setTimeout(function() {
        var encoded = encodeURIComponent(place);
        previewArea.innerHTML =
            '<iframe class="map-preview-iframe"' +
            ' src="https://maps.google.com/maps?q=' + encoded + '&output=embed&hl=ja"' +
            ' loading="lazy" allowfullscreen></iframe>';
    }, 600);
}
function insertMapTag() {
    var place = document.getElementById('map-place-input').value.trim();
    if (!place) return;
    var ta        = document.getElementById('bodyTextarea');
    var pos       = window._mapInsertPos || { start: ta.value.length, end: ta.value.length };
    var val       = ta.value;
    var lineStart = val.lastIndexOf('\n', pos.start - 1) + 1;
    var tag       = (pos.start === lineStart ? '' : '\n') + '[map:' + place + ']\n';
    ta.value      = val.substring(0, pos.start) + tag + val.substring(pos.end);
    var newPos    = pos.start + tag.length;
    ta.setSelectionRange(newPos, newPos);
    ta.focus();
    closeMapModal();
}


/* =========================================================
   YouTube 挿入モーダル
   =========================================================
   ※ extractYoutubeId() はクライアント側の入力検証用。
      サーバー側 views/blog.py の _extract_youtube_id() が
      同等の抽出ロジックを持つ（正規表現の分岐が対応する）。
      クライアント検証とサーバー検証は独立して必要なため二重定義となるが、
      片方を変更したらもう片方も合わせること。
   ========================================================= */
var _ytPreviewTimer = null;

function openYoutubeModal() {
    // モーダル本体が DOM に無い場合は、原因を明示して安全に中断する
    // （_youtube_modal.html の include 忘れなどを早期に発見できるようにする）
    var modal = document.getElementById('youtube-modal');
    if (!modal) {
        console.error('[editor.js] #youtube-modal が見つかりません。_youtube_modal.html が include されているか確認してください。');
        return;
    }
    var ta = document.getElementById('bodyTextarea');
    window._youtubeInsertPos = { start: ta.selectionStart, end: ta.selectionEnd };
    document.getElementById('youtube-url-input').value = '';
    document.getElementById('youtube-preview-area').innerHTML =
        '<p class="map-preview-placeholder youtube-preview-placeholder">URL を入力するとプレビューが表示されます</p>';
    document.getElementById('youtube-insert-btn').disabled = true;
    document.getElementById('youtube-modal-overlay').classList.add('open');
    document.getElementById('youtube-modal').classList.add('open');
    setTimeout(function() { document.getElementById('youtube-url-input').focus(); }, 80);
}
function closeYoutubeModal() {
    document.getElementById('youtube-modal-overlay').classList.remove('open');
    document.getElementById('youtube-modal').classList.remove('open');
}
function extractYoutubeId(raw) {
    raw = raw.trim();
    var m = raw.match(/[?&]v=([A-Za-z0-9_-]{11})/);
    if (m) return m[1];
    m = raw.match(/youtu\.be\/([A-Za-z0-9_-]{11})/);
    if (m) return m[1];
    m = raw.match(/\/shorts\/([A-Za-z0-9_-]{11})/);
    if (m) return m[1];
    m = raw.match(/\/embed\/([A-Za-z0-9_-]{11})/);
    if (m) return m[1];
    if (/^[A-Za-z0-9_-]{11}$/.test(raw)) return raw;
    return null;
}
function updateYoutubePreview(value) {
    var insertBtn   = document.getElementById('youtube-insert-btn');
    var previewArea = document.getElementById('youtube-preview-area');
    clearTimeout(_ytPreviewTimer);
    var videoId = extractYoutubeId(value);
    if (!videoId) {
        previewArea.innerHTML = '<p class="map-preview-placeholder youtube-preview-placeholder">URL を入力するとプレビューが表示されます</p>';
        insertBtn.disabled = true;
        return;
    }
    insertBtn.disabled = false;
    _ytPreviewTimer = setTimeout(function() {
        var thumbUrl = 'https://img.youtube.com/vi/' + videoId + '/hqdefault.jpg';
        previewArea.innerHTML =
            '<img src="' + thumbUrl + '" alt="サムネイルプレビュー"' +
            ' style="width:100%; height:100%; object-fit:cover; display:block;"' +
            ' onerror="this.parentNode.innerHTML=\'<p class=map-preview-placeholder>サムネイルを取得できませんでした</p>\'">';
    }, 600);
}
function insertYoutubeTag() {
    var rawUrl = document.getElementById('youtube-url-input').value.trim();
    if (!rawUrl || !extractYoutubeId(rawUrl)) return;
    var ta        = document.getElementById('bodyTextarea');
    var pos       = window._youtubeInsertPos || { start: ta.value.length, end: ta.value.length };
    var val       = ta.value;
    var lineStart = val.lastIndexOf('\n', pos.start - 1) + 1;
    var tag       = (pos.start === lineStart ? '' : '\n') + '[youtube:' + rawUrl + ']\n';
    ta.value      = val.substring(0, pos.start) + tag + val.substring(pos.end);
    var newPos    = pos.start + tag.length;
    ta.setSelectionRange(newPos, newPos);
    ta.focus();
    closeYoutubeModal();
}


/* =========================================================
   初期化処理（DOM 構築後に実行）
   =========================================================
   このファイルは <body> 末尾で読み込まれるため、
   以下の登録時点で対象要素は既に存在する。
   ========================================================= */

/* [imgN] ボタンのクリック委譲
   create の動的生成ボタンも update の初期サーバー描画ボタンも
   すべて #img-btn-group 上の 1 つのリスナーで処理する。 */
(function () {
    var group = document.getElementById('img-btn-group');
    if (!group) return;
    group.addEventListener('click', function (e) {
        var btn = e.target.closest('.md-btn-img');
        if (btn && btn.dataset.imgIndex) {
            mdInsertImg(parseInt(btn.dataset.imgIndex, 10));
        }
    });
})();

/* Escape キーでモーダルを閉じる */
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { closeMapModal(); closeYoutubeModal(); }
});

/* Sticky ツールバー（本文欄上部への貼り付き検知） */
(function () {
    'use strict';
    var toolbar = document.getElementById('md-toolbar');
    if (!toolbar) return;
    var sentinel = document.createElement('div');
    sentinel.style.cssText = 'position:absolute;top:0;height:1px;pointer-events:none;';
    toolbar.parentElement.insertBefore(sentinel, toolbar);
    var observer = new IntersectionObserver(
        function(entries) { toolbar.classList.toggle('is-sticky', !entries[0].isIntersecting); },
        { rootMargin: '-85px 0px 0px 0px', threshold: 0 }
    );
    observer.observe(sentinel);
    var mq = window.matchMedia('(max-width: 767px)');
    function updateRootMargin(e) {
        observer.disconnect();
        var offset = e.matches ? '-63px' : '-85px';
        observer = new IntersectionObserver(
            function(entries) { toolbar.classList.toggle('is-sticky', !entries[0].isIntersecting); },
            { rootMargin: offset + ' 0px 0px 0px', threshold: 0 }
        );
        observer.observe(sentinel);
    }
    mq.addEventListener('change', updateRootMargin);
})();