/**
 * main.js - Mr XPRONOS – Version ultime (corrigée)
 * Toutes les fonctionnalités sont regroupées dans ce seul fichier.
 */

// =======================================================
// Désactiver les logs en production
// =======================================================
if (location.hostname !== 'localhost' && !location.hostname.includes('127.0.0.1')) {
    console.log = function() {};
    console.warn = function() {};
    console.error = function() {};
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

// Éléments DOM fréquemment utilisés
const matchesContainer = document.getElementById('matches-container');
let sharePopup = document.getElementById('share-popup');
const vipLockedOverlay = document.getElementById('vip-locked-overlay');
const bookmakersFooter = document.getElementById('bookmakers-footer');
const bookmakersBonus = document.getElementById('bookmakers-bonus');
const vipSubtabs = document.getElementById('vip-subtabs');

// =======================================================
// FONCTIONS UTILITAIRES (toasts, IDs, etc.)
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
        userId = 'MX-' + Math.random().toString(36).substring(2, 10).toUpperCase();
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
// GESTION DES COMPTEURS (visites, partages)
// =======================================================
async function incrementCounter(counterName) {
    if (!supabaseAvailable) return;
    try {
        await supabase.rpc('increment_counter', { counter_name: counterName });
    } catch (e) { console.error('Erreur incrémentation:', e); }
}

async function updateDisplayedCounters() {
    if (!supabaseAvailable) return;
    try {
        const { data, error } = await supabase
            .from('counters')
            .select('total_users, total_shares')
            .eq('id', 1)
            .single();
        if (error) throw error;
        const usersEl = document.getElementById('total-users-count');
        const sharesEl = document.getElementById('total-shares-count');
        if (usersEl) usersEl.textContent = data.total_users.toLocaleString() + '+';
        if (sharesEl) sharesEl.textContent = data.total_shares.toLocaleString() + '+';
    } catch (e) { console.error('Erreur récupération counters:', e); }
}

function subscribeToCounters() {
    if (!supabaseAvailable) return;
    supabase
        .channel('counters-live')
        .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'counters' }, (payload) => {
            const usersEl = document.getElementById('total-users-count');
            const sharesEl = document.getElementById('total-shares-count');
            if (usersEl) usersEl.textContent = payload.new.total_users.toLocaleString() + '+';
            if (sharesEl) sharesEl.textContent = payload.new.total_shares.toLocaleString() + '+';
        })
        .subscribe();
}

function recordEvent(type) {
    const userId = getUserId();
    const page = window.location.pathname;
    if (supabaseAvailable) {
        supabase.from('events').insert({ type, user_id: userId, page })
            .then(({ error }) => { if (error) console.warn('Erreur envoi événement:', error); })
            .catch(e => console.warn('Erreur réseau Supabase', e));
    }
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
    const counter = document.getElementById('share-counter');
    if (counter) {
        const count = getDailyShareCount();
        counter.textContent = `🔥 ${count} partages aujourd'hui`;
    }
}

// =======================================================
// PWA & INSTALLATION
// =======================================================
let deferredPrompt;
const installButton = document.getElementById('install-app');
const iosGuidePopup = document.getElementById('ios-guide-popup');

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
        if (iosGuidePopup) iosGuidePopup.style.display = 'flex';
    }
}

function closeIosGuide() {
    if (iosGuidePopup) iosGuidePopup.style.display = 'none';
    localStorage.setItem('iosGuideLastClosed', Date.now().toString());
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installButton && !isPwaInstalled() && getOS() !== 'iOS') {
        installButton.style.display = 'inline-block';
    }
});

installButton?.addEventListener('click', async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`Installation : ${outcome}`);
    deferredPrompt = null;
    installButton.style.display = 'none';
});

window.addEventListener('appinstalled', () => {
    console.log('PWA installée');
    if (installButton) installButton.style.display = 'none';
    if (iosGuidePopup) iosGuidePopup.style.display = 'none';
});

document.getElementById('close-ios-guide')?.addEventListener('click', closeIosGuide);
document.getElementById('close-ios-guide-btn')?.addEventListener('click', closeIosGuide);

// =======================================================
// CHARGEMENT DES DONNÉES (data.json)
// =======================================================
async function loadData() {
    console.log('🔄 Chargement des pronostics...');
    if (matchesContainer) {
        matchesContainer.innerHTML = `<div style="text-align:center; padding:80px 20px; color:#aaa;"><div style="font-size:60px; margin-bottom:20px;">⏳</div><div>Chargement des matchs...</div></div>`;
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
        if (matchesContainer && !navigator.onLine) {
            matchesContainer.insertAdjacentHTML('afterbegin', `<div style="background:#ffcc00; color:#000; text-align:center; padding:8px; font-weight:700; font-size:0.95rem;">📴 MODE HORS LIGNE — Pronostics du cache (${new Date().toLocaleDateString('fr-FR')})</div>`);
        }
        renderBookmakers(allData.bookmakers);
        hideEmptyTabs();
        maybeHideTabBar();
        filterAndDisplay();
    } else if (matchesContainer) {
        matchesContainer.innerHTML = `<div class="error" style="text-align:center; padding:60px;">❌ Aucune donnée disponible.<br><small>Connectez-vous une première fois pour charger le cache.</small></div>`;
    }
}

// =======================================================
// FILTRAGE ET AFFICHAGE
// =======================================================
function hideEmptyTabs() {
    const vipEnabled = localStorage.getItem('vipEnabled') !== 'false'; // true par défaut
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
    if (vipSubtabs) {
        const showPronostics = counts.vip > 0 && vipEnabled;
        const subtabBtns = vipSubtabs.querySelectorAll('.subtab-btn');
        if (subtabBtns.length >= 1) subtabBtns[0].style.display = showPronostics ? 'inline-block' : 'none';
        vipSubtabs.style.display = showPronostics ? 'flex' : 'none';
        const activeSub = vipSubtabs.querySelector('.subtab-btn.active');
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
        if (sharePopup) sharePopup.classList.remove('active');
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
            // Revenir à la catégorie simple
            currentCategory = 'simple';
            document.querySelector('.tab-btn[data-cat="simple"]').classList.add('active');
            document.querySelector('.tab-btn[data-cat="vip"]').classList.remove('active');
            filterAndDisplay();
            return;
        }
        const isVip = await checkVipStatus();
        if (!isVip) {
            if (vipLockedOverlay) {
                ensureVipOverlayStructure();
                showVipLoginForm(vipLockedOverlay);
                vipLockedOverlay.style.display = 'flex';
                if (matchesContainer) matchesContainer.style.display = 'none';
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

    if (vipLockedOverlay) {
        ensureVipOverlayStructure();
        
        const titleEl = vipLockedOverlay.querySelector('h3');
        const textEl = vipLockedOverlay.querySelector('p');
        const shareCountEl = document.getElementById('share-count-locked');
        const shareTargetEl = document.getElementById('share-target-locked');

        if (titleEl) titleEl.textContent = `🔒 ${category === 'pro' ? 'Pronostics Pro' : 'Pronostics VIP'} verrouillés`;
        if (textEl) textEl.innerHTML = `Partagez ce lien à <strong>${remaining}</strong> ami(s) pour débloquer.`;
        if (shareCountEl) shareCountEl.textContent = shareCount;
        if (shareTargetEl) shareTargetEl.textContent = target;

        vipLockedOverlay.style.display = 'flex';
        if (matchesContainer) matchesContainer.style.display = 'none';
    } else {
        showSharePopup(category, remaining);
    }
}

function ensureVipOverlayStructure() {
    if (!vipLockedOverlay) return;
    if (vipLockedOverlay.children.length === 0) {
        vipLockedOverlay.innerHTML = `
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
            vipLockedOverlay.style.display = 'none';
            if (matchesContainer) matchesContainer.style.display = 'grid';
        });
    }
}

function hideVipLocked() {
    if (vipLockedOverlay) {
        vipLockedOverlay.style.display = 'none';
        if (matchesContainer) matchesContainer.style.display = 'grid';
    }
}

function showSharePopup(category, remaining) {
    if (!sharePopup) {
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

    sharePopup.classList.add('active');
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
    sharePopup = popup;
    document.getElementById('share-wa').addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg').addEventListener('click', () => share('telegram'));
    document.getElementById('close-popup').addEventListener('click', () => {
        sharePopup.classList.remove('active');
    });
}

function share(platform) {
    const baseUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    let message = platform === 'whatsapp' 
        ? `🔥 *Mr XPRONOS* – 3 matchs à ne pas manquer aujourd'hui !\n\n📊 *Analyses exclusives* et pronostics fiables.\n\n👉 Débloque l'accès PRO en partageant ce lien :\n${baseUrl}\n\n⚽ Arrête de perdre ton argent, rejoins les gagnants !`
        : `🔥 Mr XPRONOS – 3 matchs à ne pas manquer aujourd'hui !\n\n📊 Analyses exclusives et pronostics fiables.\n\n👉 Débloque l'accès PRO en partageant ce lien :\n${baseUrl}\n\n⚽ Arrête de perdre ton argent, rejoins les gagnants !`;
    const url = platform === 'whatsapp' 
        ? `https://wa.me/?text=${encodeURIComponent(message)}`
        : `https://t.me/share/url?url=${encodeURIComponent(baseUrl)}&text=${encodeURIComponent(message)}`;
    window.open(url, '_blank');
    shareStartTime = Date.now();
    sharePending = true;
}

function sharePronostic(match) {
    const siteUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    const messageWhatsApp = `🔥 *Mr XPRONOS* – Pronostic du jour\n\n⚽ *${match.home_team} vs ${match.away_team}*\n📈 *Double chance* : ${match.prediction.double_chance} – Fiabilité ${match.prediction.confidence}%\n\n👉 Analyse complète sur ${siteUrl}`;
    const messageTelegram = `🔥 Mr XPRONOS – Pronostic du jour\n\n⚽ ${match.home_team} vs ${match.away_team}\n📈 Double chance : ${match.prediction.double_chance} – Fiabilité ${match.prediction.confidence}%\n\n👉 Analyse complète sur ${siteUrl}`;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(messageWhatsApp)}`;
    const telegramUrl = `https://t.me/share/url?url=${encodeURIComponent(siteUrl)}&text=${encodeURIComponent(messageTelegram)}`;
    if (confirm("Partager sur WhatsApp ? (OK = WhatsApp, Annuler = Telegram)")) {
        window.open(whatsappUrl, '_blank');
    } else {
        window.open(telegramUrl, '_blank');
    }
    incrementShareCount();
    incrementCounter('total_shares').catch(e => console.warn('Erreur incrémentation', e));
    recordEvent('share');
}

// =======================================================
// FONCTIONS DE FILTRAGE DES MATCHS
// =======================================================
function getLocalDateString(day) {
    const now = new Date();
    const target = new Date(now);
    if (day === 'tomorrow') target.setDate(now.getDate() + 1);
    else if (day === 'yesterday') target.setDate(now.getDate() - 1);
    const year = target.getFullYear();
    const month = String(target.getMonth() + 1).padStart(2, '0');
    const dayOfMonth = String(target.getDate()).padStart(2, '0');
    return `${year}-${month}-${dayOfMonth}`;
}

function getLocalDateFromEvent(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    if (isNaN(date)) return null;
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
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
        if (matchesContainer) matchesContainer.innerHTML = '<div class="no-events">Aucun match disponible.</div>';
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
    if (!matchesContainer) return;
    if (matches.length === 0) {
        matchesContainer.innerHTML = '<div class="no-events">Aucun match.</div>';
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
            const homeLogo = getTeamLogoPath(m.home_team, true);
            const awayLogo = getTeamLogoPath(m.away_team, false);
            const isWinner = m.verified_double;
            const winnerClass = isWinner ? 'winner' : '';
            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';
            const matchDataEncoded = encodeURIComponent(JSON.stringify(m));
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
                        <button class="btn btn-secondary btn-share" data-match='${matchDataEncoded}'>📤 Partager ce prono</button>
                    </div>
                </div>
            `;
        });
    });
    matchesContainer.innerHTML = html;
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
    if (bookmakersFooter) {
        bookmakersFooter.innerHTML = '';
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
            bookmakersFooter.appendChild(a);
        });
    }
    if (bookmakersBonus) {
        bookmakersBonus.innerHTML = '';
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
            bookmakersBonus.appendChild(div);
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
    showIosGuideIfNeeded();

    // Initialisation selon la page
    if (matchesContainer) {
        setupEventListeners();
        await loadData();
    } else if (document.getElementById('history-container')) {
        displayHistory();
    } else if (document.getElementById('bonus-bookmaker-select')) {
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

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
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
                recordEvent('share');
                const target = shareLimits[currentCategory];
                if (newCount >= target) {
                    hideVipLocked();
                    filterAndDisplay();
                } else {
                    if (vipLockedOverlay && vipLockedOverlay.style.display === 'flex') {
                        showVipLocked(currentCategory);
                    } else {
                        showSharePopup(currentCategory, target - newCount);
                    }
                }
            }
        }
    });
    recordEvent('visit');
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
    const container = document.getElementById('history-container');
    if (!container) return;
    await loadData();
    if (!allData || !allData.matches) {
        container.innerHTML = '<div class="no-events">Aucun historique disponible.</div>';
        return;
    }
    const today = new Date(); today.setHours(0,0,0,0);
    let historyMatches = allData.matches.filter(m => new Date(m.event_date) < today);
    if (historyMatches.length === 0) {
        container.innerHTML = '<div class="no-events">Aucun match dans cette période.</div>';
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
            const homeLogo = getTeamLogoPath(m.home_team, true);
            const awayLogo = getTeamLogoPath(m.away_team, false);
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
    container.innerHTML = html;
}

function initBonusPage() {
    // À implémenter si nécessaire
}

function displayLatestVerified() {
    const container = document.getElementById('today-picks');
    if (!container) return;
    if (!allData || !allData.matches) {
        container.innerHTML = '<div class="loading">Chargement...</div>';
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
        container.innerHTML = '<div class="no-events">📭 Aucun pronostic validé récent. Revenez plus tard !</div>';
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
        const homeLogo = getTeamLogoPath(m.home_team, true);
        const awayLogo = getTeamLogoPath(m.away_team, false);
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
    container.innerHTML = html;
}

function startWinsSlider() {
    const track = document.getElementById('wins-track');
    if (!track || !allData || !allData.matches) return;
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
    track.innerHTML = html + html;
}

function startWinNotifications() {
    const popup = document.getElementById('win-popup');
    if (!popup) return;
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
        popup.innerHTML = `💰 <b>${name}</b> a gagné <b>${gain}€</b> aujourd'hui grâce au VIP !`;
        popup.classList.add('show');
        setTimeout(() => popup.classList.remove('show'), 4000);
        index = (index + 1) % notifications.length;
    }
    setInterval(showPopup, 3600000);
    showPopup();
}

function animateWins() {
    const el = document.getElementById('wins-count');
    if (!el || !allData || !allData.matches) return;
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
        el.textContent = count;
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
    const container = document.getElementById('testimonials-container');
    if (!container) return;
    try {
        const resp = await fetch('testimonials.json?t=' + Date.now());
        if (!resp.ok) throw new Error('Erreur');
        const testimonials = await resp.json();
        let html = '';
        testimonials.forEach(t => {
            html += `<div class="card"><p>"${t.text}"</p><p style="margin-top: 1rem; color: var(--or);">— ${t.name}</p></div>`;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error('Erreur chargement témoignages', e);
        container.innerHTML = `
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
    const allArticles = [...(window.generatedArticles || []), ...(data?.blog || [])];
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
    const modal = document.getElementById('article-modal');
    if (!modal) return;
    document.getElementById('article-modal-title').textContent = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
    document.getElementById('article-modal-image').src = article.image_url || 'assets/images/default-logo.png';
    let content = article.content;
    if (window.marked) content = window.marked.parse(content);
    else content = content.replace(/\n/g,'<br>');
    document.getElementById('article-modal-content').innerHTML = content;
    document.getElementById('article-modal-link').href = 'article.html?slug=' + article.slug;
    modal.style.display = 'flex';
};

window.closeArticleModal = function() {
    const modal = document.getElementById('article-modal');
    if (modal) modal.style.display = 'none';
};

async function displayBlogPost() {
    const container = document.getElementById('blog-post');
    if (!container) return;
    const urlParams = new URLSearchParams(window.location.search);
    const slug = urlParams.get('slug');
    if (!slug) { container.innerHTML = '<p>Article non trouvé.</p>'; return; }
    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const allArticles = [...(window.generatedArticles || []), ...(data?.blog || [])];
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
    const modal = document.getElementById('conseil-modal');
    if (!modal) return;
    document.getElementById('conseil-modal-title').textContent = conseil.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
    document.getElementById('conseil-modal-image').src = conseil.image_url || 'assets/images/default-logo.png';
    let content = conseil.content;
    if (window.marked) content = window.marked.parse(content);
    else content = content.replace(/\n/g,'<br>');
    document.getElementById('conseil-modal-content').innerHTML = content;
    modal.style.display = 'flex';
};

window.closeConseilModal = function() {
    const modal = document.getElementById('conseil-modal');
    if (modal) modal.style.display = 'none';
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
    const modal = document.getElementById('news-modal');
    if (!modal) return;
    document.getElementById('news-modal-title').textContent = news.title;
    document.getElementById('news-modal-image').src = news.image || 'assets/images/default-logo.png';
    let content = news.summary;
    if (window.marked) content = window.marked.parse(content);
    else content = content.replace(/\n/g,'<br>');
    content += '<p><em>Source: BBC</em></p>';
    document.getElementById('news-modal-content').innerHTML = content;
    document.getElementById('news-modal-link').href = news.link || '#';
    modal.style.display = 'flex';
};

window.closeNewsModal = function() {
    const modal = document.getElementById('news-modal');
    if (modal) modal.style.display = 'none';
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
            showToast('Code VIP activé avec succès !', 'success');
            window.location.reload();
        } catch (e) {
            alert('Code invalide ou expiré.');
        }
    });
    document.getElementById('vip-close-btn').addEventListener('click', () => {
        container.style.display = 'none';
        if (matchesContainer) matchesContainer.style.display = 'grid';
    });
}