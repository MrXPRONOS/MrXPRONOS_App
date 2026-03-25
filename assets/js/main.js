/**
 * main.js - Mr XPRONOS
 * Version stable + SEO amélioré (slug articles + metas dynamiques)
 */

if (location.hostname !== 'localhost' && !location.hostname.includes('127.0.0.1')) {
    console.log = () => {};
    console.warn = () => {};
}

let supabase = null;
let supabaseAvailable = false;
let supabaseConfig = { url: '', anonKey: '' };

let allData = null;
let currentCategory = 'simple';
let currentSubcat = 'pronostics';
let currentDay = 'today';
let filteredMatchesWithoutSearch = [];
let searchTerm = '';
let usingCachedData = false;

let deferredPrompt = null;
let onlineChannel = null;
let pendingShare = null;
let generatedContentPromise = null;

const activeChannels = new Set();

const shareLimits = { pro: 3, vip: 5 };

const BASE_SITE_URL = 'https://mrxpronos.github.io/MrXPRONOS_App/';

const POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
];

const DOM = {
    matches: null,
    sharePopup: null,
    vipLockedOverlay: null,
    bookmakersFooter: null,
    bookmakersBonus: null,
    vipSubtabs: null,
    usersCount: null,
    onlineCount: null,
    sharesCount: null,
    winsCount: null,
    successFill: null,
    successPercent: null,
    shareCounter: null,
    winsTrack: null,
    testimonials: null,
    todayPicks: null,
    searchInput: null,
    historyContainer: null,
    bonusSelect: null,
    bonusGrid: null,
    bonusThumbnails: null,
    bonusModal: null,
    articleModal: null,
    conseilModal: null,
    newsModal: null,
    winPopup: null,
    iosGuidePopup: null,
    installButton: null,
    blogList: null,
    blogPost: null,
    conseilsList: null,
    infosList: null,
    footNewsContainer: null,
    successRateContainer: null
};

function qs(sel, root = document) {
    return root.querySelector(sel);
}

function qsa(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
}

function initDOM() {
    DOM.matches = document.getElementById('matches-container');
    DOM.sharePopup = document.getElementById('share-popup');
    DOM.vipLockedOverlay = document.getElementById('vip-locked-overlay');
    DOM.bookmakersFooter = document.getElementById('bookmakers-footer');
    DOM.bookmakersBonus = document.getElementById('bookmakers-bonus');
    DOM.vipSubtabs = document.getElementById('vip-subtabs');
    DOM.usersCount = document.getElementById('total-users-count');
    DOM.onlineCount = document.getElementById('online-users-count');
    DOM.sharesCount = document.getElementById('total-shares-count');
    DOM.winsCount = document.getElementById('wins-count');
    DOM.successFill = document.getElementById('success-fill');
    DOM.successPercent = document.getElementById('success-percent');
    DOM.shareCounter = document.getElementById('share-counter');
    DOM.winsTrack = document.getElementById('wins-track');
    DOM.testimonials = document.getElementById('testimonials-container');
    DOM.todayPicks = document.getElementById('today-picks');
    DOM.searchInput = document.getElementById('search-input');
    DOM.historyContainer = document.getElementById('history-container');
    DOM.bonusSelect = document.getElementById('bonus-bookmaker-select');
    DOM.bonusGrid = document.getElementById('bonus-grid');
    DOM.bonusThumbnails = document.getElementById('bonus-thumbnails');
    DOM.bonusModal = document.getElementById('bonus-modal');
    DOM.articleModal = document.getElementById('article-modal');
    DOM.conseilModal = document.getElementById('conseil-modal');
    DOM.newsModal = document.getElementById('news-modal');
    DOM.winPopup = document.getElementById('win-popup');
    DOM.iosGuidePopup = document.getElementById('ios-guide-popup');
    DOM.installButton = document.getElementById('install-app');
    DOM.blogList = document.getElementById('blog-list');

    // article.html utilise #blog-post
    DOM.blogPost =
        document.getElementById('blog-post') ||
        document.getElementById('blog-post-content') ||
        document.getElementById('article-page-content');

    DOM.conseilsList = document.getElementById('conseils-list');
    DOM.infosList = document.getElementById('infos-list');
    DOM.footNewsContainer = document.getElementById('foot-news-container');
    DOM.successRateContainer = document.getElementById('success-rate-container');
}

/* =======================================================
   SECURITY
   ======================================================= */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function escapeAttribute(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function stripMarkdown(text = '') {
    return String(text)
        .replace(/#+\s*/g, '')
        .replace(/\*\*/g, '')
        .replace(/\*/g, '')
        .replace(/`/g, '')
        .replace(/\[|\]/g, '')
        .trim();
}

function sanitizeHtml(unsafeHtml = '') {
    const template = document.createElement('template');
    template.innerHTML = unsafeHtml;

    const allowedTags = new Set([
        'div', 'p', 'br', 'strong', 'em', 'b', 'i', 'u',
        'ul', 'ol', 'li', 'blockquote', 'code', 'pre',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'a', 'img', 'span', 'hr'
    ]);

    const allowedAttrs = {
        '*': new Set(['class']),
        a: new Set(['href', 'target', 'rel']),
        img: new Set(['src', 'alt', 'loading', 'decoding'])
    };

    const cleanNode = (node) => {
        [...node.childNodes].forEach(child => {
            if (child.nodeType === Node.COMMENT_NODE) {
                child.remove();
                return;
            }

            if (child.nodeType !== Node.ELEMENT_NODE) return;

            const tag = child.tagName.toLowerCase();

            if (!allowedTags.has(tag)) {
                const fragment = document.createDocumentFragment();
                while (child.firstChild) fragment.appendChild(child.firstChild);
                child.replaceWith(fragment);
                cleanNode(node);
                return;
            }

            [...child.attributes].forEach(attr => {
                const name = attr.name.toLowerCase();
                const value = attr.value || '';
                const isAllowed =
                    (allowedAttrs[tag] && allowedAttrs[tag].has(name)) ||
                    (allowedAttrs['*'] && allowedAttrs['*'].has(name));

                if (name.startsWith('on') || !isAllowed) {
                    child.removeAttribute(attr.name);
                    return;
                }

                if ((name === 'href' || name === 'src') && /^\s*javascript:/i.test(value)) {
                    child.removeAttribute(attr.name);
                    return;
                }

                if (tag === 'a' && name === 'href') {
                    child.setAttribute('target', '_blank');
                    child.setAttribute('rel', 'noopener noreferrer');
                }
            });

            cleanNode(child);
        });
    };

    cleanNode(template.content);
    return template.innerHTML;
}

function renderSafeRichContent(content = '') {
    try {
        if (window.marked) {
            return sanitizeHtml(window.marked.parse(String(content)));
        }
    } catch (e) {
        console.error('Erreur marked:', e);
    }
    return sanitizeHtml(escapeHtml(String(content)).replace(/\n/g, '<br>'));
}

/* =======================================================
   UTILS
   ======================================================= */
function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        font-weight: 600;
        max-width: 90vw;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), duration);
}

function toFloatSafe(value, defaultValue = null) {
    const n = Number(value);
    return Number.isFinite(n) ? n : defaultValue;
}

function safeJsonParse(value, fallback = null) {
    try { return JSON.parse(value); } catch { return fallback; }
}

function getUserId() {
    let userId = localStorage.getItem('mx_user_id');
    if (!userId) {
        try { userId = 'MX-' + crypto.randomUUID(); }
        catch { userId = 'MX-' + Date.now().toString(36) + Math.random().toString(36).slice(2); }
        localStorage.setItem('mx_user_id', userId);
    }
    return userId;
}
window.getUserId = getUserId;

function isFinishedMatch(match) {
    if (!match) return false;
    if (match.is_finished === true) return true;
    const status = (match.status || '').toLowerCase();
    return status.includes('finished') || status.includes('terminé') || status.includes('ended') || status.includes('ft');
}

function getTodayString() {
    return new Date().toDateString();
}

function cleanupChannels() {
    activeChannels.forEach(channel => {
        try {
            channel.unsubscribe?.();
            if (supabaseAvailable && supabase?.removeChannel) supabase.removeChannel(channel);
        } catch (e) {}
    });
    activeChannels.clear();
}
window.addEventListener('beforeunload', cleanupChannels);

/* =======================================================
   PAGE DETECTION
   ======================================================= */
function detectPage() {
    if (DOM.matches) return 'pronos';
    if (DOM.historyContainer) return 'history';
    if (DOM.blogList) return 'blog-list';
    if (DOM.blogPost) return 'blog-post';
    if (DOM.conseilsList) return 'conseils';
    if (DOM.bonusSelect || DOM.bonusGrid || DOM.bonusThumbnails) return 'bonus';
    if (DOM.footNewsContainer) return 'infos';
    if (DOM.todayPicks || DOM.testimonials) return 'home';
    return 'generic';
}

/* =======================================================
   SUPABASE
   ======================================================= */
async function initSupabase() {
    const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout Supabase')), 5000));

    try {
        const initPromise = (async () => {
            const { supabaseUrl, supabaseAnonKey } = await import('./config.js');

            if (!supabaseUrl || !supabaseUrl.startsWith('https://')) throw new Error('URL Supabase invalide');
            if (!supabaseAnonKey) throw new Error('Clé Supabase manquante');

            supabaseConfig.url = supabaseUrl;
            supabaseConfig.anonKey = supabaseAnonKey;

            const { createClient } = await import('https://esm.sh/@supabase/supabase-js@2');
            supabase = createClient(supabaseUrl, supabaseAnonKey);
            supabaseAvailable = true;
            console.log('✅ Supabase connecté');
        })();

        await Promise.race([initPromise, timeout]);
    } catch (error) {
        console.warn('⚠️ Supabase non configuré:', error.message);
        supabaseAvailable = false;
    }
}

/* =======================================================
   PUSH
   ======================================================= */
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i++) outputArray[i] = rawData.charCodeAt(i);
    return outputArray;
}

async function subscribeToPush(askPermission = false) {
    if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) return;
    if (!supabaseConfig.url) return;

    try {
        let permission = Notification.permission;
        if (permission === 'default' && askPermission) permission = await Notification.requestPermission();
        if (permission !== 'granted') return;

        const swReady = await Promise.race([
            navigator.serviceWorker.ready,
            new Promise((_, reject) => setTimeout(() => reject(new Error('SW timeout')), 5000))
        ]);

        let subscription = await swReady.pushManager.getSubscription();

        if (!subscription) {
            const keyResp = await fetch(`${supabaseConfig.url}/functions/v1/vapid-public-key`);
            if (!keyResp.ok) throw new Error('Clé VAPID non récupérée');

            const publicKey = (await keyResp.text()).trim();
            const convertedKey = urlBase64ToUint8Array(publicKey);

            subscription = await swReady.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: convertedKey
            });
        }

        const userId = getUserId();

        await fetch(`${supabaseConfig.url}/functions/v1/push-subscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, subscription })
        });
    } catch (err) {
        console.error('Erreur push:', err);
    }
}

window.enablePushNotifications = async function () {
    await subscribeToPush(true);
};

/* =======================================================
   COUNTERS / ANALYTICS
   ======================================================= */
async function incrementCounter(counterName) {
    if (!supabaseAvailable || !supabase) {
        const local = parseInt(localStorage.getItem(counterName) || '0', 10);
        localStorage.setItem(counterName, String(local + 1));
        return;
    }

    try {
        await supabase.rpc('increment_counter', { counter_name: counterName });
    } catch (e) {
        console.error('Erreur incrémentation:', e);
    }
}

async function updateDisplayedCounters() {
    if (!supabaseAvailable || !supabase) return;

    try {
        const { data, error } = await supabase
            .from('counters')
            .select('total_visits, total_shares, unique_users')
            .eq('id', 1)
            .single();

        if (error) throw error;

        if (DOM.usersCount) DOM.usersCount.textContent = ((data?.unique_users || 0)).toLocaleString() + '+';
        if (DOM.sharesCount) DOM.sharesCount.textContent = ((data?.total_shares || 0)).toLocaleString() + '+';
    } catch (e) {
        console.error('Erreur récupération counters:', e);
    }
}

function subscribeToCounters() {
    if (!supabaseAvailable || !supabase) return;

    const channel = supabase
        .channel('counters-live')
        .on(
            'postgres_changes',
            { event: 'UPDATE', schema: 'public', table: 'counters', filter: 'id=eq.1' },
            (payload) => {
                if (DOM.usersCount) DOM.usersCount.textContent = ((payload.new?.unique_users || 0)).toLocaleString() + '+';
                if (DOM.sharesCount) DOM.sharesCount.textContent = ((payload.new?.total_shares || 0)).toLocaleString() + '+';
            }
        )
        .subscribe((status) => {
            if (status === 'SUBSCRIBED') activeChannels.add(channel);
        });
}

async function recordEvent(type, page = '') {
    if (!supabaseAvailable || !supabase) return;
    const userId = getUserId();

    try {
        await supabase.from('analytics').insert({ event_type: type, user_id: userId, page });
    } catch (e) {
        console.error('Erreur analytics:', e);
    }
}

function countVisitOncePerDay() {
    const todayKey = getTodayString();
    const lastVisit = localStorage.getItem('mx_last_visit');

    if (lastVisit !== todayKey) {
        localStorage.setItem('mx_last_visit', todayKey);
        incrementCounter('total_visits');
        recordEvent('visit', window.location.pathname);
    }
}

async function registerUniqueUser() {
    if (!supabaseAvailable || !supabase) return;

    const userId = getUserId();
    const registered = localStorage.getItem('mx_registered');
    if (registered) return;

    try {
        const { error } = await supabase.from('users').insert({ user_id: userId });
        if (!error) await supabase.rpc('increment_counter', { counter_name: 'unique_users' });
        localStorage.setItem('mx_registered', 'true');
    } catch (e) {
        console.error('Erreur enregistrement user:', e);
    }
}

async function initOnlineUsers() {
    if (!supabaseAvailable || !supabase || !DOM.onlineCount) return;

    if (onlineChannel) {
        try {
            onlineChannel.unsubscribe();
            supabase.removeChannel?.(onlineChannel);
        } catch {}
    }

    onlineChannel = supabase.channel('online-users', {
        config: { presence: { key: getUserId() } }
    });

    onlineChannel
        .on('presence', { event: 'sync' }, () => {
            const state = onlineChannel.presenceState();
            const onlineUsers = Object.keys(state).length;
            if (DOM.onlineCount) DOM.onlineCount.textContent = onlineUsers;
        })
        .subscribe(async (status) => {
            if (status === 'SUBSCRIBED') {
                try {
                    await onlineChannel.track({ online_at: new Date().toISOString() });
                    activeChannels.add(onlineChannel);
                } catch (e) {}
            }
        });
}

/* =======================================================
   PWA
   ======================================================= */
function getOS() {
    const ua = window.navigator.userAgent;
    if (/iPad|iPhone|iPod/.test(ua)) return 'iOS';
    if (/Android/.test(ua)) return 'Android';
    return 'Other';
}

function isPwaInstalled() {
    return window.matchMedia('(display-mode: standalone)').matches ||
        window.navigator.standalone === true;
}

function showIosGuideIfNeeded() {
    if (getOS() === 'iOS' && !isPwaInstalled()) {
        const lastClosed = localStorage.getItem('iosGuideLastClosed');
        if (lastClosed) {
            const hoursSince = (Date.now() - parseInt(lastClosed, 10)) / (1000 * 60 * 60);
            if (hoursSince < 24) return;
        }
        if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = 'flex';
    }
}

function closeIosGuide() {
    if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = 'none';
    localStorage.setItem('iosGuideLastClosed', String(Date.now()));
}

function setupInstallButton() {
    if (!DOM.installButton) return;

    DOM.installButton.addEventListener('click', async () => {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            await deferredPrompt.userChoice;
            deferredPrompt = null;
            DOM.installButton.style.display = 'none';
        } else {
            if (getOS() === 'iOS') showIosGuideIfNeeded();
            else alert("Utilisez le menu du navigateur pour ajouter l'application à l'écran d'accueil.");
        }
    });
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (DOM.installButton && !isPwaInstalled()) DOM.installButton.style.display = 'inline-block';
});

window.addEventListener('appinstalled', () => {
    if (DOM.installButton) DOM.installButton.style.display = 'none';
    if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = 'none';
});

/* =======================================================
   SHARE / VIP
   ======================================================= */
function getDailyShareCount() {
    const lastReset = localStorage.getItem('shareLastReset');
    const todayKey = getTodayString();

    if (lastReset !== todayKey) {
        localStorage.setItem('shareLastReset', todayKey);
        localStorage.setItem('shareCount', '0');
        return 0;
    }
    return parseInt(localStorage.getItem('shareCount') || '0', 10);
}

function incrementShareCount() {
    const current = getDailyShareCount();
    const next = current + 1;
    localStorage.setItem('shareCount', String(next));
    return next;
}

function updateShareCounter() {
    if (DOM.shareCounter) {
        DOM.shareCounter.textContent = `🔥 ${getDailyShareCount()} partages aujourd'hui`;
    }
}

function startShareTracking({ countForUnlock = true, category = currentCategory } = {}) {
    pendingShare = {
        startedAt: Date.now(),
        countForUnlock,
        category,
        finalized: false
    };
    setTimeout(() => finalizePendingShare(true), 5500);
}

function finalizePendingShare(force = false) {
    if (!pendingShare || pendingShare.finalized) return;

    const elapsed = Date.now() - pendingShare.startedAt;
    if (!force && elapsed < 5000) return;

    pendingShare.finalized = true;
    const ctx = pendingShare;
    pendingShare = null;

    if (ctx.countForUnlock) {
        const newCount = incrementShareCount();
        updateShareCounter();
        updateLockedStateForCategory(ctx.category, newCount);
    }

    incrementCounter('total_shares');
    recordEvent('share', window.location.pathname);
}

document.addEventListener('visibilitychange', () => {
    if (!document.hidden) finalizePendingShare(false);
});

function updateLockedStateForCategory(category, newCount) {
    const target = shareLimits[category];
    if (!target) return;

    if (newCount >= target) {
        hideVipLocked();
        filterAndDisplay();
    } else {
        if (DOM.vipLockedOverlay && DOM.vipLockedOverlay.style.display === 'flex') {
            showVipLocked(category);
        } else {
            showSharePopup(category, target - newCount);
        }
    }
}

function openShareWindow(url) {
    return !!window.open(url, '_blank', 'noopener,noreferrer');
}

function share(platform) {
    const message = `🔥 PRONOSTICS FOOTBALL GRATUITS😱

Je viens de découvrir ce site ⚽

Ils donnent :
🎯 80% de précision
🎯 80% des coupons gagnant chaque jour
🎯 statistiques + analyse
🎯 pronostics fiables

👇 Accède aux matchs du jour :
${BASE_SITE_URL}

💰 Très utile pour les paris sportifs !`;

    const url = platform === 'whatsapp'
        ? `https://wa.me/?text=${encodeURIComponent(message)}`
        : `https://t.me/share/url?url=${encodeURIComponent(BASE_SITE_URL)}&text=${encodeURIComponent(message)}`;

    openShareWindow(url);
    startShareTracking({ countForUnlock: true, category: currentCategory });
}

function sharePronostic(match) {
    if (!match || !match.prediction) return;

    const msg = `🔥 PRONOSTICS FOOTBALL GRATUITS

⚽ ${match.home_team} vs ${match.away_team}
📈 Double chance : ${match.prediction.double_chance} – Fiabilité ${match.prediction.confidence}%

👇 Analyse complète :
${BASE_SITE_URL}

💰 Rejoins les gagnants !`;

    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(msg)}`;
    const telegramUrl = `https://t.me/share/url?url=${encodeURIComponent(BASE_SITE_URL)}&text=${encodeURIComponent(msg)}`;

    const useWhatsapp = confirm("Partager sur WhatsApp ? (OK = WhatsApp, Annuler = Telegram)");
    openShareWindow(useWhatsapp ? whatsappUrl : telegramUrl);

    recordEvent('click_pronostic', window.location.pathname);
    startShareTracking({ countForUnlock: false, category: currentCategory });
}

function ensureVipOverlayStructure() {
    if (!DOM.vipLockedOverlay) return;

    if (DOM.vipLockedOverlay.children.length === 0) {
        DOM.vipLockedOverlay.innerHTML = `
            <div class="vip-locked-content">
                <div class="lock-icon">🔒</div>
                <h3></h3>
                <p></p>
                <div class="share-buttons vip-contact-buttons" style="display:flex; gap:10px; justify-content:center; margin:20px 0;">
                    <button id="share-wa-locked" class="btn btn-primary">WhatsApp</button>
                    <button id="share-tg-locked" class="btn btn-primary">Telegram</button>
                </div>
                <p>Partages actuels : <span id="share-count-locked">0</span>/<span id="share-target-locked">3</span></p>
                <button id="close-locked" class="btn btn-secondary">Fermer</button>
            </div>
        `;

        document.getElementById('share-wa-locked')?.addEventListener('click', () => share('whatsapp'));
        document.getElementById('share-tg-locked')?.addEventListener('click', () => share('telegram'));
        document.getElementById('close-locked')?.addEventListener('click', () => {
            DOM.vipLockedOverlay.style.display = 'none';
            if (DOM.matches) DOM.matches.style.display = 'grid';
        });
    }
}

function showVipLocked(category) {
    const target = shareLimits[category];
    const shareCount = getDailyShareCount();
    const remaining = Math.max(0, target - shareCount);

    if (DOM.vipLockedOverlay) {
        ensureVipOverlayStructure();

        const titleEl = DOM.vipLockedOverlay.querySelector('h3');
        const textEl = DOM.vipLockedOverlay.querySelector('p');
        const shareCountEl = document.getElementById('share-count-locked');
        const shareTargetEl = document.getElementById('share-target-locked');

        if (titleEl) titleEl.textContent = `🔒 ${category === 'pro' ? 'Pronostics Pro' : 'Pronostics VIP'} verrouillés`;
        if (textEl) textEl.innerHTML = `Partagez ce lien à <strong>${remaining}</strong> ami(s) pour débloquer.`;
        if (shareCountEl) shareCountEl.textContent = String(shareCount);
        if (shareTargetEl) shareTargetEl.textContent = String(target);

        DOM.vipLockedOverlay.style.display = 'flex';
        if (DOM.matches) DOM.matches.style.display = 'none';
    } else {
        showSharePopup(category, remaining);
    }
}

function hideVipLocked() {
    if (DOM.vipLockedOverlay) {
        DOM.vipLockedOverlay.style.display = 'none';
        if (DOM.matches) DOM.matches.style.display = 'grid';
    }
}

function showSharePopup(category, remaining) {
    if (!DOM.sharePopup) createSharePopup();

    const shareCount = getDailyShareCount();
    const currentEl = document.getElementById('share-current');
    const targetEl = document.getElementById('share-target');
    const messageEl = document.getElementById('share-message');

    if (currentEl) currentEl.textContent = String(shareCount);
    if (targetEl) targetEl.textContent = String(shareLimits[category] || 0);
    if (messageEl) {
        messageEl.innerHTML = `Pour accéder aux pronostics ${category === 'pro' ? 'Pro' : 'VIP'}, partagez ce lien à <span id="share-remaining">${remaining}</span> amis sur WhatsApp ou Telegram.`;
    }

    DOM.sharePopup.classList.add('active');
}

function createSharePopup() {
    const popup = document.createElement('div');
    popup.id = 'share-popup';
    popup.className = 'popup';
    popup.innerHTML = `
        <div class="popup-content">
            <h3>🔒 Contenu premium</h3>
            <p id="share-message">Pour accéder aux pronostics Pro, partagez ce lien à <span id="share-remaining">3</span> amis sur WhatsApp ou Telegram.</p>
            <div class="share-buttons">
                <button id="share-wa" class="btn btn-primary">WhatsApp</button>
                <button id="share-tg" class="btn btn-primary">Telegram</button>
            </div>
            <p>Partages actuels : <span id="share-current">0</span>/<span id="share-target">3</span></p>
            <button id="close-popup" class="btn btn-secondary">Fermer</button>
        </div>
    `;
    document.body.appendChild(popup);
    DOM.sharePopup = popup;

    document.getElementById('share-wa')?.addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg')?.addEventListener('click', () => share('telegram'));
    document.getElementById('close-popup')?.addEventListener('click', () => DOM.sharePopup?.classList.remove('active'));
}

async function checkVipStatus() {
    if (!supabaseAvailable || !supabase) return false;

    const userId = getUserId();
    const storedCode = localStorage.getItem('mx_vip_code');
    if (!storedCode) return false;

    try {
        const { data, error } = await supabase.rpc('check_vip_code', {
            p_user_id: userId,
            p_code: storedCode
        });

        if (error) throw error;
        if (Array.isArray(data)) return data[0]?.valid === true;
        if (typeof data === 'boolean') return data;
        return data?.valid === true;
    } catch (e) {
        console.error('Erreur vérification VIP:', e);
        return false;
    }
}

function showVipLoginForm(container) {
    const userId = getUserId();
    const encodedUserId = encodeURIComponent(userId);

    container.innerHTML = `
        <div class="vip-locked-content" style="display:block;">
            <div class="lock-icon">💎</div>
            <h3>🔐 Accès VIP Payant</h3>
            <p><strong>Votre ID :</strong> ${escapeHtml(userId)}</p>
            <p>Pour obtenir un code VIP (5000 FCFA/mois), contactez-nous sur WhatsApp ou Telegram avec votre ID.</p>
            <div class="vip-contact-buttons" style="display:flex; gap:10px; justify-content:center; margin:20px 0;">
                <a href="https://wa.me/22899201444?text=Bonjour%2C%20voici%20mon%20ID%20VIP%20${encodedUserId}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">WhatsApp</a>
                <a href="https://t.me/mr_xpronos?text=Bonjour%2C%20voici%20mon%20ID%20VIP%20${encodedUserId}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Telegram</a>
            </div>
            <hr style="border-color:#444; margin:20px 0;">
            <p>Si vous avez déjà un code, saisissez-le ci-dessous :</p>
            <input type="text" id="vip-code-input" placeholder="Code VIP" style="width:100%; padding:10px; margin-bottom:10px; border-radius:8px; border:1px solid #D4AF37; background:#0D0D0D; color:#fff;">
            <button id="vip-activate-btn" class="btn btn-primary" style="width:100%;">Activer</button>
            <button id="vip-close-btn" class="btn btn-secondary" style="width:100%; margin-top:10px;">Fermer</button>
        </div>
    `;

    document.getElementById('vip-activate-btn')?.addEventListener('click', async () => {
        const codeInput = document.getElementById('vip-code-input');
        if (!codeInput) return;

        const code = codeInput.value.trim();
        if (!code) return alert('Veuillez entrer un code.');

        const uid = getUserId();

        try {
            const { data, error } = await supabase.rpc('check_vip_code', {
                p_user_id: uid,
                p_code: code
            });

            const valid = Array.isArray(data) ? data[0]?.valid === true : (data?.valid === true || data === true);
            if (error || !valid) throw new Error('Code invalide');

            localStorage.setItem('mx_vip_code', code);
            recordEvent('vip_conversion', window.location.pathname);
            showToast('Code VIP activé avec succès !', 'success');
            window.location.reload();
        } catch {
            alert('Code invalide ou expiré.');
        }
    });

    document.getElementById('vip-close-btn')?.addEventListener('click', () => {
        container.style.display = 'none';
        if (DOM.matches) DOM.matches.style.display = 'grid';
    });
}

window.handleVipMenuClick = async function () {
    const isVip = await checkVipStatus();
    if (isVip) {
        window.location.href = `${BASE_SITE_URL}live.html`;
    } else {
        if (DOM.vipLockedOverlay) {
            ensureVipOverlayStructure();
            showVipLoginForm(DOM.vipLockedOverlay);
            DOM.vipLockedOverlay.style.display = 'flex';
            if (DOM.matches) DOM.matches.style.display = 'none';
        } else {
            alert('Accès VIP payant. Contactez-nous sur WhatsApp ou Telegram.');
        }
    }
};
window.handleVipClick = window.handleVipMenuClick;

/* =======================================================
   DATA LOADING
   ======================================================= */
async function fetchJsonWithCache(url, cacheKey, timeoutMs = 8000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const resp = await fetch(url, { signal: controller.signal, cache: 'no-cache' });
        clearTimeout(timeoutId);

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const data = await resp.json();
        localStorage.setItem(cacheKey, JSON.stringify(data));
        return { data, fromCache: false };
    } catch {
        clearTimeout(timeoutId);
        const cached = localStorage.getItem(cacheKey);
        if (cached) return { data: safeJsonParse(cached, null), fromCache: true };
        return { data: null, fromCache: false };
    }
}

async function loadData() {
    const { data, fromCache } = await fetchJsonWithCache(`data.json?t=${Date.now()}`, 'cachedData', 8000);
    usingCachedData = fromCache;
    allData = data;

    if (!allData) {
        if (DOM.matches) DOM.matches.innerHTML = `<div class="error">❌ Aucune donnée disponible.</div>`;
        return;
    }

    renderBookmakers(allData.bookmakers);
    hideEmptyTabs();
    maybeHideTabBar();
    filterAndDisplay();
    updatePronosticsSuccessRate();
}

async function loadDataGeneric() {
    const { data, fromCache } = await fetchJsonWithCache(`data.json?t=${Date.now()}`, 'cachedData', 8000);
    usingCachedData = fromCache;
    return data;
}

/* =======================================================
   BOOKMAKERS
   ======================================================= */
function renderBookmakers(bookmakers) {
    const defaultBookmakers = [
        { name: "1xBet", logo: "assets/images/1xbet.webp", url: "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599" },
        { name: "1win", logo: "assets/images/1win.webp", url: "https://1wrbgb.com/?open=register&p=qqcw" },
        { name: "Betwinner", logo: "assets/images/betwinner.webp", url: "https://bwredir.com/299Y" },
        { name: "Melbet", logo: "assets/images/melbet.webp", url: "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041" },
        { name: "Linebet", logo: "assets/images/linebet.webp", url: "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611" },
        { name: "BetClic", logo: "assets/images/betclic.webp", url: "https://betpari-click.com/2vY0?extid=USD" }
    ];

    const items = Array.isArray(bookmakers) && bookmakers.length ? bookmakers : defaultBookmakers;

    if (DOM.bookmakersFooter) {
        DOM.bookmakersFooter.innerHTML = '';
        items.forEach(b => {
            const a = document.createElement('a');
            a.href = b.url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';

            const img = document.createElement('img');
            img.src = b.logo;
            img.alt = b.name;
            img.loading = 'lazy';
            img.decoding = 'async';
            img.style.maxHeight = '40px';

            img.onerror = function () {
                this.style.display = 'none';
                const span = document.createElement('span');
                span.textContent = b.name;
                span.style.color = 'var(--or)';
                span.style.fontWeight = '600';
                span.style.fontSize = '0.8rem';
                a.appendChild(span);
            };

            a.appendChild(img);
            DOM.bookmakersFooter.appendChild(a);
        });
    }

    if (DOM.bookmakersBonus) {
        DOM.bookmakersBonus.innerHTML = '';
        items.forEach(b => {
            const div = document.createElement('div');
            div.className = 'bookmaker-card';
            div.innerHTML = `
                <img src="${escapeAttribute(b.logo)}" alt="${escapeAttribute(b.name)}" loading="lazy" decoding="async">
                <h3>${escapeHtml(b.name)}</h3>
                <p>Bonus de bienvenue jusqu'à 130€</p>
                <a href="${escapeAttribute(b.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">S'inscrire avec XPVIP</a>
            `;
            DOM.bookmakersBonus.appendChild(div);
        });
    }
}

/* =======================================================
   PRONOS PAGE
   ======================================================= */
function getLocalDateString(day) {
    const now = new Date();
    const target = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    if (day === 'tomorrow') target.setUTCDate(target.getUTCDate() + 1);
    else if (day === 'yesterday') target.setUTCDate(target.getUTCDate() - 1);

    const y = target.getUTCFullYear();
    const m = String(target.getUTCMonth() + 1).padStart(2, '0');
    const d = String(target.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function getLocalDateFromEvent(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    if (isNaN(date)) return null;
    const y = date.getUTCFullYear();
    const m = String(date.getUTCMonth() + 1).padStart(2, '0');
    const d = String(date.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function sortMatchesByLeague(matches) {
    return matches.sort((a, b) => {
        const leagueA = a.league || '';
        const leagueB = b.league || '';

        const indexA = POPULAR_LEAGUES.findIndex(l => leagueA.includes(l) || leagueA === l);
        const indexB = POPULAR_LEAGUES.findIndex(l => leagueB.includes(l) || leagueB === l);

        const rankA = indexA === -1 ? 999 : indexA;
        const rankB = indexB === -1 ? 999 : indexB;

        if (rankA !== rankB) return rankA - rankB;
        return new Date(a.event_date || 0) - new Date(b.event_date || 0);
    });
}

function translateStatus(status) {
    if (!status) return 'À venir';
    const s = String(status).toLowerCase();

    if (s.includes('finished') || s.includes('terminé') || s.includes('ended')) return 'Terminé';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'En cours';
    if (s.includes('notstarted') || s.includes('à venir')) return 'À venir';
    if (s.includes('postponed')) return 'Reporté';
    if (s.includes('cancelled')) return 'Annulé';

    return escapeHtml(status);
}

function getStatusClass(status) {
    if (!status) return '';
    const s = String(status).toLowerCase();
    if (s.includes('finished') || s.includes('terminé') || s.includes('ended')) return 'finished';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'live';
    return '';
}

function formatMatchTime(isoString) {
    if (!isoString) return 'Horaire inconnu';
    const date = new Date(isoString);
    if (isNaN(date)) return 'Horaire inconnu';
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function getTeamLogoPath(teamName, isHome = true) {
    if (!teamName) return isHome ? 'assets/images/home.webp' : 'assets/images/away.webp';
    const normalized = String(teamName).toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-]/g, '');
    return `assets/images/${normalized}.webp`;
}

function hideEmptyTabs() {
    const vipEnabled = localStorage.getItem('vipEnabled') !== 'false';
    const counts = { simple: 0, pro: 0, vip: 0 };

    if (allData?.matches) {
        allData.matches.forEach(m => {
            if (counts[m.category] !== undefined) counts[m.category]++;
        });
    }

    qsa('.tab-btn').forEach(btn => {
        const cat = btn.dataset.cat;
        if (cat === 'vip' && !vipEnabled) btn.style.display = 'none';
        else if (cat === 'pro' || cat === 'vip') btn.style.display = 'inline-block';
        else btn.style.display = counts[cat] > 0 ? 'inline-block' : 'none';
    });

    if (DOM.vipSubtabs) DOM.vipSubtabs.style.display = vipEnabled ? 'flex' : 'none';
}

function maybeHideTabBar() {
    const tabBar = qs('.category-tabs');
    if (!tabBar) return;

    const visibleTabs = qsa('.tab-btn', tabBar).filter(btn => btn.style.display !== 'none');
    tabBar.style.display = visibleTabs.length === 0 ? 'none' : 'grid';
}

function filterAndDisplay() {
    if (!allData || !Array.isArray(allData.matches) || !DOM.matches) {
        if (DOM.matches) DOM.matches.innerHTML = '<div class="no-events">Aucun match disponible.</div>';
        return;
    }

    const targetDate = getLocalDateString(currentDay);
    const targetCat = (currentCategory === 'vip' && currentSubcat === 'pronostics') ? 'vip' : currentCategory;

    const filtered = allData.matches.filter(m => {
        const eventLocalDate = getLocalDateFromEvent(m.event_date);
        return m.category === targetCat && eventLocalDate === targetDate;
    });

    filteredMatchesWithoutSearch = sortMatchesByLeague(filtered);
    applySearchFilter();
}

function applySearchFilter() {
    if (!DOM.matches) return;
    if (!filteredMatchesWithoutSearch) return;

    if (!searchTerm.trim()) {
        renderMatches(filteredMatchesWithoutSearch);
        return;
    }

    const term = searchTerm.toLowerCase().trim();
    const filtered = filteredMatchesWithoutSearch.filter(m =>
        String(m.home_team || '').toLowerCase().includes(term) ||
        String(m.away_team || '').toLowerCase().includes(term) ||
        String(m.league || '').toLowerCase().includes(term)
    );

    renderMatches(filtered);
}

function renderMatches(matches) {
    if (!DOM.matches) return;

    const offlineBanner = (usingCachedData && !navigator.onLine)
        ? `<div style="background:#ffcc00; color:#000; text-align:center; padding:8px; font-weight:700; font-size:0.95rem; margin-bottom:12px;">
                📴 MODE HORS LIGNE — Pronostics chargés depuis le cache
           </div>`
        : '';

    if (!matches || matches.length === 0) {
        DOM.matches.innerHTML = `${offlineBanner}<div class="no-events">Aucun match.</div>`;
        return;
    }

    const grouped = {};
    matches.forEach(m => {
        const league = m.league || 'Autres ligues';
        if (!grouped[league]) grouped[league] = [];
        grouped[league].push(m);
    });

    let html = offlineBanner;

    const leagueOrder = [...POPULAR_LEAGUES, 'Autres ligues'];
    const sortedLeagues = Object.keys(grouped).sort((a, b) => {
        const ia = leagueOrder.findIndex(l => a.includes(l) || a === l);
        const ib = leagueOrder.findIndex(l => b.includes(l) || b === l);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    });

    sortedLeagues.forEach(league => {
        html += `<h2 class="league-header" style="color: var(--or); margin-top: 2rem;">${escapeHtml(league)}</h2>`;

        grouped[league].forEach(m => {
            const pred = m.prediction || {};
            const doubleChance = escapeHtml(pred.double_chance || 'N/A');

            // ✅ confidence fix (support 0..1 ou 0..100)
            let confidence = toFloatSafe(pred.confidence, 0) || 0;
            if (confidence <= 1) confidence = confidence * 100;
            else if (confidence > 100) confidence = confidence / 100;
            confidence = Math.min(100, Math.round(confidence * 10) / 10);

            const matchTime = formatMatchTime(m.event_date);
            const statusFr = translateStatus(m.status);
            const statusClass = getStatusClass(m.status);

            const eventDate = m.event_date ? String(m.event_date).split('T')[0] : '';
            const yesterdayStr = getLocalDateString('yesterday');
            const verifiedDouble = (eventDate === yesterdayStr && m.verified_double) ? 'checked' : '';

            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';

            const homeDefault = 'assets/images/home.webp';
            const awayDefault = 'assets/images/away.webp';
            const homeLogo = escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true));
            const awayLogo = escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false));

            const isWinner = !!m.verified_double;
            const winnerClass = isWinner ? 'winner' : '';
            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${escapeHtml(m.badge)}</span>` : '';

            const matchDataForSharing = {
                home_team: m.home_team,
                away_team: m.away_team,
                prediction: {
                    double_chance: pred.double_chance,
                    confidence: confidence
                }
            };
            const matchDataEncoded = encodeURIComponent(JSON.stringify(matchDataForSharing));

            html += `
                <div class="match-card ${winnerClass}">
                    <div class="win-effect"></div>
                    <div class="match-info">
                        <div class="teams">
                            <div class="team">
                                <img src="${homeLogo}" alt="${escapeAttribute(m.home_team)}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${homeDefault}';">
                                <span class="team-name">${escapeHtml(m.home_team)}</span>
                                <span class="team-score">${m.home_score ?? '-'}</span>
                            </div>
                            <div class="vs">VS</div>
                            <div class="team">
                                <img src="${awayLogo}" alt="${escapeAttribute(m.away_team)}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${awayDefault}';">
                                <span class="team-name">${escapeHtml(m.away_team)}</span>
                                <span class="team-score">${m.away_score ?? '-'}</span>
                            </div>
                        </div>
                        <div class="match-meta">
                            <span class="league-badge">${escapeHtml(m.league || 'Ligue')}</span>
                            <span class="status ${statusClass}">${statusFr}</span>
                            <span class="match-time"><i>🕒</i> ${matchTime}</span>
                            ${m.venue ? `<span class="match-venue"><i>🏟️</i> ${escapeHtml(m.venue)}</span>` : ''}
                        </div>
                    </div>
                    <div class="analysis-panel ticket ${winnerClass}">
                        <h4>Pronostic ${xpronosBadge}</h4>
                        <p><strong>Double chance :</strong> ${doubleChance} ${eventDate === yesterdayStr ? `<input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled>` : ''}</p>
                        <div class="confidence-bar"><div class="confidence-fill" data-value="${confidence}"></div></div>
                        <p><strong>Fiabilité :</strong> <span class="confidence-text">${confidence}%</span></p>
                        ${premiumBadge}
                        <button class="btn btn-secondary btn-share" data-match="${matchDataEncoded}">📤 Partager ce prono</button>
                    </div>
                </div>
            `;
        });
    });

    DOM.matches.innerHTML = html;

    requestAnimationFrame(() => {
        qsa('.confidence-fill').forEach(bar => {
            const value = bar.getAttribute('data-value') || '0';
            bar.style.width = value + '%';
        });
    });
}

/* =======================================================
   HISTORY PAGE
   ======================================================= */
async function displayHistory() {
    if (!DOM.historyContainer) return;

    allData = await loadDataGeneric();

    if (!allData || !Array.isArray(allData.matches)) {
        DOM.historyContainer.innerHTML = '<div class="no-events">Aucun historique disponible.</div>';
        return;
    }

    const todayStr = getLocalDateString('today');
    const historyMatches = allData.matches.filter(m => {
        const d = getLocalDateFromEvent(m.event_date);
        return d && d < todayStr;
    });

    if (!historyMatches.length) {
        DOM.historyContainer.innerHTML = '<div class="no-events">Aucun match dans cette période.</div>';
        return;
    }

    const groupedByDay = {};
    historyMatches.forEach(m => {
        const dateStr = getLocalDateFromEvent(m.event_date);
        if (!groupedByDay[dateStr]) groupedByDay[dateStr] = [];
        groupedByDay[dateStr].push(m);
    });

    let html = '';
    const sortedDays = Object.keys(groupedByDay).sort((a, b) => new Date(b) - new Date(a));

    sortedDays.forEach(day => {
        const dayDate = new Date(day + 'T12:00:00');
        const formattedDate = dayDate.toLocaleDateString('fr-FR', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        html += `<h2 class="day-header">${escapeHtml(formattedDate)}</h2>`;

        groupedByDay[day].forEach(m => {
            const pred = m.prediction || {};
            let confidence = toFloatSafe(pred.confidence, 0) || 0;
            if (confidence <= 1) confidence = confidence * 100;
            else if (confidence > 100) confidence = confidence / 100;

            const homeLogo = escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true));
            const awayLogo = escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false));

            html += `
                <div class="match-card ${m.verified_double ? 'winner' : ''}">
                    <div class="match-info">
                        <div class="teams">
                            <div class="team">
                                <img src="${homeLogo}" alt="${escapeAttribute(m.home_team)}" class="team-logo" loading="lazy">
                                <span class="team-name">${escapeHtml(m.home_team)}</span>
                                <span class="team-score">${m.home_score ?? '-'}</span>
                            </div>
                            <div class="vs">VS</div>
                            <div class="team">
                                <img src="${awayLogo}" alt="${escapeAttribute(m.away_team)}" class="team-logo" loading="lazy">
                                <span class="team-name">${escapeHtml(m.away_team)}</span>
                                <span class="team-score">${m.away_score ?? '-'}</span>
                            </div>
                        </div>
                    </div>
                    <div class="analysis-panel">
                        <h4>Pronostic</h4>
                        <p><strong>Double chance :</strong> ${escapeHtml(pred.double_chance || 'N/A')}
                           <input type="checkbox" class="prediction-checkbox" ${m.verified_double ? 'checked' : ''} disabled>
                        </p>
                        <p><strong>Fiabilité :</strong> ${escapeHtml(String(Math.round(confidence * 10) / 10))}%</p>
                    </div>
                </div>
            `;
        });
    });

    DOM.historyContainer.innerHTML = html;
}

/* =======================================================
   CONTENT GENERATION
   ======================================================= */
async function loadGeneratedContent() {
    if (generatedContentPromise) return generatedContentPromise;

    generatedContentPromise = (async () => {
        try {
            const [articlesResp, conseilsResp] = await Promise.all([
                fetch(`articles.json?t=${Date.now()}`, { cache: 'no-cache' }).catch(() => null),
                fetch(`conseils.json?t=${Date.now()}`, { cache: 'no-cache' }).catch(() => null)
            ]);

            window.generatedArticles = articlesResp && articlesResp.ok ? await articlesResp.json() : [];
            window.generatedConseils = conseilsResp && conseilsResp.ok ? await conseilsResp.json() : [];
        } catch (error) {
            console.error('Erreur contenu généré:', error);
            window.generatedArticles = [];
            window.generatedConseils = [];
        }
    })();

    return generatedContentPromise;
}

/* =======================================================
   BLOG (SEO slug)
   ======================================================= */
window.showArticleDetail = function (index) {
    const article = window.articlesData?.[index];
    if (!article) return;

    // fallback: si modal n'existe pas, on navigue directement
    if (!DOM.articleModal) {
        const slug = article.slug || '';
        window.location.href = slug
            ? `article.html?slug=${encodeURIComponent(slug)}`
            : `article.html?article=${encodeURIComponent(index)}`;
        return;
    }

    const title = stripMarkdown(article.title || 'Article');
    const image = article.image_url || 'assets/images/default-logo.png';
    const contentHtml = renderSafeRichContent(article.content || '');

    const titleEl = document.getElementById('article-modal-title');
    const imageEl = document.getElementById('article-modal-image');
    const contentEl = document.getElementById('article-modal-content');
    const linkEl = document.getElementById('article-modal-link');

    if (titleEl) titleEl.textContent = title;
    if (imageEl) {
        imageEl.src = image;
        imageEl.alt = title;
    }
    if (contentEl) contentEl.innerHTML = contentHtml;

    const slug = article.slug || '';
    if (linkEl) {
        linkEl.href = slug
            ? `article.html?slug=${encodeURIComponent(slug)}`
            : `article.html?article=${encodeURIComponent(index)}`;
    }

    DOM.articleModal.style.display = 'flex';
};

window.closeArticleModal = function () {
    if (DOM.articleModal) DOM.articleModal.style.display = 'none';
};

async function displayBlogList() {
    if (!DOM.blogList) return;

    await loadGeneratedContent();
    const data = await loadDataGeneric();

    const allArticles = [
        ...(window.generatedArticles || []),
        ...((data?.blog) || [])
    ].filter(a => a?.active !== false);

    window.articlesData = allArticles;

    const horizontalContainer = document.getElementById('blog-horizontal-list');
    if (horizontalContainer) {
        horizontalContainer.innerHTML = allArticles.slice(0, 8).map((article, index) => `
            <div class="horizontal-item" onclick="showArticleDetail(${index})">
                <img src="${escapeAttribute(article.image_url || 'assets/images/default-logo.png')}" alt="${escapeAttribute(stripMarkdown(article.title || 'Article'))}">
                <div class="item-title">${escapeHtml(stripMarkdown(article.title || 'Article'))}</div>
            </div>
        `).join('');
    }

    DOM.blogList.innerHTML = allArticles.map((article, index) => `
        <div class="news-card card" onclick="showArticleDetail(${index})">
            <img src="${escapeAttribute(article.image_url || 'assets/images/default-logo.png')}" alt="${escapeAttribute(stripMarkdown(article.title || 'Article'))}" loading="lazy" class="news-image">
            <h3>${escapeHtml(stripMarkdown(article.title || 'Article'))}</h3>
            <p>${escapeHtml(stripMarkdown((article.excerpt || article.content || '').slice(0, 120)))}...</p>
            <button class="btn btn-secondary" style="margin-top:10px;">Lire la suite</button>
        </div>
    `).join('') || '<div class="no-events">Aucun article pour le moment.</div>';
}

function setMetaContent(id, value) {
    const el = document.getElementById(id);
    if (el) el.setAttribute('content', value);
}

function ensureCanonical(href) {
    let canonical = document.querySelector('link[rel="canonical"]');
    if (!canonical) {
        canonical = document.createElement('link');
        canonical.rel = 'canonical';
        document.head.appendChild(canonical);
    }
    canonical.href = href;
}

function updateArticleSeo(article, resolvedSlug) {
    // Ne fait quelque chose que sur article.html (qui a ces ids)
    const title = stripMarkdown(article.title || 'Article');
    const metaDesc = (article.meta_description || article.excerpt || '').slice(0, 160) ||
        `Analyse et pronostic : ${title}`;

    const url = new URL(window.location.href);
    const canonicalUrl = resolvedSlug
        ? `${url.origin}${url.pathname}?slug=${encodeURIComponent(resolvedSlug)}`
        : window.location.href;

    document.title = `${title} - Mr XPRONOS`;

    const descEl = document.getElementById('article-description');
    if (descEl) descEl.setAttribute('content', metaDesc);

    setMetaContent('og-title', title);
    setMetaContent('og-description', metaDesc);
    setMetaContent('og-url', canonicalUrl);
    setMetaContent('og-image', article.og_image || article.image_url || `${BASE_SITE_URL}assets/images/preview.jpg`);

    setMetaContent('twitter-title', title);
    setMetaContent('twitter-description', metaDesc);
    setMetaContent('twitter-image', article.image_url || `${BASE_SITE_URL}assets/images/preview.jpg`);

    ensureCanonical(canonicalUrl);

    const jsonLdEl = document.getElementById('article-jsonld');
    if (jsonLdEl) {
        const baseArticle = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "author": { "@type": "Person", "name": article.author || "Mr XPRONOS" },
            "datePublished": article.date || article.published_at || new Date().toISOString(),
            "image": [article.image_url].filter(Boolean),
            "mainEntityOfPage": canonicalUrl
        };

        // FAQ si présent
        if (Array.isArray(article.faq) && article.faq.length) {
            const graph = [
                baseArticle,
                {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": article.faq
                        .filter(x => x && x.q && x.a)
                        .map(x => ({
                            "@type": "Question",
                            "name": String(x.q),
                            "acceptedAnswer": { "@type": "Answer", "text": String(x.a) }
                        }))
                }
            ];
            jsonLdEl.textContent = JSON.stringify({ "@graph": graph }, null, 2);
        } else {
            jsonLdEl.textContent = JSON.stringify(baseArticle, null, 2);
        }
    }
}

async function displayBlogPost() {
    if (!DOM.blogPost) return;

    await loadGeneratedContent();
    const data = await loadDataGeneric();

    const allArticles = [
        ...(window.generatedArticles || []),
        ...((data?.blog) || [])
    ].filter(a => a?.active !== false);

    const params = new URLSearchParams(window.location.search);

    // ✅ slug first (SEO)
    const slug = params.get('slug');
    const articleIndex = params.get('article') ?? params.get('id');

    let article = null;

    if (slug) {
        article = allArticles.find(a => (a.slug || '') === slug) || null;
    }

    if (!article && articleIndex !== null && articleIndex !== '') {
        const idx = parseInt(articleIndex, 10);
        if (!isNaN(idx) && allArticles[idx]) article = allArticles[idx];
    }

    if (!article) {
        DOM.blogPost.innerHTML = '<div class="no-events">Article introuvable.</div>';
        return;
    }

    const title = stripMarkdown(article.title || 'Article');
    const contentHtml = renderSafeRichContent(article.content || '');

    DOM.blogPost.innerHTML = `
        <article class="card article-page-card">
            <img src="${escapeAttribute(article.image_url || 'assets/images/default-logo.png')}" alt="${escapeAttribute(title)}" class="news-image" loading="lazy">
            <h1>${escapeHtml(title)}</h1>
            <div class="article-content">${contentHtml}</div>
        </article>
    `;

    // ✅ SEO dynamic meta (article.html)
    updateArticleSeo(article, article.slug || slug || '');

    const titleMeta = document.getElementById('article-title');
    if (titleMeta) titleMeta.textContent = `${title} - Mr XPRONOS`;
}

/* =======================================================
   CONSEILS
   ======================================================= */
async function displayConseils() {
    if (!DOM.conseilsList) return;

    await loadGeneratedContent();
    const data = await loadDataGeneric();

    const allConseils = (window.generatedConseils && window.generatedConseils.length)
        ? window.generatedConseils
        : ((data?.conseils) || []);

    window.conseilsData = allConseils.filter(c => c?.active !== false);

    const horizontalContainer = document.getElementById('conseils-horizontal-list');
    if (horizontalContainer) {
        horizontalContainer.innerHTML = window.conseilsData.slice(0, 8).map((conseil, index) => `
            <div class="horizontal-item" onclick="showConseilDetail(${index})">
                <img src="${escapeAttribute(conseil.image_url || 'assets/images/default-logo.png')}" alt="${escapeAttribute(stripMarkdown(conseil.title || 'Conseil'))}">
                <div class="item-title">${escapeHtml(stripMarkdown(conseil.title || 'Conseil'))}</div>
            </div>
        `).join('');
    }

    DOM.conseilsList.innerHTML = window.conseilsData.map((conseil, index) => `
        <div class="news-card card" onclick="showConseilDetail(${index})">
            <img src="${escapeAttribute(conseil.image_url || 'assets/images/default-logo.png')}" alt="${escapeAttribute(stripMarkdown(conseil.title || 'Conseil'))}" loading="lazy" class="news-image">
            <h3>${escapeHtml(stripMarkdown(conseil.title || 'Conseil'))}</h3>
            <p>${escapeHtml(stripMarkdown((conseil.content || '').slice(0, 120)))}...</p>
            <button class="btn btn-secondary" style="margin-top:10px;">Lire le conseil</button>
        </div>
    `).join('') || '<div class="no-events">Aucun conseil disponible pour le moment.</div>';
}

window.showConseilDetail = function (index) {
    const conseil = window.conseilsData?.[index];
    if (!conseil || !DOM.conseilModal) return;

    document.getElementById('conseil-modal-title').textContent = stripMarkdown(conseil.title || 'Conseil');

    const img = document.getElementById('conseil-modal-image');
    if (img) {
        img.src = conseil.image_url || 'assets/images/default-logo.png';
        img.alt = stripMarkdown(conseil.title || 'Conseil');
    }

    const contentEl = document.getElementById('conseil-modal-content');
    if (contentEl) contentEl.innerHTML = renderSafeRichContent(conseil.content || '');

    DOM.conseilModal.style.display = 'flex';
};

window.closeConseilModal = function () {
    if (DOM.conseilModal) DOM.conseilModal.style.display = 'none';
};

/* =======================================================
   INFOS / NEWS
   ======================================================= */
async function displayInfos() {
    if (!DOM.infosList) return;

    const data = await loadDataGeneric();
    const infos = data?.infos || [];

    DOM.infosList.innerHTML = infos.length
        ? infos.map(i => `<div class="news-card card"><h3>${escapeHtml(i.title)}</h3><p>${escapeHtml(i.content)}</p></div>`).join('')
        : '<div class="no-events">Aucune info disponible.</div>';
}

async function displayFootNews() {
    if (!DOM.footNewsContainer) return;

    try {
        const resp = await fetch(`footnews.json?t=${Date.now()}`, { cache: 'no-cache' });
        if (!resp.ok) throw new Error('Erreur chargement');

        const news = await resp.json();
        if (!Array.isArray(news) || news.length === 0) {
            DOM.footNewsContainer.innerHTML = '<div class="no-events">Aucune actualité pour le moment.</div>';
            return;
        }

        window.newsData = news;

        DOM.footNewsContainer.innerHTML = news.map((item, index) => `
            <div class="news-card card" onclick="showNewsDetail(${index})">
                ${item.image ? `<img src="${escapeAttribute(item.image)}" alt="${escapeAttribute(item.title)}" class="news-image" loading="lazy">` : ''}
                <h3>${escapeHtml(item.title)}</h3>
                <p>${escapeHtml(item.summary || '')}</p>
                <button class="btn btn-secondary" style="margin-top:10px;">Lire la suite</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Erreur actualités:', error);
        DOM.footNewsContainer.innerHTML = '<div class="error">Impossible de charger les actualités.</div>';
    }
}

window.showNewsDetail = function (index) {
    const news = window.newsData?.[index];
    if (!news || !DOM.newsModal) return;

    const titleEl = document.getElementById('news-modal-title');
    const img = document.getElementById('news-modal-image');
    const contentEl = document.getElementById('news-modal-content');
    const linkEl = document.getElementById('news-modal-link');

    if (titleEl) titleEl.textContent = news.title || 'Actualité';
    if (img) {
        img.src = news.image || 'assets/images/default-logo.png';
        img.alt = news.title || 'Actualité';
    }
    if (contentEl) contentEl.innerHTML = renderSafeRichContent(news.summary || '');
    if (linkEl) {
        linkEl.href = news.link || '#';
        linkEl.target = '_blank';
        linkEl.rel = 'noopener noreferrer';
    }

    DOM.newsModal.style.display = 'flex';
};

window.closeNewsModal = function () {
    if (DOM.newsModal) DOM.newsModal.style.display = 'none';
};

/* =======================================================
   BONUS
   ======================================================= */
function initBonusPage() {
    const defaultBookmakers = [
        { name: "1xBet", logo: "assets/images/1xbet.webp", url: "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599", desc: "Bonus de bienvenue jusqu'à 130€" },
        { name: "1win", logo: "assets/images/1win.webp", url: "https://1wrbgb.com/?open=register&p=qqcw", desc: "Bonus exclusif avec XPVIP" },
        { name: "Betwinner", logo: "assets/images/betwinner.webp", url: "https://bwredir.com/299Y", desc: "Offre spéciale nouveaux joueurs" },
        { name: "Melbet", logo: "assets/images/melbet.webp", url: "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041", desc: "Bonus premium Melbet avec inscription rapide" },
        { name: "Linebet", logo: "assets/images/linebet.webp", url: "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611", desc: "Bonus et promotions spéciales Linebet" },
        { name: "Betclic", logo: "assets/images/betclic.webp", url: "https://betpari-click.com/2vY0?extid=USD", desc: "Offre de bienvenue Betclic" }
    ];

    const sourceBookmakers = Array.isArray(allData?.bookmakers) && allData.bookmakers.length
        ? allData.bookmakers.map(b => ({
            name: b.name || "Bookmaker",
            logo: b.logo || "assets/images/default-logo.webp",
            url: b.url || "#",
            desc: b.desc || `Bonus exclusif chez ${b.name || "ce bookmaker"}`
        }))
        : defaultBookmakers;

    window.currentBonusBookmakers = sourceBookmakers;

    if (DOM.bonusSelect) {
        DOM.bonusSelect.innerHTML = sourceBookmakers.map((b, i) =>
            `<option value="${i}">${escapeHtml(b.name)}</option>`
        ).join("");

        DOM.bonusSelect.addEventListener("change", () => {
            const index = parseInt(DOM.bonusSelect.value, 10);
            highlightBonusCard(index);
        });
    }

    renderBonusGrid(sourceBookmakers);
}

function renderBonusGrid(bookmakers) {
    if (!DOM.bonusGrid) return;

    DOM.bonusGrid.innerHTML = bookmakers.map((b, i) => `
        <div class="bookmaker-card bonus-bookmaker-card" data-index="${i}">
            <img src="${escapeAttribute(b.logo)}" alt="${escapeAttribute(b.name)}" loading="lazy" onerror="this.onerror=null; this.src='assets/images/default-logo.webp';">
            <h3>${escapeHtml(b.name)}</h3>
            <p>${escapeHtml(b.desc || "Bonus exclusif bookmaker")}</p>
            <div style="display:flex; gap:10px; flex-wrap:wrap; justify-content:center;">
                <button class="btn btn-secondary" onclick="openBonusModal(${i})">Détails</button>
                <a href="${escapeAttribute(b.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Profiter</a>
            </div>
        </div>
    `).join("");
}

function highlightBonusCard(index) {
    qsa(".bonus-bookmaker-card").forEach(card => card.classList.remove("active-bonus-card"));
    const target = document.querySelector(`.bonus-bookmaker-card[data-index="${index}"]`);
    if (target) {
        target.classList.add("active-bonus-card");
        target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

window.openBonusModal = function (index) {
    const b = window.currentBonusBookmakers?.[index];
    if (!b || !DOM.bonusModal) return;

    const titleEl = document.getElementById("bonus-modal-title");
    const img = document.getElementById("bonus-modal-image");
    const descEl = document.getElementById("bonus-modal-description");
    const footerEl = document.getElementById("bonus-modal-footer");
    const linkEl = document.getElementById("bonus-modal-link");

    if (titleEl) titleEl.textContent = b.name;
    if (img) { img.src = b.logo || "assets/images/default-logo.webp"; img.alt = b.name || "Bookmaker"; }
    if (descEl) {
        descEl.innerHTML = `
            <p>${escapeHtml(b.desc || "Bonus exclusif bookmaker")}</p>
            <p style="margin-top:10px;">Utilisez le code promo <strong>XPVIP</strong> si l'offre le permet.</p>
        `;
    }
    if (footerEl) footerEl.textContent = "Inscription via notre lien recommandé.";
    if (linkEl) { linkEl.href = b.url || "#"; linkEl.target = "_blank"; linkEl.rel = "noopener noreferrer"; }

    DOM.bonusModal.style.display = "flex";
};

window.closeBonusModal = function () {
    if (DOM.bonusModal) DOM.bonusModal.style.display = "none";
};

/* =======================================================
   HOME WIDGETS
   ======================================================= */
function displayLatestVerified() {
    if (!DOM.todayPicks || !allData?.matches) return;

    const verified = allData.matches
        .filter(m => isFinishedMatch(m) && m.verified_double && (m.category === 'pro' || m.category === 'vip'))
        .sort((a, b) => new Date(b.event_date || 0) - new Date(a.event_date || 0))
        .slice(0, 4);

    if (!verified.length) {
        DOM.todayPicks.innerHTML = '<div class="no-events">📭 Aucun pronostic validé récent.</div>';
        return;
    }

    DOM.todayPicks.innerHTML = verified.map(m => `
        <div class="match-card winner">
            <div class="match-info">
                <div class="teams">
                    <div class="team">
                        <img src="${escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true))}" alt="${escapeAttribute(m.home_team)}" class="team-logo" loading="lazy">
                        <span class="team-name">${escapeHtml(m.home_team)}</span>
                        <span class="team-score">${m.home_score ?? '-'}</span>
                    </div>
                    <div class="vs">VS</div>
                    <div class="team">
                        <img src="${escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false))}" alt="${escapeAttribute(m.away_team)}" class="team-logo" loading="lazy">
                        <span class="team-name">${escapeHtml(m.away_team)}</span>
                        <span class="team-score">${m.away_score ?? '-'}</span>
                    </div>
                </div>
            </div>
            <div class="analysis-panel">
                <h4>Pronostic</h4>
                <p><strong>Double chance :</strong> ${escapeHtml(m.prediction?.double_chance || 'N/A')} <input type="checkbox" class="prediction-checkbox" checked disabled></p>
                <p><strong>Fiabilité :</strong> ${escapeHtml(String(m.prediction?.confidence || 0))}%</p>
            </div>
        </div>
    `).join('');
}

function startWinsSlider() {
    if (!DOM.winsTrack || !allData?.matches) return;

    const wins = allData.matches
        .filter(m => isFinishedMatch(m) && m.verified_double)
        .sort((a, b) => new Date(b.event_date || 0) - new Date(a.event_date || 0))
        .slice(0, 10);

    const html = wins.map(m => {
        const score = `${m.home_score ?? '-'} - ${m.away_score ?? '-'}`;
        return `<div class="win-item">✅ <span>${escapeHtml(m.home_team)} ${escapeHtml(score)} ${escapeHtml(m.away_team)}</span> 🏆 ${escapeHtml(m.prediction?.double_chance || '')}</div>`;
    }).join('');

    DOM.winsTrack.innerHTML = html + html;
}

function animateWins() {
    if (!DOM.winsCount || !allData?.matches) return;

    const target = allData.matches.filter(m => isFinishedMatch(m) && m.verified_double).length;
    if (target <= 0) {
        DOM.winsCount.textContent = '0';
        return;
    }

    let count = 0;
    const interval = setInterval(() => {
        count++;
        DOM.winsCount.textContent = String(count);
        if (count >= target) clearInterval(interval);
    }, 20);
}

async function displayTestimonials() {
    if (!DOM.testimonials) return;

    try {
        const resp = await fetch(`testimonials.json?t=${Date.now()}`, { cache: 'no-cache' });
        if (!resp.ok) throw new Error('Erreur');
        const testimonials = await resp.json();

        DOM.testimonials.innerHTML = testimonials.map(t => `
            <div class="card">
                <p>"${escapeHtml(t.text)}"</p>
                <p style="margin-top:1rem; color:var(--or);">— ${escapeHtml(t.name)}</p>
            </div>
        `).join('');
    } catch {
        DOM.testimonials.innerHTML = `
            <div class="card"><p>"Grâce à Mr XPRONOS, j'ai multiplié mes gains par 3 en un mois !"</p><p style="margin-top:1rem;color:var(--or);">— Jean Martin</p></div>
            <div class="card"><p>"Les pronostics VIP sont incroyablement précis. Je recommande !"</p><p style="margin-top:1rem;color:var(--or);">— Marie Dubois</p></div>
            <div class="card"><p>"Le système de partage permet d'accéder à des analyses de qualité gratuitement."</p><p style="margin-top:1rem;color:var(--or);">— Thomas Petit</p></div>
        `;
    }
}

function startWinNotifications() {
    if (!DOM.winPopup) return;

    const firstNames = ["Jean", "Michel", "David", "Lucas", "Thomas", "Patrick", "Samuel", "Kevin"];
    const lastNames = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand"];

    const notifications = Array.from({ length: 5 }).map(() => ({
        name: `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`,
        gain: Math.floor(Math.random() * (200 - 45 + 1)) + 45
    }));

    let index = 0;

    function showPopup() {
        const { name, gain } = notifications[index];
        DOM.winPopup.innerHTML = `💰 <b>${escapeHtml(name)}</b> a gagné <b>${escapeHtml(gain)}€</b> aujourd'hui grâce au VIP !`;
        DOM.winPopup.classList.add('show');
        setTimeout(() => DOM.winPopup.classList.remove('show'), 4000);
        index = (index + 1) % notifications.length;
    }

    setTimeout(showPopup, 5000);
}

function updateHomeSuccessRate() {
    if (!DOM.successFill || !DOM.successPercent || !allData?.matches) return;

    const finished = allData.matches.filter(isFinishedMatch);
    if (finished.length === 0) {
        DOM.successFill.style.width = '0%';
        DOM.successPercent.textContent = '0%';
        return;
    }

    const successful = finished.filter(m => m.verified_double).length;
    const percent = Math.round((successful / finished.length) * 100);

    DOM.successFill.style.width = percent + '%';
    DOM.successPercent.textContent = percent + '%';
}

function updatePronosticsSuccessRate() {
    if (!DOM.successRateContainer) return;
    if (!allData?.matches) {
        DOM.successRateContainer.style.display = 'none';
        return;
    }

    const finished = allData.matches.filter(isFinishedMatch);
    const successful = finished.filter(m => m.verified_double);

    if (finished.length === 0) {
        DOM.successRateContainer.style.display = 'none';
        return;
    }

    const rate = ((successful.length / finished.length) * 100).toFixed(1);
    const roi = Number(allData?.stats?.roi || 0);
    const roiDisplay = roi !== 0 ? (roi > 0 ? '+' : '') + roi + '%' : 'N/A';

    DOM.successRateContainer.innerHTML = `
        <div class="success-rate-item">
            <div class="success-rate-value">${escapeHtml(rate)}%</div>
            <div class="success-rate-label">Réussite</div>
        </div>
        <div class="success-rate-item">
            <div class="success-rate-value">${escapeHtml(roiDisplay)}</div>
            <div class="success-rate-label">ROI</div>
        </div>
    `;
    DOM.successRateContainer.style.display = 'flex';
}

/* =======================================================
   SCROLL PROGRESS
   ======================================================= */
function initScrollProgress() {
    if (document.querySelector('.scroll-progress')) return;
    const progressBar = document.createElement('div');
    progressBar.className = 'scroll-progress';
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', () => {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = height > 0 ? (winScroll / height) * 100 : 0;
        progressBar.style.width = scrolled + '%';
    });
}

/* =======================================================
   EVENT LISTENERS
   ======================================================= */
function setupGlobalButtons() {
    document.getElementById('close-ios-guide')?.addEventListener('click', closeIosGuide);
    document.getElementById('close-ios-guide-btn')?.addEventListener('click', closeIosGuide);
}

function setupPronosticPageListeners() {
    qsa('.tab-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            qsa('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.cat;
            if (currentCategory !== 'vip') currentSubcat = 'pronostics';
            await handleCategoryChange();
        });
    });

    qsa('.subtab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            qsa('.subtab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSubcat = btn.dataset.subcat;
            filterAndDisplay();
        });
    });

    qsa('.day-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            qsa('.day-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentDay = btn.dataset.day;
            filterAndDisplay();
        });
    });

    DOM.searchInput?.addEventListener('input', (e) => {
        searchTerm = e.target.value || '';
        applySearchFilter();
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-share');
        if (!btn) return;
        try {
            const matchData = JSON.parse(decodeURIComponent(btn.dataset.match));
            sharePronostic(matchData);
        } catch (err) {
            console.error('Erreur parsing données match', err);
        }
    });
}

async function handleCategoryChange() {
    const vipEnabled = localStorage.getItem('vipEnabled') !== 'false';

    if (currentCategory === 'vip') {
        if (!vipEnabled) {
            alert('Les pronostics VIP sont temporairement désactivés.');
            currentCategory = 'simple';
            qsa('.tab-btn').forEach(b => b.classList.remove('active'));
            qs('.tab-btn[data-cat="simple"]')?.classList.add('active');
            filterAndDisplay();
            return;
        }

        const isVip = await checkVipStatus();
        if (!isVip) {
            if (DOM.vipLockedOverlay) {
                ensureVipOverlayStructure();
                showVipLoginForm(DOM.vipLockedOverlay);
                DOM.vipLockedOverlay.style.display = 'flex';
                if (DOM.matches) DOM.matches.style.display = 'none';
            }
            return;
        }

        hideVipLocked();
        filterAndDisplay();
        return;
    }

    if (currentCategory === 'simple') {
        hideVipLocked();
        filterAndDisplay();
        return;
    }

    const target = shareLimits[currentCategory];
    const shareCount = getDailyShareCount();

    if (shareCount >= target) {
        hideVipLocked();
        filterAndDisplay();
    } else {
        showVipLocked(currentCategory);
    }
}

/* =======================================================
   INIT APP
   ======================================================= */
document.addEventListener('DOMContentLoaded', async () => {
    initDOM();
    setupGlobalButtons();
    setupInstallButton();
    updateShareCounter();

    await initSupabase();
    await updateDisplayedCounters();
    subscribeToCounters();
    await registerUniqueUser();
    await initOnlineUsers();
    countVisitOncePerDay();
    showIosGuideIfNeeded();

    if (Notification.permission === 'granted') subscribeToPush(false);

    const page = detectPage();

    switch (page) {
        case 'pronos':
            setupPronosticPageListeners();
            await loadData();
            break;

        case 'history':
            await displayHistory();
            renderBookmakers();
            break;

        case 'blog-list':
            await displayBlogList();
            renderBookmakers();
            break;

        case 'blog-post':
            await displayBlogPost();
            renderBookmakers();
            break;

        case 'conseils':
            await displayConseils();
            renderBookmakers();
            break;

        case 'bonus': {
            const data = await loadDataGeneric();
            if (data) allData = data;
            initBonusPage();
            renderBookmakers(allData?.bookmakers);
            break;
        }

        case 'infos':
            await displayFootNews();
            renderBookmakers();
            break;

        case 'home': {
            const data = await loadDataGeneric();
            if (data) {
                allData = data;
                renderBookmakers(data.bookmakers);
                displayLatestVerified();
                startWinsSlider();
                animateWins();
                updateHomeSuccessRate();
            }
            await displayTestimonials();
            startWinNotifications();
            break;
        }

        default:
            renderBookmakers();
            break;
    }

    await displayInfos(); // no-op si container absent
    initScrollProgress();
});