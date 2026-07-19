/* ============================================================
   static/js/base.js
   【対象ページ】 全ページ共通（base.html の末尾で読み込み）
   ============================================================
   【外部ファイル化の背景（improvement.md 第2版 項目 A-6）】
   以前この内容は base.html の <script> にインラインで直書きされていた。
   インライン JS は外部ファイルと違ってブラウザキャッシュが効かず、
   全ページの HTML に毎回まるごと含まれるため、記事一覧などの
   HTML サイズを常時押し上げていた。

   外部ファイル化することで、2 回目以降のページ表示では
   このファイルはキャッシュから読み込まれ、HTML の転送量が減る。
   ロジック自体は base.html にあったものを一切変えずに移設している。

   【含まれる機能】
     [1] ダークモード切り替え（🌙 / ☀️ ボタン）
     [2] スマホ用ドロワーナビの開閉
     [3] スクロール連動ヘッダーの表示 / 非表示

   ※ <head> の「ダークモード初期化スクリプト」（data-theme の初期設定）は
     描画前に実行しないとチラつき（FOUC）が起きるため、
     このファイルには移さず base.html にインラインのまま残している。

   【読み込み方法】
     base.html の </body> 直前で
       <script src="{{ static_url('js/base.js') }}"></script>
     として読み込む。<body> 末尾で実行されるため DOM は構築済み。
   ============================================================ */

/* ============================================================
   [1] ダークモード切り替え
   ============================================================
   - クリックで <html> の data-theme を light / dark で切り替える
   - 選択内容は localStorage に保存し、次回訪問時も維持する
   - ボタンのアイコン（🌙 / ☀️）と aria-label を状態に合わせて更新
   ※ 初期テーマ自体は <head> のインラインスクリプトで
     描画前に設定済み（チラつき防止）。ここではその後の
     切り替え操作とアイコン同期のみを担当する。
   ============================================================ */
(function () {
    const toggleBtn = document.getElementById('themeToggleBtn');
    if (!toggleBtn) return;
    const icon = toggleBtn.querySelector('.theme-toggle-icon');

    function syncButton() {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        // ライト時は「これから暗くする」意味で🌙、ダーク時は☀️を表示
        if (icon) icon.textContent = isDark ? '☀️' : '🌙';
        toggleBtn.setAttribute('aria-label', isDark ? 'ライトモードに切り替え' : 'ダークモードに切り替え');
        toggleBtn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    }

    // ページ表示時点の状態にアイコンを合わせる
    syncButton();

    toggleBtn.addEventListener('click', function () {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const next = isDark ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem('theme', next); } catch (e) {}
        syncButton();
    });
})();


/* ============================================================
   [2] ドロワーナビ（スマホ）の開閉
   ============================================================
   ※ navDrawer は下の [3] スクロール連動ヘッダーからも参照するため、
     IIFE で包まずファイルスコープ（トップレベル）に置いている。
     （インライン時代と同じ構造をそのまま維持）
   ============================================================ */
const hamburgerBtn = document.getElementById('hamburgerBtn');
const navOverlay   = document.getElementById('navOverlay');
const navDrawer    = document.getElementById('navDrawer');
const navCloseBtn  = document.getElementById('navCloseBtn');

function openDrawer() {
    navDrawer.classList.add('open');
    navOverlay.classList.add('open');
    navDrawer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
}

function closeDrawer() {
    navDrawer.classList.remove('open');
    navOverlay.classList.remove('open');
    navDrawer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

hamburgerBtn.addEventListener('click', openDrawer);
navCloseBtn.addEventListener('click', closeDrawer);
navOverlay.addEventListener('click', closeDrawer);

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
});


/* ============================================================
   [3] スクロール連動ヘッダー表示 / 非表示
   ============================================================
   動作仕様:
     - ページ最上部付近（scrollY < THRESHOLD）: 常に表示
     - 下スクロール: ヘッダーを画面外（上方向）へスライドアウト
     - 上スクロール: ヘッダーをスライドインして再表示

   実装のポイント:
     1. requestAnimationFrame でバッチ処理し、scroll イベントの
        連続発火による過剰な DOM 操作（リフロー）を防ぐ。
     2. ドロワーが開いているときは非表示にしない
        （メニュー操作中にヘッダーが消えると UX が悪い）。
     3. THRESHOLD を設けることで、ページ最上部で微妙に
        上下した際にヘッダーが点滅するのを防ぐ。
   ============================================================ */
(function () {
    const header    = document.getElementById('mainHeader');
    const THRESHOLD = 80;
    const DELTA     = 5;

    let lastScrollY  = window.scrollY;
    let ticking      = false;

    function updateHeader() {
        const currentScrollY = window.scrollY;
        const diff           = currentScrollY - lastScrollY;

        if (currentScrollY <= THRESHOLD) {
            // ページ最上部付近 → 必ず表示
            header.classList.remove('header-hidden');
        } else if (Math.abs(diff) >= DELTA) {
            // DELTA 以上の変化があったときだけ方向を判定する
            if (diff > 0) {
                // 下スクロール → 非表示
                // ただしドロワーが開いているときは操作を邪魔しないよう維持
                if (!navDrawer.classList.contains('open')) {
                    header.classList.add('header-hidden');
                }
            } else {
                // 上スクロール → 再表示
                header.classList.remove('header-hidden');
            }
        }

        lastScrollY = currentScrollY;
        ticking     = false;
    }

    window.addEventListener('scroll', function () {
        // rAF がまだ予約されていなければ新たに予約する
        // これにより 1 フレームに最大 1 回だけ updateHeader() が走る
        if (!ticking) {
            requestAnimationFrame(updateHeader);
            ticking = true;
        }
    }, { passive: true });
})();