/**
 * main.js - Mr XPRONOS – Version ultime avec analytics, PWA et visiteurs en ligne
 * Toutes les fonctionnalités sont regroupées dans ce seul fichier.
 */

// =======================================================
// Désactiver les logs en production (garder les erreurs)
// =======================================================
if (location.hostname !== 'localhost' && !location.hostname.includes('127.0.0.1')) {
    console.log = () => {};
    console.warn = () => {};
    // console.error reste actif pour le débogage
}

// =======================================================
// CONFIGURATION & CONSTANTES GLOBALES
// =======================================================
let supabase = null;
let supabaseAvailable = false;
let allData = null;
let currentCategory = 'simple';
let currentSubcat = 'pronostics';
let currentDay = 'today';
let filteredMatchesWithoutSearch = [];
let searchTerm = '';
let shareStartTime = null;
let sharePending = false;

const shareLimits = { pro: 3, vip: 5 };
const POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
];

// Éléments DOM fréquemment utilisés (initialisés après chargement)
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
    articleModal: null,
    conseilModal: null,
    newsModal: null,
    winPopup: null,
    iosGuidePopup: null,
    installButton: null
};

document.addEventListener('DOMContentLoaded', () => {
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
    DOM.articleModal = document.getElementById('article-modal');
    DOM.conseilModal = document.getElementById('conseil-modal');
    DOM.newsModal = document.getElementById('news-modal');
    DOM.winPopup = document.getElementById('win-popup');
    DOM.iosGuidePopup = document.getElementById('ios-guide-popup');
    DOM.installButton = document.getElementById('install-app');
});

// =======================================================
// FONCTIONS UTILITAIRES
// =======================================================
function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; bottom: 20px; right: 20px; background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white; padding: 12px 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000; font-weight: 600; animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), duration);
}

function getUserId() {
    let userId = localStorage.getItem('mx_user_id');
    if (!userId) {
        userId = 'MX-' + crypto.randomUUID();
        localStorage.setItem('mx_user_id', userId);
    }
    return userId;
}

// =======================================================
// INITIALISATION SUPABASE
// =======================================================
async function initSupabase() {
    try {
        const { supabaseUrl, supabaseAnonKey } = await import('./config.js');
        if (!supabaseUrl || !supabaseUrl.startsWith('https://')) throw new Error('URL Supabase invalide');
        if (!supabaseAnonKey) throw new Error('Clé Supabase manquante');
        const { createClient } = await import('https://esm.sh/@supabase/supabase-js@2');
        supabase = createClient(supabaseUrl, supabaseAnonKey);
        supabaseAvailable = true;
        console.log('✅ Supabase connecté');
    } catch (error) {
        console.warn('⚠️ Supabase non configuré, utilisation des compteurs locaux');
        supabaseAvailable = false;
    }
}

// =======================================================
// GESTION DES COMPTEURS (avec fallback localStorage)
// =======================================================
async function incrementCounter(counterName) {
    if (!supabaseAvailable) {
        let local = localStorage.getItem(counterName) || 0;
        localStorage.setItem(counterName, parseInt(local) + 1);
        return;
    }
    try {
        const { error } = await supabase.rpc('increment_counter', {
            counter_name: counterName
        });
        if (error) console.error('Erreur incrémentation RPC:', error);
    } catch (e) {
        console.error('Erreur réseau incrémentation:', e);
    }
}

async function updateDisplayedCounters() {
    if (!supabaseAvailable) return;
    try {
        const { data, error } = await supabase
            .from('counters')
            .select('total_visits, total_shares, unique_users')
            .eq('id', 1)
            .single();
        if (error) throw error;
        if (DOM.usersCount) DOM.usersCount.textContent = (data.unique_users || 0).toLocaleString() + '+';
        if (DOM.sharesCount) DOM.sharesCount.textContent = (data.total_shares || 0).toLocaleString() + '+';
    } catch (e) {
        console.error('Erreur récupération counters:', e);
    }
}

function subscribeToCounters() {
    if (!supabaseAvailable) return;
    supabase
        .channel('counters-live')
        .on(
            'postgres_changes',
            { event: 'UPDATE', schema: 'public', table: 'counters', filter: 'id=eq.1' },
            (payload) => {
                if (DOM.usersCount) DOM.usersCount.textContent = (payload.new.unique_users || 0).toLocaleString() + '+';
                if (DOM.sharesCount) DOM.sharesCount.textContent = (payload.new.total_shares || 0).toLocaleString() + '+';
            }
        )
        .subscribe((status) => {
            if (status === 'SUBSCRIBED') console.log('📡 Realtime counters actif');
        });
}

// =======================================================
// ENREGISTREMENT DES ÉVÉNEMENTS (table analytics)
// =======================================================
async function recordEvent(type, page = '') {
    if (!supabaseAvailable) {
        console.warn('Supabase non disponible, événement non enregistré');
        return;
    }
    const userId = getUserId();
    try {
        const { error } = await supabase
            .from('analytics')
            .insert({ event_type: type, user_id: userId, page });
        if (error) {
            console.error('Erreur insertion événement:', error);
        } else {
            console.log('✅ Événement enregistré:', type, page);
        }
    } catch (e) {
        console.error('Exception lors de l\'enregistrement:', e);
    }
}

// =======================================================
// GESTION DES VISITES (une fois par jour)
// =======================================================
function countVisitOncePerDay() {
    const today = new Date().toDateString();
    const lastVisit = localStorage.getItem('mx_last_visit');
    if (lastVisit !== today) {
        localStorage.setItem('mx_last_visit', today);
        incrementCounter('total_visits');
        recordEvent('visit', window.location.pathname);
    }
}

// =======================================================
// GESTION DES UTILISATEURS UNIQUES
// =======================================================
async function registerUniqueUser() {
    if (!supabaseAvailable) return;
    const userId = getUserId();
    const registered = localStorage.getItem('mx_registered');
    if (registered) return;
    localStorage.setItem('mx_registered', 'true');
    try {
        await supabase.from('users').insert({ user_id: userId });
        await supabase.rpc('increment_counter', { counter_name: 'unique_users' });
    } catch (e) {
        console.error('Erreur enregistrement utilisateur unique:', e);
    }
}

// =======================================================
// VISITEURS EN LIGNE (Realtime Presence)
// =======================================================
let onlineChannel = null;

async function initOnlineUsers() {
    if (!supabaseAvailable || !DOM.onlineCount) return;

    onlineChannel = supabase.channel('online-users', {
        config: {
            presence: { key: getUserId() }
        }
    });

    onlineChannel
        .on('presence', { event: 'sync' }, () => {
            const state = onlineChannel.presenceState();
            const onlineUsers = Object.keys(state).length;
            DOM.onlineCount.textContent = onlineUsers;
        })
        .subscribe(async (status) => {
            if (status === 'SUBSCRIBED') {
                await onlineChannel.track({ online_at: new Date().toISOString() });
            }
        });
}

// =======================================================
// GESTION DES PARTAGES QUOTIDIENS
// =======================================================
function getDailyShareCount() {
    const lastReset = localStorage.getItem('shareLastReset');
    const today = new Date().toDateString();
    if (lastReset !== today) {
        localStorage.setItem('shareLastReset', today);
        localStorage.setItem('shareCount', '0');
        return 0;
    }
    return parseInt(localStorage.getItem('shareCount') || '0');
}

function incrementShareCount() {
    const current = getDailyShareCount();
    const newCount = current + 1;
    localStorage.setItem('shareCount', newCount.toString());
    return newCount;
}

function updateShareCounter() {
    if (DOM.shareCounter) {
        const count = getDailyShareCount();
        DOM.shareCounter.textContent = `🔥 ${count} partages aujourd'hui`;
    }
}

// =======================================================
// PWA & INSTALLATION (version robuste)
// =======================================================
let deferredPrompt;

function getOS() {
    const ua = window.navigator.userAgent;
    if (/iPad|iPhone|iPod/.test(ua)) return 'iOS';
    if (/Android/.test(ua)) return 'Android';
    return 'Other';
}

function isPwaInstalled() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}

function showIosGuideIfNeeded() {
    if (getOS() === 'iOS' && !isPwaInstalled()) {
        const lastClosed = localStorage.getItem('iosGuideLastClosed');
        if (lastClosed) {
            const hoursSince = (Date.now() - parseInt(lastClosed)) / (1000 * 60 * 60);
            if (hoursSince < 24) return;
        }
        if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = 'flex';
    }
}

function closeIosGuide() {
    if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = 'none';
    localStorage.setItem('iosGuideLastClosed', Date.now().toString());
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (DOM.installButton && !isPwaInstalled()) {
        DOM.installButton.style.display = 'inline-block';
    }
    console.log('beforeinstallprompt capturé');
});

DOM.installButton?.addEventListener('click', async () => {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        console.log(`Installation : ${outcome}`);
        deferredPrompt = null;
        DOM.installButton.style.display = 'none';
    } else {
        if (getOS() === 'iOS') {
            showIosGuideIfNeeded();
        } else {
            alert('L\'installation automatique n\'est pas disponible. Utilisez le menu du navigateur (Ajouter à l\'écran d\'accueil).');
        }
    }
});

window.addEventListener('appinstalled', () => {
    console.log('PWA installée');
    if (DOM.installButton) DOM.installButton.style.display = 'none';
    if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = 'none';
});

document.getElementById('close-ios-guide')?.addEventListener('click', closeIosGuide);
document.getElementById('close-ios-guide-btn')?.addEventListener('click', closeIosGuide);

// Afficher le guide iOS si nécessaire (indépendant du bouton)
showIosGuideIfNeeded();

// =======================================================
// CHARGEMENT DES DONNÉES (data.json)
// =======================================================
async function loadData() {
    console.log('🔄 Chargement des pronostics...');
    if (DOM.matches) {
        DOM.matches.innerHTML = `<div style="text-align:center; padding:80px 20px; color:#aaa;"><div style="font-size:60px; margin-bottom:20px;">⏳</div><div>Chargement des matchs...</div></div>`;
    }
    let dataLoaded = false;
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const resp = await fetch('data.json?t=' + Date.now(), { signal: controller.signal, cache: 'no-cache' });
        clearTimeout(timeoutId);
        if (resp.ok) {
            allData = await resp.json();
            console.log('✅ Données fraîches du serveur');
            localStorage.setItem('cachedData', JSON.stringify(allData));
            dataLoaded = true;
        }
    } catch (err) {
        console.log('🌐 Hors ligne ou erreur réseau → utilisation du cache');
    }
    if (!dataLoaded) {
        const cached = localStorage.getItem('cachedData');
        if (cached) {
            try {
                allData = JSON.parse(cached);
                console.log('📦 Pronos chargés depuis le cache local (' + allData.matches.length + ' matchs)');
                dataLoaded = true;
            } catch (e) { console.error('❌ Cache corrompu', e); }
        }
    }
    if (dataLoaded && allData) {
        if (DOM.matches && !navigator.onLine) {
            DOM.matches.insertAdjacentHTML('afterbegin', `<div style="background:#ffcc00; color:#000; text-align:center; padding:8px; font-weight:700; font-size:0.95rem;">📴 MODE HORS LIGNE — Pronostics du cache (${new Date().toLocaleDateString('fr-FR')})</div>`);
        }
        renderBookmakers(allData.bookmakers);
        hideEmptyTabs();
        maybeHideTabBar();
        filterAndDisplay();
        updatePronosticsSuccessRate();
    } else if (DOM.matches) {
        DOM.matches.innerHTML = `<div class="error" style="text-align:center; padding:60px;">❌ Aucune donnée disponible.<br><small>Connectez-vous une première fois pour charger le cache.</small></div>`;
    }
}

// =======================================================
// TAUX DE RÉUSSITE (page d'accueil)
// =======================================================
function updateHomeSuccessRate() {
    if (!DOM.successFill || !DOM.successPercent) return;
    if (!allData || !allData.matches) {
        DOM.successFill.style.width = '0%';
        DOM.successPercent.textContent = '0%';
        return;
    }
    const matches = allData.matches;
    const finished = matches.filter(m => {
        if (!m.status) return false;
        const s = m.status.toLowerCase();
        return s.includes('finished') || s.includes('terminé') || s.includes('ended');
    });
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

// =======================================================
// TAUX DE RÉUSSITE ET ROI (page pronostics)
// =======================================================
function updatePronosticsSuccessRate() {
    const container = document.getElementById('success-rate-container');
    if (!container) return;
    if (!allData || !allData.matches) {
        container.style.display = 'none';
        return;
    }
    const matches = allData.matches;
    const finished = matches.filter(m => {
        if (!m.status) return false;
        const s = m.status.toLowerCase();
        return s.includes('finished') || s.includes('terminé') || s.includes('ended');
    });
    const successful = finished.filter(m => m.verified_double);
    if (finished.length === 0) {
        container.style.display = 'none';
        return;
    }
    const rate = ((successful.length / finished.length) * 100).toFixed(1);
    const stats = allData.stats || {};
    const roi = stats.roi || 0;
    const roiDisplay = roi !== 0 ? (roi > 0 ? '+' : '') + roi + '%' : 'N/A';
    container.innerHTML = `
        <div class="success-rate-item">
            <div class="success-rate-value">${rate}%</div>
            <div class="success-rate-label">Réussite</div>
        </div>
        <div class="success-rate-item">
            <div class="success-rate-value">${roiDisplay}</div>
            <div class="success-rate-label">ROI</div>
        </div>
    `;
    container.style.display = 'flex';
}

// =======================================================
// FILTRAGE ET AFFICHAGE
// =======================================================
function hideEmptyTabs() {
    const vipEnabled = localStorage.getItem('vipEnabled') !== 'false';
    const counts = { simple: 0, pro: 0, vip: 0 };
    if (allData && allData.matches) {
        allData.matches.forEach(m => counts[m.category]++);
    }
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const cat = btn.dataset.cat;
        if (cat === 'vip' && !vipEnabled) {
            btn.style.display = 'none';
        } else if (cat === 'pro' || cat === 'vip') {
            btn.style.display = 'inline-block';
        } else {
            btn.style.display = counts[cat] > 0 ? 'inline-block' : 'none';
        }
    });
    const visibleTabs = Array.from(document.querySelectorAll('.tab-btn')).filter(btn => btn.style.display !== 'none');
    if (visibleTabs.length > 0) {
        const currentActive = document.querySelector('.tab-btn.active');
        if (!currentActive || currentActive.style.display === 'none') {
            visibleTabs[0].classList.add('active');
            currentCategory = visibleTabs[0].dataset.cat;
            if (currentCategory !== 'vip') currentSubcat = 'pronostics';
        }
    } else {
        const tabBar = document.querySelector('.category-tabs');
        if (tabBar) tabBar.style.display = 'none';
    }
    if (DOM.vipSubtabs) {
        const showPronostics = counts.vip > 0 && vipEnabled;
        const subtabBtns = DOM.vipSubtabs.querySelectorAll('.subtab-btn');
        if (subtabBtns.length >= 1) subtabBtns[0].style.display = showPronostics ? 'inline-block' : 'none';
        DOM.vipSubtabs.style.display = showPronostics ? 'flex' : 'none';
        const activeSub = DOM.vipSubtabs.querySelector('.subtab-btn.active');
        if (activeSub && activeSub.style.display === 'none') {
            const firstVisible = Array.from(subtabBtns).find(btn => btn.style.display !== 'none');
            if (firstVisible) {
                firstVisible.classList.add('active');
                currentSubcat = firstVisible.dataset.subcat;
            } else currentSubcat = 'pronostics';
        }
    }
}

function maybeHideTabBar() {
    const tabBar = document.querySelector('.category-tabs');
    if (tabBar) {
        const visibleTabs = Array.from(tabBar.querySelectorAll('.tab-btn')).filter(btn => btn.style.display !== 'none');
        tabBar.style.display = visibleTabs.length === 0 ? 'none' : 'flex';
    }
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.cat;
            if (currentCategory !== 'vip') currentSubcat = 'pronostics';
            handleCategoryChange();
        });
    });
    document.querySelectorAll('.subtab-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.subtab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSubcat = btn.dataset.subcat;
            filterAndDisplay();
        });
    });
    document.querySelectorAll('.day-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.day-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentDay = btn.dataset.day;
            filterAndDisplay();
        });
    });
    const shareWa = document.getElementById('share-wa');
    const shareTg = document.getElementById('share-tg');
    const closePopup = document.getElementById('close-popup');
    if (shareWa) shareWa.addEventListener('click', () => share('whatsapp'));
    if (shareTg) shareTg.addEventListener('click', () => share('telegram'));
    if (closePopup) closePopup.addEventListener('click', () => {
        if (DOM.sharePopup) DOM.sharePopup.classList.remove('active');
    });
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-share')) {
            try {
                const matchData = JSON.parse(decodeURIComponent(e.target.dataset.match));
                sharePronostic(matchData);
            } catch (err) { console.error('Erreur parsing données match', err); }
        }
    });
}

async function handleCategoryChange() {
    const vipEnabled = localStorage.getItem('vipEnabled') !== 'false';
    if (currentCategory === 'vip') {
        if (!vipEnabled) {
            alert('Les pronostics VIP sont temporairement désactivés.');
            currentCategory = 'simple';
            document.querySelector('.tab-btn[data-cat="simple"]').classList.add('active');
            document.querySelector('.tab-btn[data-cat="vip"]').classList.remove('active');
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
            } else {
                alert('Accès VIP payant. Contactez-nous sur WhatsApp ou Telegram.');
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
    } else {
        const target = shareLimits[currentCategory];
        const shareCount = getDailyShareCount();
        if (shareCount >= target) {
            hideVipLocked();
            filterAndDisplay();
        } else {
            showVipLocked(currentCategory);
        }
    }
}

function showVipLocked(category) {
    const target = shareLimits[category];
    const shareCount = getDailyShareCount();
    const remaining = target - shareCount;

    if (DOM.vipLockedOverlay) {
        ensureVipOverlayStructure();
        
        const titleEl = DOM.vipLockedOverlay.querySelector('h3');
        const textEl = DOM.vipLockedOverlay.querySelector('p');
        const shareCountEl = document.getElementById('share-count-locked');
        const shareTargetEl = document.getElementById('share-target-locked');

        if (titleEl) titleEl.textContent = `🔒 ${category === 'pro' ? 'Pronostics Pro' : 'Pronostics VIP'} verrouillés`;
        if (textEl) textEl.innerHTML = `Partagez ce lien à <strong>${remaining}</strong> ami(s) pour débloquer.`;
        if (shareCountEl) shareCountEl.textContent = shareCount;
        if (shareTargetEl) shareTargetEl.textContent = target;

        DOM.vipLockedOverlay.style.display = 'flex';
        if (DOM.matches) DOM.matches.style.display = 'none';
    } else {
        showSharePopup(category, remaining);
    }
}

function ensureVipOverlayStructure() {
    if (!DOM.vipLockedOverlay) return;
    if (DOM.vipLockedOverlay.children.length === 0) {
        DOM.vipLockedOverlay.innerHTML = `
            <div class="vip-locked-content">
                <div class="lock-icon">🔒</div>
                <h3></h3>
                <p></p>
                <div class="share-buttons vip-contact-buttons" style="display: flex; gap: 10px; justify-content: center; margin: 20px 0;">
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

function hideVipLocked() {
    if (DOM.vipLockedOverlay) {
        DOM.vipLockedOverlay.style.display = 'none';
        if (DOM.matches) DOM.matches.style.display = 'grid';
    }
}

function showSharePopup(category, remaining) {
    if (!DOM.sharePopup) {
        createSharePopup();
    }
    const shareCount = getDailyShareCount();
    const shareRemaining = document.getElementById('share-remaining');
    const shareCurrent = document.getElementById('share-current');
    const shareTarget = document.getElementById('share-target');
    const shareMessage = document.getElementById('share-message');

    if (shareRemaining) shareRemaining.textContent = remaining;
    if (shareCurrent) shareCurrent.textContent = shareCount;
    if (shareTarget) shareTarget.textContent = shareLimits[category];
    if (shareMessage) shareMessage.innerHTML = `Pour accéder aux pronostics ${category === 'pro' ? 'Pro' : 'VIP'}, partagez ce lien à <span id="share-remaining">${remaining}</span> amis.`;

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
    document.getElementById('share-wa').addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg').addEventListener('click', () => share('telegram'));
    document.getElementById('close-popup').addEventListener('click', () => {
        DOM.sharePopup.classList.remove('active');
    });
}

// =======================================================
// NOUVELLES FONCTIONS DE PARTAGE (messages améliorés)
// =======================================================
function share(platform) {
    const baseUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    let message;
    if (platform === 'whatsapp') {
        message = `🔥 PRONOSTICS FOOTBALL GRATUITS\n\nJe viens de découvrir ce site ⚽\n\nIls donnent :\n✔ plusieurs matchs analysés chaque jour\n✔ statistiques + analyse\n✔ pronostics fiables\n\n👇 Accède aux matchs du jour :\n${baseUrl}\n\n💰 Très utile pour les paris sportifs !`;
    } else {
        // Telegram : on met le lien à la fin seulement
        message = `🔥 PRONOSTICS FOOTBALL GRATUITS\n\nJe viens de découvrir ce site ⚽\n\nIls donnent :\n✔ plusieurs matchs analysés chaque jour\n✔ statistiques + analyse\n✔ pronostics fiables\n\n👇 Accède aux matchs du jour :\n${baseUrl}\n\n💰 Très utile pour les paris sportifs !`;
    }
    const url = platform === 'whatsapp' 
        ? `https://wa.me/?text=${encodeURIComponent(message)}`
        : `https://t.me/share/url?url=${encodeURIComponent(baseUrl)}&text=${encodeURIComponent(message)}`;
    window.open(url, '_blank');
    shareStartTime = Date.now();
    sharePending = true;
    recordEvent('share', window.location.pathname);
}

function sharePronostic(match) {
    const siteUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    const messageWhatsApp = `🔥 PRONOSTICS FOOTBALL GRATUITS\n\n⚽ *${match.home_team} vs ${match.away_team}*\n📈 *Double chance* : ${match.prediction.double_chance} – Fiabilité ${match.prediction.confidence}%\n\n👇 Analyse complète :\n${siteUrl}\n\n💰 Rejoins les gagnants !`;
    const messageTelegram = `🔥 PRONOSTICS FOOTBALL GRATUITS\n\n⚽ ${match.home_team} vs ${match.away_team}\n📈 Double chance : ${match.prediction.double_chance} – Fiabilité ${match.prediction.confidence}%\n\n👇 Analyse complète :\n${siteUrl}\n\n💰 Rejoins les gagnants !`;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(messageWhatsApp)}`;
    const telegramUrl = `https://t.me/share/url?url=${encodeURIComponent(siteUrl)}&text=${encodeURIComponent(messageTelegram)}`;
    if (confirm("Partager sur WhatsApp ? (OK = WhatsApp, Annuler = Telegram)")) {
        window.open(whatsappUrl, '_blank');
    } else {
        window.open(telegramUrl, '_blank');
    }
    incrementShareCount();
    incrementCounter('total_shares').catch(e => console.warn('Erreur incrémentation', e));
    recordEvent('click_pronostic', window.location.pathname);
    recordEvent('share', window.location.pathname);
}

// =======================================================
// FONCTIONS DE FILTRAGE DES MATCHS
// =======================================================
function getLocalDateString(day) {
    const now = new Date();
    // On travaille en UTC pour éviter les problèmes de fuseau horaire
    const target = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    if (day === 'tomorrow') target.setUTCDate(target.getUTCDate() + 1);
    else if (day === 'yesterday') target.setUTCDate(target.getUTCDate() - 1);
    const year = target.getUTCFullYear();
    const month = String(target.getUTCMonth() + 1).padStart(2, '0');
    const dayOfMonth = String(target.getUTCDate()).padStart(2, '0');
    return `${year}-${month}-${dayOfMonth}`;
}

function getLocalDateFromEvent(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    if (isNaN(date)) return null;
    // Extraire la date en UTC
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
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
        const dateA = new Date(a.event_date || 0);
        const dateB = new Date(b.event_date || 0);
        return dateA - dateB;
    });
}

function filterAndDisplay() {
    if (!allData || !allData.matches) {
        if (DOM.matches) DOM.matches.innerHTML = '<div class="no-events">Aucun match disponible.</div>';
        return;
    }
    const targetDate = getLocalDateString(currentDay);
    const targetCat = (currentCategory === 'vip' && currentSubcat === 'pronostics') ? 'vip' : currentCategory;
    const filtered = allData.matches.filter(m => {
        const eventLocalDate = getLocalDateFromEvent(m.event_date);
        return m.category === targetCat && eventLocalDate === targetDate;
    });
    const sorted = sortMatchesByLeague(filtered);
    filteredMatchesWithoutSearch = sorted;
    applySearchFilter();
}

function applySearchFilter() {
    if (!filteredMatchesWithoutSearch) return;
    if (!searchTerm.trim()) {
        renderMatches(filteredMatchesWithoutSearch);
        return;
    }
    const term = searchTerm.toLowerCase().trim();
    const filtered = filteredMatchesWithoutSearch.filter(m => 
        m.home_team.toLowerCase().includes(term) ||
        m.away_team.toLowerCase().includes(term) ||
        (m.league && m.league.toLowerCase().includes(term))
    );
    renderMatches(filtered);
}

function formatMatchTime(isoString) {
    if (!isoString) return 'Horaire inconnu';
    const date = new Date(isoString);
    if (isNaN(date)) return 'Horaire inconnu';
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function getTeamLogoPath(teamName, isHome = true) {
    if (!teamName) return isHome ? 'assets/images/home.webp' : 'assets/images/away.webp';
    const normalized = teamName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
    return `assets/images/${normalized}.webp`;
}

function renderMatches(matches) {
    if (!DOM.matches) return;
    if (matches.length === 0) {
        DOM.matches.innerHTML = '<div class="no-events">Aucun match.</div>';
        return;
    }
    const grouped = {};
    matches.forEach(m => {
        const league = m.league || 'Autres ligues';
        if (!grouped[league]) grouped[league] = [];
        grouped[league].push(m);
    });
    let html = '';
    const leagueOrder = [...POPULAR_LEAGUES, 'Autres ligues'];
    const sortedLeagues = Object.keys(grouped).sort((a, b) => {
        const ia = leagueOrder.findIndex(l => a.includes(l) || a === l);
        const ib = leagueOrder.findIndex(l => b.includes(l) || b === l);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    });
    sortedLeagues.forEach(league => {
        html += `<h2 class="league-header" style="color: var(--or); margin-top: 2rem;">${league}</h2>`;
        grouped[league].forEach(m => {
            const pred = m.prediction || {};
            const doubleChance = pred.double_chance || 'N/A';
            let confidence = pred.confidence || 0;
            if (typeof confidence === 'string') confidence = parseFloat(confidence);
            if (isNaN(confidence)) confidence = 0;
            if (confidence > 100) confidence = confidence / 100;
            confidence = Math.min(100, Math.round(confidence * 10) / 10);
            const matchTime = formatMatchTime(m.event_date);
            const statusFr = translateStatus(m.status);
            const statusClass = getStatusClass(m.status);
            const eventDate = m.event_date ? m.event_date.split('T')[0] : '';
            const yesterdayStr = getLocalDateString('yesterday');
            const verifiedDouble = (eventDate === yesterdayStr && m.verified_double) ? 'checked' : '';
            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const homeDefault = 'assets/images/home.webp';
            const awayDefault = 'assets/images/away.webp';
            const homeLogo = m.home_logo || getTeamLogoPath(m.home_team, true);
            const awayLogo = m.away_logo || getTeamLogoPath(m.away_team, false);
            const isWinner = m.verified_double;
            const winnerClass = isWinner ? 'winner' : '';
            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';
            const matchDataEncoded = encodeURIComponent(JSON.stringify(m));

            // Badges avancés
            let advancedHtml = '';
            if (m.ai_score) {
                advancedHtml += `<div class="ai-score-badge">🤖 AI: ${m.ai_score}</div>`;
            }
            if (m.elo_home && m.elo_away) {
                advancedHtml += `<div class="elo-info">📊 Elo: ${m.elo_home} - ${m.elo_away}</div>`;
            }
            if (m.xg_home && m.xg_away) {
                advancedHtml += `<div class="xg-info">⚽ xG: ${m.xg_home.toFixed(2)} - ${m.xg_away.toFixed(2)}</div>`;
            }
            if (m.fatigue_home || m.fatigue_away) {
                advancedHtml += `<div class="fatigue-info">😓 Fatigue: ${m.fatigue_home || '?'} - ${m.fatigue_away || '?'}</div>`;
            }
            if (m.trap_detected) {
                advancedHtml += `<div class="trap-warning">⚠️ Piège bookmaker</div>`;
            }

            html += `
                <div class="match-card ${winnerClass}" data-match-id="${m.id}">
                    <div class="win-effect"></div>
                    <div class="match-info">
                        <div class="teams">
                            <div class="team">
                                <img src="${homeLogo}" alt="${m.home_team}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${homeDefault}';">
                                <span class="team-name">${m.home_team}</span>
                                <span class="team-score">${m.home_score ?? '-'}</span>
                            </div>
                            <div class="vs">VS</div>
                            <div class="team">
                                <img src="${awayLogo}" alt="${m.away_team}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${awayDefault}';">
                                <span class="team-name">${m.away_team}</span>
                                <span class="team-score">${m.away_score ?? '-'}</span>
                            </div>
                        </div>
                        <div class="match-meta">
                            <span class="league-badge">${m.league || 'Ligue'}</span>
                            <span class="status ${statusClass}">${statusFr}</span>
                            <span class="match-time"><i>🕒</i> ${matchTime}</span>
                            ${m.venue ? `<span class="match-venue"><i>🏟️</i> ${m.venue}</span>` : ''}
                        </div>
                    </div>
                    <div class="analysis-panel ticket ${winnerClass}">
                        <h4>Pronostic ${xpronosBadge}</h4>
                        <p><strong>Double chance :</strong> ${doubleChance} ${eventDate === yesterdayStr ? `<input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled>` : ''}</p>
                        <div class="confidence-bar"><div class="confidence-fill" data-value="${confidence}"></div></div>
                        <p><strong>Fiabilité :</strong> <span class="confidence-text">${confidence}%</span></p>
                        ${premiumBadge}
                        ${advancedHtml}
                        <button class="btn btn-secondary btn-share" data-match='${matchDataEncoded}'>📤 Partager ce prono</button>
                    </div>
                </div>
            `;
        });
    });
    DOM.matches.innerHTML = html;
    document.querySelectorAll('.confidence-fill').forEach(bar => {
        let value = bar.getAttribute('data-value');
        setTimeout(() => { bar.style.width = value + '%'; }, 300);
    });
    document.querySelectorAll('.match-card.winner').forEach(card => {
        for (let i = 0; i < 8; i++) {
            let spark = document.createElement('div');
            spark.className = 'spark';
            let dx = (Math.random() - 0.5) * 200;
            let dy = (Math.random() - 0.5) * 200;
            spark.style.setProperty('--dx', dx + 'px');
            spark.style.setProperty('--dy', dy + 'px');
            spark.style.left = Math.random() * 100 + '%';
            spark.style.top = Math.random() * 100 + '%';
            card.appendChild(spark);
        }
        setTimeout(() => { card.querySelectorAll('.spark').forEach(s => s.remove()); }, 1000);
    });
}

function translateStatus(status) {
    if (!status) return 'À venir';
    const s = status.toLowerCase();
    if (s.includes('finished') || s.includes('terminé') || s.includes('ended')) return 'Terminé';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'En cours';
    if (s.includes('notstarted') || s.includes('à venir')) return 'À venir';
    if (s.includes('postponed')) return 'Reporté';
    if (s.includes('cancelled')) return 'Annulé';
    return status;
}

function getStatusClass(status) {
    if (!status) return '';
    const s = status.toLowerCase();
    if (s.includes('finished') || s.includes('terminé') || s.includes('ended')) return 'finished';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'live';
    return '';
}

// =======================================================
// BOOKMAKERS
// =======================================================
function renderBookmakers(bookmakers) {
    if (!bookmakers || bookmakers.length === 0) {
        console.warn("⚠️ Aucun bookmaker dans data.json → utilisation du fallback");
        bookmakers = [
            { name: "1xBet",     logo: "assets/images/1xbet.webp",     url: "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599" },
            { name: "1win",      logo: "assets/images/1win.webp",      url: "https://1wrbgb.com/?open=register&p=qqcw" },
            { name: "Betwinner", logo: "assets/images/betwinner.webp", url: "https://bwredir.com/299Y" },
            { name: "Melbet",    logo: "assets/images/melbet.webp",    url: "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041" },
            { name: "Linebet",   logo: "assets/images/linebet.webp",   url: "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611" },
            { name: "BetClic",   logo: "assets/images/betclic.webp",   url: "https://betpari-click.com/2vY0?extid=USD" }
        ];
    }
    if (DOM.bookmakersFooter) {
        DOM.bookmakersFooter.innerHTML = '';
        bookmakers.forEach(b => {
            const a = document.createElement('a');
            a.href = b.url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            const img = document.createElement('img');
            img.src = b.logo;
            img.alt = b.name;
            img.style.maxHeight = '40px';
            img.loading = 'lazy';
            img.decoding = 'async';
            img.onerror = function() {
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
        bookmakers.forEach(b => {
            const div = document.createElement('div');
            div.className = 'bookmaker-card';
            const img = document.createElement('img');
            img.src = b.logo;
            img.alt = b.name;
            img.loading = 'lazy';
            img.decoding = 'async';
            img.onerror = function() {
                this.style.display = 'none';
                const span = document.createElement('span');
                span.textContent = b.name;
                span.style.display = 'block';
                span.style.marginBottom = '0.5rem';
                span.style.color = 'var(--or)';
                div.insertBefore(span, div.firstChild);
            };
            div.appendChild(img);
            const title = document.createElement('h3');
            title.textContent = b.name;
            div.appendChild(title);
            const p = document.createElement('p');
            p.textContent = 'Bonus de bienvenue jusqu\'à 130€';
            div.appendChild(p);
            const a = document.createElement('a');
            a.href = b.url;
            a.target = '_blank';
            a.className = 'btn btn-primary';
            a.textContent = 'S\'inscrire avec XPVIP';
            div.appendChild(a);
            DOM.bookmakersBonus.appendChild(div);
        });
    }
}

// =======================================================
// INITIALISATION PRINCIPALE
// =======================================================
document.addEventListener('DOMContentLoaded', async () => {
    await initSupabase();
    await updateDisplayedCounters();
    subscribeToCounters();
    await registerUniqueUser();
    await initOnlineUsers();
    countVisitOncePerDay();
    showIosGuideIfNeeded(); // déjà appelé dans la section PWA, mais on le laisse aussi ici par sécurité

    // Initialisation selon la page
    if (DOM.matches) {
        setupEventListeners();
        await loadData();
    } else if (DOM.historyContainer) {
        displayHistory();
    } else if (DOM.bonusSelect) {
        initBonusPage();
    } else {
        // Page d'accueil
        await loadDataGeneric().then(data => {
            if (data) {
                allData = data;
                renderBookmakers(data.bookmakers);
                updateShareCounter();
                displayLatestVerified();
                startWinsSlider();
                animateWins();
                updateHomeSuccessRate();
            }
        });
        displayTestimonials();
        startWinNotifications();
    }

    displayBlogList();
    displayBlogPost();
    displayConseils();
    displayInfos();
    displayFootNews();
    initScrollProgress();

    if (DOM.searchInput) {
        DOM.searchInput.addEventListener('input', (e) => {
            searchTerm = e.target.value;
            applySearchFilter();
        });
    }

    document.addEventListener('visibilitychange', () => {
        if (sharePending && !document.hidden) {
            const elapsed = Date.now() - shareStartTime;
            if (elapsed >= 5000) {
                sharePending = false;
                const newCount = incrementShareCount();
                updateShareCounter();
                incrementCounter('total_shares').catch(e => console.warn('Erreur incrémentation', e));
                recordEvent('share', window.location.pathname);
                const target = shareLimits[currentCategory];
                if (newCount >= target) {
                    hideVipLocked();
                    filterAndDisplay();
                } else {
                    if (DOM.vipLockedOverlay && DOM.vipLockedOverlay.style.display === 'flex') {
                        showVipLocked(currentCategory);
                    } else {
                        showSharePopup(currentCategory, target - newCount);
                    }
                }
            }
        }
    });
    recordEvent('visit', window.location.pathname);
});

// =======================================================
// FONCTIONS POUR LES PAGES SPÉCIFIQUES (HISTORIQUE, BONUS, etc.)
// =======================================================
async function loadDataGeneric() {
    try {
        const resp = await fetch('data.json?t=' + Date.now());
        if (!resp.ok) throw new Error('Erreur');
        const data = await resp.json();
        localStorage.setItem('cachedData', JSON.stringify(data));
        return data;
    } catch {
        const cached = localStorage.getItem('cachedData');
        return cached ? JSON.parse(cached) : null;
    }
}

async function displayHistory() {
    if (!DOM.historyContainer) return;
    await loadData();
    if (!allData || !allData.matches) {
        DOM.historyContainer.innerHTML = '<div class="no-events">Aucun historique disponible.</div>';
        return;
    }
    const today = new Date(); today.setHours(0,0,0,0);
    let historyMatches = allData.matches.filter(m => new Date(m.event_date) < today);
    if (historyMatches.length === 0) {
        DOM.historyContainer.innerHTML = '<div class="no-events">Aucun match dans cette période.</div>';
        return;
    }
    const catOrder = { vip: 0, pro: 1, simple: 2 };
    historyMatches.sort((a,b) => {
        const orderA = catOrder[a.category] !== undefined ? catOrder[a.category] : 3;
        const orderB = catOrder[b.category] !== undefined ? catOrder[b.category] : 3;
        if (orderA !== orderB) return orderA - orderB;
        return new Date(b.event_date) - new Date(a.event_date);
    });
    const groupedByDay = {};
    historyMatches.forEach(m => {
        const dateStr = getLocalDateFromEvent(m.event_date);
        if (!groupedByDay[dateStr]) groupedByDay[dateStr] = [];
        groupedByDay[dateStr].push(m);
    });
    let html = '';
    const sortedDays = Object.keys(groupedByDay).sort((a,b) => new Date(b) - new Date(a));
    sortedDays.forEach(day => {
        const dayDate = new Date(day + 'T12:00:00');
        const formattedDate = dayDate.toLocaleDateString('fr-FR', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
        html += `<h2 class="day-header" style="color: var(--or); margin-top: 2rem;">${formattedDate}</h2>`;
        groupedByDay[day].forEach(m => {
            const pred = m.prediction || {};
            const doubleChance = pred.double_chance || 'N/A';
            let confidence = pred.confidence || 0;
            if (typeof confidence === 'string') confidence = parseFloat(confidence);
            if (isNaN(confidence)) confidence = 0;
            if (confidence > 100) confidence = confidence / 100;
            confidence = Math.min(100, Math.round(confidence * 10) / 10);
            const matchTime = formatMatchTime(m.event_date);
            const statusFr = translateStatus(m.status);
            const statusClass = getStatusClass(m.status);
            const verifiedDouble = m.verified_double ? 'checked' : '';
            const homeDefault = 'assets/images/home.webp';
            const awayDefault = 'assets/images/away.webp';
            const homeLogo = m.home_logo || getTeamLogoPath(m.home_team, true);
            const awayLogo = m.away_logo || getTeamLogoPath(m.away_team, false);
            const isWinner = m.verified_double;
            const winnerClass = isWinner ? 'winner' : '';
            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';
            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const categoryBadge = m.category ? `<span class="badge-category badge-${m.category}">${m.category.toUpperCase()}</span>` : '';
            html += `
                <div class="match-card ${winnerClass}">
                    <div class="match-info">
                        <div class="teams">
                            <div class="team"><img src="${homeLogo}" alt="${m.home_team}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${homeDefault}';"><span class="team-name">${m.home_team}</span><span class="team-score">${m.home_score ?? '-'}</span></div>
                            <div class="vs">VS</div>
                            <div class="team"><img src="${awayLogo}" alt="${m.away_team}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${awayDefault}';"><span class="team-name">${m.away_team}</span><span class="team-score">${m.away_score ?? '-'}</span></div>
                        </div>
                        <div class="match-meta">
                            <span class="league-badge">${m.league || 'Ligue'}</span>
                            <span class="status ${statusClass}">${statusFr}</span>
                            <span class="match-time"><i>🕒</i> ${matchTime}</span>
                        </div>
                    </div>
                    <div class="analysis-panel">
                        <h4>Pronostic ${xpronosBadge} ${categoryBadge}</h4>
                        <p><strong>Double chance :</strong> ${doubleChance} <input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled></p>
                        <p><strong>Fiabilité :</strong> ${confidence}%</p>
                        ${premiumBadge}
                    </div>
                </div>
            `;
        });
    });
    DOM.historyContainer.innerHTML = html;
}

function initBonusPage() {
    // À implémenter si nécessaire
}

function displayLatestVerified() {
    if (!DOM.todayPicks) return;
    if (!allData || !allData.matches) {
        DOM.todayPicks.innerHTML = '<div class="loading">Chargement...</div>';
        return;
    }
    const verified = allData.matches.filter(m => {
        if (!m.status) return false;
        const statusLower = m.status.toLowerCase();
        const isFinished = statusLower.includes('finished') || statusLower.includes('terminé') || statusLower.includes('ended');
        if (!isFinished) return false;
        return m.verified_double && (m.category === 'pro' || m.category === 'vip');
    });
    const latest = [...verified].sort((a,b) => new Date(b.event_date) - new Date(a.event_date)).slice(0,4);
    if (latest.length === 0) {
        DOM.todayPicks.innerHTML = '<div class="no-events">📭 Aucun pronostic validé récent. Revenez plus tard !</div>';
        return;
    }
    let html = '';
    latest.forEach(m => {
        const pred = m.prediction || {};
        const doubleChance = pred.double_chance || 'N/A';
        const confidence = pred.confidence || 0;
        const matchTime = formatMatchTime(m.event_date);
        const statusFr = translateStatus(m.status);
        const statusClass = getStatusClass(m.status);
        const homeDefault = 'assets/images/home.webp';
        const awayDefault = 'assets/images/away.webp';
        const homeLogo = m.home_logo || getTeamLogoPath(m.home_team, true);
        const awayLogo = m.away_logo || getTeamLogoPath(m.away_team, false);
        const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';
        const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
        const categoryBadge = m.category ? `<span class="badge-category badge-${m.category}">${m.category.toUpperCase()}</span>` : '';
        html += `
            <div class="match-card winner" data-match-id="${m.id}">
                <div class="win-effect"></div>
                <div class="match-info">
                    <div class="teams">
                        <div class="team"><img src="${homeLogo}" alt="${m.home_team}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${homeDefault}';"><span class="team-name">${m.home_team}</span><span class="team-score">${m.home_score ?? '-'}</span></div>
                        <div class="vs">VS</div>
                        <div class="team"><img src="${awayLogo}" alt="${m.away_team}" class="team-logo" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${awayDefault}';"><span class="team-name">${m.away_team}</span><span class="team-score">${m.away_score ?? '-'}</span></div>
                    </div>
                    <div class="match-meta">
                        <span class="league-badge">${m.league || 'Ligue'}</span>
                        <span class="status ${statusClass}">${statusFr}</span>
                        <span class="match-time"><i>🕒</i> ${matchTime}</span>
                        ${m.venue ? `<span class="match-venue"><i>🏟️</i> ${m.venue}</span>` : ''}
                    </div>
                </div>
                <div class="analysis-panel">
                    <h4>Pronostic ${xpronosBadge} ${categoryBadge}</h4>
                    <p><strong>Double chance :</strong> ${doubleChance} <input type="checkbox" class="prediction-checkbox" checked disabled></p>
                    <p><strong>Fiabilité :</strong> ${confidence}%</p>
                    ${premiumBadge}
                </div>
            </div>
        `;
    });
    DOM.todayPicks.innerHTML = html;
}

function startWinsSlider() {
    if (!DOM.winsTrack || !allData || !allData.matches) return;
    const wins = allData.matches.filter(m => {
        if (!m.status) return false;
        const statusLower = m.status.toLowerCase();
        const isFinished = statusLower.includes('finished') || statusLower.includes('terminé') || statusLower.includes('ended');
        if (!isFinished) return false;
        return m.verified_double;
    }).sort((a,b) => new Date(b.event_date) - new Date(a.event_date)).slice(0,10);
    let html = '';
    wins.forEach(m => {
        const score = `${m.home_score ?? '-'} - ${m.away_score ?? '-'}`;
        html += `<div class="win-item">✅ <span>${m.home_team} ${score} ${m.away_team}</span> 🏆 ${m.prediction?.double_chance || ''}</div>`;
    });
    DOM.winsTrack.innerHTML = html + html;
}

function startWinNotifications() {
    if (!DOM.winPopup) return;
    const firstNames = ["Jean","Michel","David","Lucas","Thomas","Patrick","Samuel","Kevin","Éric","Daniel","Pierre","Philippe","Nicolas","François","Antoine"];
    const lastNames = ["Martin","Bernard","Dubois","Thomas","Robert","Richard","Petit","Durand","Leroy","Moreau","Simon","Laurent","Lefebvre","Michel","Garcia"];
    let usedNames = new Set();
    let notifications = [];
    while (notifications.length < 5) {
        const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
        const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
        const fullName = `${firstName} ${lastName}`;
        if (!usedNames.has(fullName)) {
            usedNames.add(fullName);
            const gain = Math.floor(Math.random() * (200 - 45 + 1)) + 45;
            notifications.push({ name: fullName, gain });
        }
    }
    let index = 0;
    function showPopup() {
        const { name, gain } = notifications[index];
        DOM.winPopup.innerHTML = `💰 <b>${name}</b> a gagné <b>${gain}€</b> aujourd'hui grâce au VIP !`;
        DOM.winPopup.classList.add('show');
        setTimeout(() => DOM.winPopup.classList.remove('show'), 4000);
        index = (index + 1) % notifications.length;
    }
    setInterval(showPopup, 3600000);
    showPopup();
}

function animateWins() {
    if (!DOM.winsCount || !allData || !allData.matches) return;
    const winsCount = allData.matches.filter(m => {
        if (!m.status) return false;
        const statusLower = m.status.toLowerCase();
        const isFinished = statusLower.includes('finished') || statusLower.includes('terminé') || statusLower.includes('ended');
        if (!isFinished) return false;
        return m.verified_double;
    }).length;
    let count = 0;
    const target = winsCount;
    const interval = setInterval(() => {
        count++;
        DOM.winsCount.textContent = count;
        if (count >= target) clearInterval(interval);
    }, 20);
}

function initScrollProgress() {
    const progressBar = document.createElement('div');
    progressBar.className = 'scroll-progress';
    document.body.appendChild(progressBar);
    window.addEventListener('scroll', () => {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (winScroll / height) * 100;
        progressBar.style.width = scrolled + '%';
    });
}

async function displayTestimonials() {
    if (!DOM.testimonials) return;
    try {
        const resp = await fetch('testimonials.json?t=' + Date.now());
        if (!resp.ok) throw new Error('Erreur');
        const testimonials = await resp.json();
        let html = '';
        testimonials.forEach(t => {
            html += `<div class="card"><p>"${t.text}"</p><p style="margin-top: 1rem; color: var(--or);">— ${t.name}</p></div>`;
        });
        DOM.testimonials.innerHTML = html;
    } catch (e) {
        console.error('Erreur chargement témoignages', e);
        DOM.testimonials.innerHTML = `
            <div class="card"><p>"Grâce à Mr XPRONOS, j'ai multiplié mes gains par 3 en un mois !"</p><p style="margin-top:1rem;color:var(--or);">— Jean Martin</p></div>
            <div class="card"><p>"Les pronostics VIP sont incroyablement précis. Je recommande !"</p><p style="margin-top:1rem;color:var(--or);">— Marie Dubois</p></div>
            <div class="card"><p>"Le système de partage permet d'accéder à des analyses de qualité gratuitement."</p><p style="margin-top:1rem;color:var(--or);">— Thomas Petit</p></div>
        `;
    }
}

// =======================================================
// FONCTIONS POUR LE CONTENU (blog, conseils, news)
// =======================================================
async function loadGeneratedContent() {
    try {
        const articlesResp = await fetch('articles.json?t=' + Date.now());
        if (articlesResp.ok) window.generatedArticles = await articlesResp.json();
        const conseilsResp = await fetch('conseils.json?t=' + Date.now());
        if (conseilsResp.ok) window.generatedConseils = await conseilsResp.json();
    } catch (error) { console.error('Erreur chargement contenu généré:', error); }
}

async function displayBlogList() {
    const container = document.getElementById('blog-list');
    if (!container) return;
    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    let allArticles = [...(window.generatedArticles || []), ...(data?.blog || [])];
    // Filtrer les articles inactifs (champ active === false)
    allArticles = allArticles.filter(a => a.active !== false);
    if (allArticles.length === 0) { container.innerHTML = '<div class="no-events">Aucun article.</div>'; return; }
    window.articlesData = allArticles;
    const horizontalContainer = document.getElementById('blog-horizontal-list');
    if (horizontalContainer) {
        let hHtml = '';
        allArticles.slice(0,8).forEach((article,index) => {
            const title = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
            hHtml += `<div class="horizontal-item" onclick="showArticleDetail(${index})"><img src="${article.image_url || 'assets/images/default-logo.png'}" alt="${title}" loading="lazy"><div class="item-title">${title}</div></div>`;
        });
        horizontalContainer.innerHTML = hHtml;
    }
    let html = '';
    allArticles.forEach((article,index) => {
        let cleanTitle = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
        let excerpt = article.excerpt || article.content.substring(0,150) + '...';
        let cleanExcerpt = excerpt.replace(/#+\s*/g,'').replace(/\*\*/g,'').replace(/\*/g,'').replace(/\[|\]/g,'').substring(0,120) + '...';
        let imageUrl = article.image_url || 'assets/images/default-logo.png';
        let articleDate = article.date ? new Date(article.date).toLocaleDateString('fr-FR') : '';
        html += `
            <div class="news-card card" onclick="showArticleDetail(${index})">
                <img src="${imageUrl}" alt="${cleanTitle}" loading="lazy" class="news-image">
                <h3>${cleanTitle}</h3>
                <p class="meta">${articleDate} par ${article.author || 'Mr XPRONOS'}</p>
                <p>${cleanExcerpt}</p>
                <button class="btn btn-secondary" style="margin-top:10px;">Lire la suite</button>
            </div>
        `;
    });
    container.innerHTML = html;
}

window.showArticleDetail = function(index) {
    const article = window.articlesData[index];
    if (!article) return;
    if (!DOM.articleModal) return;
    document.getElementById('article-modal-title').textContent = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
    document.getElementById('article-modal-image').src = article.image_url || 'assets/images/default-logo.png';
    let content = article.content;
    if (window.marked) content = window.marked.parse(content);
    else content = content.replace(/\n/g,'<br>');
    document.getElementById('article-modal-content').innerHTML = content;
    document.getElementById('article-modal-link').href = 'article.html?slug=' + article.slug;
    DOM.articleModal.style.display = 'flex';
};

window.closeArticleModal = function() {
    if (DOM.articleModal) DOM.articleModal.style.display = 'none';
};

async function displayBlogPost() {
    const container = document.getElementById('blog-post');
    if (!container) return;
    const urlParams = new URLSearchParams(window.location.search);
    const slug = urlParams.get('slug');
    if (!slug) { container.innerHTML = '<p>Article non trouvé.</p>'; return; }
    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    let allArticles = [...(window.generatedArticles || []), ...(data?.blog || [])];
    allArticles = allArticles.filter(a => a.active !== false);
    const article = allArticles.find(a => a.slug === slug);
    if (!article) { container.innerHTML = '<p>Article non trouvé.</p>'; return; }
    let cleanTitle = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
    document.title = cleanTitle + ' - Mr XPRONOS';
    const description = article.excerpt || article.content.substring(0,150).replace(/[#*]/g,'') + '...';
    const imageUrl = article.image_url || 'https://mrxpronos.github.io/MrXPRONOS_App/assets/images/preview.jpg';
    const fullUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/article.html?slug=' + encodeURIComponent(slug);
    document.getElementById('article-description')?.setAttribute('content', description);
    document.getElementById('og-title')?.setAttribute('content', cleanTitle);
    document.getElementById('og-description')?.setAttribute('content', description);
    document.getElementById('og-image')?.setAttribute('content', imageUrl);
    document.getElementById('og-url')?.setAttribute('content', fullUrl);
    document.getElementById('twitter-title')?.setAttribute('content', cleanTitle);
    document.getElementById('twitter-description')?.setAttribute('content', description);
    document.getElementById('twitter-image')?.setAttribute('content', imageUrl);
    const jsonLd = {
        "@context":"https://schema.org","@type":"Article","headline":cleanTitle,"description":description,"image":imageUrl,
        "author":{"@type":"Person","name":article.author||"Mr XPRONOS"},
        "publisher":{"@type":"Organization","name":"Mr XPRONOS","logo":{"@type":"ImageObject","url":"https://mrxpronos.github.io/MrXPRONOS_App/assets/images/icon-192.webp"}},
        "datePublished":article.date,"dateModified":article.date,"mainEntityOfPage":fullUrl
    };
    document.getElementById('article-jsonld').textContent = JSON.stringify(jsonLd);
    let htmlContent = article.content;
    if (window.marked) htmlContent = window.marked.parse(htmlContent);
    else htmlContent = htmlContent.replace(/\n/g,'<br>');
    container.innerHTML = `
        <h1>${cleanTitle}</h1>
        <div class="meta">${article.date} par ${article.author}</div>
        ${article.image_url ? `<img src="${article.image_url}" alt="${cleanTitle}" loading="lazy">` : ''}
        <div style="margin-top: 2rem;">${htmlContent}</div>
        <a href="blog.html" class="btn btn-secondary" style="margin-top: 2rem;">← Retour au blog</a>
    `;
}

async function displayConseils() {
    const container = document.getElementById('conseils-list');
    if (!container) return;
    if (!window.generatedConseils) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const allConseils = [...(window.generatedConseils || []), ...(data?.conseils || [])];
    if (allConseils.length === 0) { container.innerHTML = '<div class="no-events">Aucun conseil.</div>'; return; }
    window.conseilsData = allConseils;
    const horizontalContainer = document.getElementById('conseils-horizontal-list');
    if (horizontalContainer) {
        let hHtml = '';
        allConseils.slice(0,8).forEach((conseil,index) => {
            const title = conseil.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
            hHtml += `<div class="horizontal-item" onclick="showConseilDetail(${index})"><img src="${conseil.image_url || 'assets/images/default-logo.png'}" alt="${title}" loading="lazy"><div class="item-title">${title}</div></div>`;
        });
        horizontalContainer.innerHTML = hHtml;
    }
    let html = '';
    allConseils.forEach((conseil,index) => {
        let cleanTitle = conseil.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
        let excerpt = conseil.content.substring(0,150) + '...';
        let cleanExcerpt = excerpt.replace(/#+\s*/g,'').replace(/\*\*/g,'').replace(/\*/g,'').replace(/\[|\]/g,'').substring(0,120) + '...';
        let imageUrl = conseil.image_url || 'assets/images/default-logo.png';
        let conseilDate = conseil.date ? new Date(conseil.date).toLocaleDateString('fr-FR') : '';
        html += `
            <div class="news-card card" onclick="showConseilDetail(${index})">
                <img src="${imageUrl}" alt="${cleanTitle}" loading="lazy" class="news-image">
                <h3>${cleanTitle}</h3>
                <p class="meta">${conseilDate}</p>
                <p>${cleanExcerpt}</p>
                <button class="btn btn-secondary" style="margin-top:10px;">Lire le conseil</button>
            </div>
        `;
    });
    container.innerHTML = html;
}

window.showConseilDetail = function(index) {
    const conseil = window.conseilsData[index];
    if (!conseil) return;
    if (!DOM.conseilModal) return;
    document.getElementById('conseil-modal-title').textContent = conseil.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
    document.getElementById('conseil-modal-image').src = conseil.image_url || 'assets/images/default-logo.png';
    let content = conseil.content;
    if (window.marked) content = window.marked.parse(content);
    else content = content.replace(/\n/g,'<br>');
    document.getElementById('conseil-modal-content').innerHTML = content;
    DOM.conseilModal.style.display = 'flex';
};

window.closeConseilModal = function() {
    if (DOM.conseilModal) DOM.conseilModal.style.display = 'none';
};

async function displayInfos() {
    const container = document.getElementById('infos-list');
    if (!container) return;
    const data = await loadDataGeneric();
    if (!data || !data.infos) return;
    let html = '';
    data.infos.forEach(i => { html += `<div class="news-card card"><h3>${i.title}</h3><p>${i.content}</p></div>`; });
    container.innerHTML = html;
}

async function displayFootNews() {
    const container = document.getElementById('foot-news-container');
    if (!container) return;
    try {
        const resp = await fetch('footnews.json?t=' + Date.now());
        if (!resp.ok) throw new Error('Erreur chargement');
        const news = await resp.json();
        if (news.length === 0) { container.innerHTML = '<div class="no-events">Aucune actualité pour le moment.</div>'; return; }
        window.newsData = news;
        let html = '';
        news.forEach((item,index) => {
            html += `
                <div class="news-card card" onclick="showNewsDetail(${index})">
                    ${item.image ? `<img src="${item.image}" alt="${item.title}" class="news-image" loading="lazy">` : ''}
                    <h3>${item.title}</h3>
                    <p class="meta">${new Date(item.published).toLocaleDateString('fr-FR')}</p>
                    <p>${item.summary}</p>
                    <button class="btn btn-secondary" style="margin-top:10px;">Lire la suite</button>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (error) {
        console.error('Erreur chargement actualités:', error);
        container.innerHTML = '<div class="error">Impossible de charger les actualités.</div>';
    }
}

window.showNewsDetail = function(index) {
    const news = window.newsData[index];
    if (!news) return;
    if (!DOM.newsModal) return;
    document.getElementById('news-modal-title').textContent = news.title;
    document.getElementById('news-modal-image').src = news.image || 'assets/images/default-logo.png';
    let content = news.summary;
    if (window.marked) content = window.marked.parse(content);
    else content = content.replace(/\n/g,'<br>');
    content += '<p><em>Source: BBC</em></p>';
    document.getElementById('news-modal-content').innerHTML = content;
    document.getElementById('news-modal-link').href = news.link || '#';
    DOM.newsModal.style.display = 'flex';
};

window.closeNewsModal = function() {
    if (DOM.newsModal) DOM.newsModal.style.display = 'none';
};

// =======================================================
// FONCTIONS VIP
// =======================================================
async function checkVipStatus() {
    if (!supabaseAvailable) return false;
    const userId = getUserId();
    const storedCode = localStorage.getItem('mx_vip_code');
    if (!storedCode) return false;
    try {
        const { data, error } = await supabase.rpc('check_vip_code', { 
            p_user_id: userId, 
            p_code: storedCode 
        });
        if (error) throw error;
        return data.valid === true;
    } catch (e) {
        console.error('Erreur vérification VIP:', e);
        return false;
    }
}

function showVipLoginForm(container) {
    const userId = getUserId();
    container.innerHTML = `
        <div class="vip-locked-content" style="display:block;">
            <div class="lock-icon">💎</div>
            <h3>🔐 Accès VIP Payant</h3>
            <p><strong>Votre ID :</strong> ${userId}</p>
            <p>Pour obtenir un code VIP (5000 FCFA/mois), contactez-nous sur WhatsApp ou Telegram avec votre ID.</p>
            <div class="vip-contact-buttons" style="display: flex; gap: 10px; justify-content: center; margin: 20px 0;">
                <a href="https://wa.me/22899201444?text=Bonjour%2C%20voici%20mon%20ID%20VIP%20${encodeURIComponent(userId)}" target="_blank" class="btn btn-primary">WhatsApp</a>
                <a href="https://t.me/mr_xpronos?text=Bonjour%2C%20voici%20mon%20ID%20VIP%20${encodeURIComponent(userId)}" target="_blank" class="btn btn-primary">Telegram</a>
            </div>
            <hr style="border-color:#444; margin:20px 0;">
            <p>Si vous avez déjà un code, saisissez-le ci-dessous :</p>
            <input type="text" id="vip-code-input" placeholder="Code VIP" style="width:100%; padding:10px; margin-bottom:10px; border-radius:8px; border:1px solid #D4AF37; background:#0D0D0D; color:#fff;">
            <button id="vip-activate-btn" class="btn btn-primary" style="width:100%;">Activer</button>
            <button id="vip-close-btn" class="btn btn-secondary" style="width:100%; margin-top:10px;">Fermer</button>
        </div>
    `;
    document.getElementById('vip-activate-btn').addEventListener('click', async () => {
        const code = document.getElementById('vip-code-input').value.trim();
        if (!code) { alert('Veuillez entrer un code.'); return; }
        const userId = getUserId();
        try {
            const { data, error } = await supabase.rpc('check_vip_code', { p_user_id: userId, p_code: code });
            if (error || !data.valid) throw new Error('Code invalide');
            localStorage.setItem('mx_vip_code', code);
            recordEvent('vip_conversion', window.location.pathname);
            showToast('Code VIP activé avec succès !', 'success');
            window.location.reload();
        } catch (e) {
            alert('Code invalide ou expiré.');
        }
    });
    document.getElementById('vip-close-btn').addEventListener('click', () => {
        container.style.display = 'none';
        if (DOM.matches) DOM.matches.style.display = 'grid';
    });
}