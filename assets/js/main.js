// assets/js/main.js - Script principal complet avec toutes les fonctionnalités

import { supabase } from './supabase-client.js';

let allData = null;
let currentCategory = 'simple';
let currentSubcat = 'pronostics';
let currentDay = 'today';
let searchTerm = '';
let filteredMatchesWithoutSearch = [];

const matchesContainer = document.getElementById('matches-container');
const sharePopup = document.getElementById('share-popup');
const shareRemaining = document.getElementById('share-remaining');
const shareCurrent = document.getElementById('share-current');
const shareTarget = document.getElementById('share-target');
const shareMessage = document.getElementById('share-message');
const bookmakersFooter = document.getElementById('bookmakers-footer');
const bookmakersBonus = document.getElementById('bookmakers-bonus');
const vipSubtabs = document.getElementById('vip-subtabs');
const vipLockedOverlay = document.getElementById('vip-locked-overlay');

// Compteurs globaux
let totalUsers = 1000;
let totalShares = 10000;

const shareLimits = { pro: 2, vip: 5 };
const POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", "Eredivisie",
    "Primeira Liga", "Super Lig", "Russian Premier League", "MLS", "Brasileirão",
    "Liga Profesional", "Jupiler Pro League", "Super League", "Championship",
    "Liga Portugal", "Trendyol Super Lig"
];

// ==================== PARTAGES QUOTIDIENS ====================
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

// ==================== COMPTEURS GLOBAUX (SUPABASE) ====================
async function loadCounters() {
    try {
        const { data, error } = await supabase
            .from('counters')
            .select('total_users, total_shares')
            .eq('id', 1)
            .single();
        if (error) throw error;
        totalUsers = data.total_users;
        totalShares = data.total_shares;
    } catch (e) {
        console.warn('Utilisation des valeurs par défaut pour les compteurs', e);
        totalUsers = 1000;
        totalShares = 10000;
    }
    updateCountersDisplay();
}

function updateCountersDisplay() {
    const userCounter = document.getElementById('total-users-counter');
    const shareCounter = document.getElementById('total-shares-counter');
    if (userCounter) userCounter.textContent = totalUsers.toLocaleString();
    if (shareCounter) shareCounter.textContent = totalShares.toLocaleString();
}

// ==================== INSTALLATION PWA ====================
let deferredPrompt;
const installButton = document.getElementById('install-app');
const iosGuidePopup = document.getElementById('ios-guide-popup');

function getOS() {
    const ua = navigator.userAgent;
    if (/iPad|iPhone|iPod/.test(ua)) return 'iOS';
    if (/Android/.test(ua)) return 'Android';
    return 'Other';
}

function isPwaInstalled() {
    return window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
}

function showIosGuideIfNeeded() {
    if (getOS() === 'iOS' && !isPwaInstalled()) {
        const lastClosed = localStorage.getItem('iosGuideLastClosed');
        if (lastClosed) {
            const hours = (Date.now() - parseInt(lastClosed)) / (1000*60*60);
            if (hours < 24) return;
        }
        iosGuidePopup.style.display = 'flex';
    }
}

function closeIosGuide() {
    iosGuidePopup.style.display = 'none';
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

// ==================== CHARGEMENT DES DONNÉES ====================
async function loadData() {
    try {
        const resp = await fetch('data.json?t=' + Date.now());
        if (!resp.ok) throw new Error('Erreur chargement');
        allData = await resp.json();
        localStorage.setItem('cachedData', JSON.stringify(allData));
        renderBookmakers(allData.bookmakers);
    } catch (error) {
        console.error(error);
        const cached = localStorage.getItem('cachedData');
        if (cached) {
            allData = JSON.parse(cached);
            if (matchesContainer) matchesContainer.innerHTML = '<div class="warning">⚠️ Données en cache.</div>';
            renderBookmakers(allData.bookmakers);
        } else {
            if (matchesContainer) matchesContainer.innerHTML = '<div class="error">❌ Impossible de charger.</div>';
        }
    }
}

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

// ==================== GESTION DES ONGLETS ====================
function hideEmptyTabs() {
    if (!allData) return;
    const counts = { simple:0, pro:0, vip:0 };
    allData.matches.forEach(m => counts[m.category]++);
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const cat = btn.dataset.cat;
        if (cat === 'pro' || cat === 'vip') btn.style.display = 'inline-block';
        else btn.style.display = counts[cat] > 0 ? 'inline-block' : 'none';
    });
    const visible = Array.from(document.querySelectorAll('.tab-btn')).filter(b => b.style.display !== 'none');
    if (visible.length) {
        const active = document.querySelector('.tab-btn.active');
        if (!active || active.style.display === 'none') {
            visible[0].classList.add('active');
            currentCategory = visible[0].dataset.cat;
            if (currentCategory !== 'vip') currentSubcat = 'pronostics';
        }
    } else {
        const bar = document.querySelector('.category-tabs');
        if (bar) bar.style.display = 'none';
    }
    if (vipSubtabs) {
        const show = counts.vip > 0;
        const btns = vipSubtabs.querySelectorAll('.subtab-btn');
        if (btns.length) btns[0].style.display = show ? 'inline-block' : 'none';
        vipSubtabs.style.display = show ? 'flex' : 'none';
        const activeSub = vipSubtabs.querySelector('.subtab-btn.active');
        if (activeSub && activeSub.style.display === 'none') {
            const first = Array.from(btns).find(b => b.style.display !== 'none');
            if (first) {
                first.classList.add('active');
                currentSubcat = first.dataset.subcat;
            } else currentSubcat = 'pronostics';
        }
    }
}

function maybeHideTabBar() {
    const bar = document.querySelector('.category-tabs');
    if (bar) {
        const visible = Array.from(bar.querySelectorAll('.tab-btn')).filter(b => b.style.display !== 'none');
        bar.style.display = visible.length ? 'flex' : 'none';
    }
}

// ==================== FILTRAGE ET RECHERCHE ====================
function getLocalDateString(day) {
    const d = new Date();
    if (day === 'tomorrow') d.setDate(d.getDate() + 1);
    else if (day === 'yesterday') d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0,10);
}

function getLocalDateFromEvent(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d)) return null;
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function sortMatchesByLeague(matches) {
    return matches.sort((a,b) => {
        const ia = POPULAR_LEAGUES.findIndex(l => a.league?.includes(l) || a.league === l);
        const ib = POPULAR_LEAGUES.findIndex(l => b.league?.includes(l) || b.league === l);
        const ra = ia === -1 ? 999 : ia;
        const rb = ib === -1 ? 999 : ib;
        if (ra !== rb) return ra - rb;
        return new Date(a.event_date||0) - new Date(b.event_date||0);
    });
}

function filterAndDisplay() {
    if (!allData?.matches) {
        if (matchesContainer) matchesContainer.innerHTML = '<div class="no-events">Aucun match disponible.</div>';
        return;
    }
    const targetDate = getLocalDateString(currentDay);
    const targetCat = (currentCategory === 'vip' && currentSubcat === 'pronostics') ? 'vip' : currentCategory;
    const filtered = allData.matches.filter(m => {
        const date = getLocalDateFromEvent(m.event_date);
        return m.category === targetCat && date === targetDate;
    });
    filteredMatchesWithoutSearch = sortMatchesByLeague(filtered);
    applySearch();
}

function applySearch() {
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

// ==================== AFFICHAGE DES MATCHES ====================
function formatMatchTime(iso) {
    if (!iso) return 'Horaire inconnu';
    const d = new Date(iso);
    if (isNaN(d)) return 'Horaire inconnu';
    return d.toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' });
}

function translateStatus(status) {
    if (!status) return 'À venir';
    const s = status.toLowerCase();
    if (s.includes('finished') || s.includes('terminé')) return 'Terminé';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'En cours';
    if (s.includes('notstarted') || s.includes('à venir')) return 'À venir';
    if (s.includes('postponed')) return 'Reporté';
    if (s.includes('cancelled')) return 'Annulé';
    return status;
}

function getStatusClass(status) {
    const s = (status||'').toLowerCase();
    if (s.includes('finished') || s.includes('terminé')) return 'finished';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'live';
    return '';
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
    const sortedLeagues = Object.keys(grouped).sort((a,b) => {
        const ia = leagueOrder.findIndex(l => a.includes(l) || a === l);
        const ib = leagueOrder.findIndex(l => b.includes(l) || b === l);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    });
    sortedLeagues.forEach(league => {
        html += `<h2 class="league-header" style="color: var(--or); margin-top:2rem;">${league}</h2>`;
        grouped[league].forEach(m => {
            const pred = m.prediction || {};
            const dc = pred.double_chance || 'N/A';
            const over25 = pred.over_25 ? 'Oui' : 'Non';
            let conf = pred.confidence || 0;
            if (typeof conf === 'string') conf = parseFloat(conf);
            if (isNaN(conf)) conf = 0;
            if (conf > 100) conf /= 100;
            conf = Math.min(100, Math.round(conf*10)/10);
            const time = formatMatchTime(m.event_date);
            const statusFr = translateStatus(m.status);
            const statusClass = getStatusClass(m.status);
            const verifiedDouble = m.verified_double ? 'checked' : '';
            const verifiedOver = m.verified_over ? 'checked' : '';
            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const defaultLogo = 'assets/images/default-logo.png';
            const isWinner = m.verified_double && m.verified_over;
            const winnerClass = isWinner ? 'winner' : '';
            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';

            html += `
                <div class="match-card ${winnerClass}" data-id="${m.id}">
                    <div class="win-effect"></div>
                    <div class="match-info">
                        <div class="teams">
                            <div class="team">
                                <img src="${m.home_logo || defaultLogo}" alt="${m.home_team}" class="team-logo" onerror="this.src='${defaultLogo}'">
                                <span class="team-name">${m.home_team}</span>
                                <span class="team-score">${m.home_score ?? '-'}</span>
                            </div>
                            <div class="vs">VS</div>
                            <div class="team">
                                <img src="${m.away_logo || defaultLogo}" alt="${m.away_team}" class="team-logo" onerror="this.src='${defaultLogo}'">
                                <span class="team-name">${m.away_team}</span>
                                <span class="team-score">${m.away_score ?? '-'}</span>
                            </div>
                        </div>
                        <div class="match-meta">
                            <span class="league-badge">${m.league || 'Ligue'}</span>
                            <span class="status ${statusClass}">${statusFr}</span>
                            <span class="match-time"><i>🕒</i> ${time}</span>
                            ${m.venue ? `<span class="match-venue"><i>🏟️</i> ${m.venue}</span>` : ''}
                        </div>
                    </div>
                    <div class="analysis-panel ticket ${winnerClass}">
                        <h4>Pronostic ${xpronosBadge}</h4>
                        <p><strong>Double chance :</strong> ${dc} ${m.date === getLocalDateString('yesterday') ? `<input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled>` : ''}</p>
                        <p><strong>Over 2.5 :</strong> ${over25} ${m.date === getLocalDateString('yesterday') ? `<input type="checkbox" class="prediction-checkbox" ${verifiedOver} disabled>` : ''}</p>
                        <div class="confidence-bar"><div class="confidence-fill" data-value="${conf}"></div></div>
                        <p><strong>Fiabilité :</strong> <span class="confidence-text">${conf}%</span></p>
                        ${premiumBadge}
                    </div>
                </div>
            `;
        });
    });
    matchesContainer.innerHTML = html;
    document.querySelectorAll('.confidence-fill').forEach(bar => {
        let v = bar.getAttribute('data-value');
        setTimeout(() => bar.style.width = v + '%', 300);
    });
    document.querySelectorAll('.match-card.winner').forEach(card => {
        for (let i=0; i<20; i++) {
            let spark = document.createElement('div');
            spark.className = 'spark';
            let dx = (Math.random()-0.5)*200;
            let dy = (Math.random()-0.5)*200;
            spark.style.setProperty('--dx', dx+'px');
            spark.style.setProperty('--dy', dy+'px');
            spark.style.left = Math.random()*100+'%';
            spark.style.top = Math.random()*100+'%';
            card.appendChild(spark);
        }
        setTimeout(() => card.querySelectorAll('.spark').forEach(s => s.remove()), 1000);
    });
}

// ==================== BOOKMAKERS ====================
function renderBookmakers(bookmakers) {
    if (!bookmakers || bookmakers.length === 0) {
        console.warn("Fallback bookmakers");
        bookmakers = [
            { name: "1xBet", logo: "assets/images/1xbet.png", url: "#" },
            { name: "1win", logo: "assets/images/1win.png", url: "#" },
            { name: "Betwinner", logo: "assets/images/betwinner.png", url: "#" },
            { name: "Melbet", logo: "assets/images/melbet.png", url: "#" },
            { name: "Linebet", logo: "assets/images/linebet.png", url: "#" },
            { name: "888starz", logo: "assets/images/888starz.png", url: "#" }
        ];
    }
    if (bookmakersFooter) {
        bookmakersFooter.innerHTML = '';
        bookmakers.forEach(b => {
            const a = document.createElement('a');
            a.href = b.url; a.target = '_blank'; a.rel = 'noopener';
            a.innerHTML = `<img src="${b.logo}" alt="${b.name}" style="max-height:40px;">`;
            bookmakersFooter.appendChild(a);
        });
    }
    if (bookmakersBonus) {
        bookmakersBonus.innerHTML = '';
        bookmakers.forEach(b => {
            const div = document.createElement('div');
            div.className = 'bookmaker-card';
            div.innerHTML = `<img src="${b.logo}" alt="${b.name}"><h3>${b.name}</h3><p>Bonus de bienvenue jusqu'à 130€</p><a href="${b.url}" class="btn btn-primary" target="_blank">S'inscrire avec XPVIP</a>`;
            bookmakersBonus.appendChild(div);
        });
    }
}

// ==================== PARTAGE ====================
function showSharePopup(category, remaining) {
    if (!sharePopup) return;
    const count = getDailyShareCount();
    shareRemaining.textContent = remaining;
    shareCurrent.textContent = count;
    shareTarget.textContent = shareLimits[category];
    shareMessage.innerHTML = `Pour accéder aux pronostics ${category==='pro'?'Pro':'VIP'}, partagez ce lien à <span id="share-remaining">${remaining}</span> amis.`;
    sharePopup.classList.add('active');
}

function showVipLocked(category) {
    if (vipLockedOverlay) {
        const target = shareLimits[category];
        const count = getDailyShareCount();
        const remaining = target - count;
        vipLockedOverlay.querySelector('h3').textContent = `🔒 ${category==='pro'?'Pronostics Pro':'Pronostics VIP'} verrouillés`;
        vipLockedOverlay.querySelector('p').innerHTML = `Partagez ce lien à <strong>${remaining}</strong> ami(s) pour débloquer.`;
        document.getElementById('share-count-locked').textContent = count;
        document.getElementById('share-target-locked').textContent = target;
        vipLockedOverlay.style.display = 'flex';
        if (matchesContainer) matchesContainer.style.display = 'none';
    } else {
        const target = shareLimits[category];
        const count = getDailyShareCount();
        showSharePopup(category, target - count);
    }
}

function hideVipLocked() {
    if (vipLockedOverlay) {
        vipLockedOverlay.style.display = 'none';
        if (matchesContainer) matchesContainer.style.display = 'grid';
    }
}

async function share(platform) {
    const siteUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    let message = `🔥 *Mr XPRONOS* - Des pronostics fiables qui font la différence !\n\n📊 Hier encore, nos coupons ont rapporté gros. Aujourd'hui, ne rate pas les analyses exclusives.\n\n👉 Rejoins la communauté et débloque les pronostics Pro/VIP en partageant ce lien :\n\n${siteUrl}\n\n⚽ Arrête d'acheter des coupons qui perdent chaque jour. Un vrai pronostiqueur ne vend pas ses analyses si elles sont gagnantes. Rejoins-nous gratuitement !`;
    let url = platform === 'whatsapp'
        ? `https://wa.me/?text=${encodeURIComponent(message)}`
        : `https://t.me/share/url?url=${encodeURIComponent(siteUrl)}&text=${encodeURIComponent(message)}`;
    window.open(url, '_blank');

    const newCount = incrementShareCount();
    updateCountersDisplay();

    // Incrémenter compteur global Supabase
    try {
        await supabase.rpc('increment_shares');
        const { data } = await supabase.from('counters').select('total_shares').eq('id',1).single();
        if (data) totalShares = data.total_shares;
        updateCountersDisplay();
    } catch (e) { console.error(e); }

    const target = shareLimits[currentCategory];
    if (newCount >= target) {
        hideVipLocked();
        filterAndDisplay();
    } else {
        if (vipLockedOverlay && vipLockedOverlay.style.display === 'flex')
            showVipLocked(currentCategory);
        else
            showSharePopup(currentCategory, target - newCount);
    }
}

function updateShareCounter() {
    const c = document.getElementById('share-counter');
    if (c) c.textContent = `🔥 ${getDailyShareCount()} partages aujourd'hui`;
}

// ==================== GESTION DES ONGLETS VIP ====================
function handleCategoryChange() {
    if (currentCategory === 'simple') {
        hideVipLocked();
        filterAndDisplay();
    } else {
        const target = shareLimits[currentCategory];
        const count = getDailyShareCount();
        if (count >= target) {
            hideVipLocked();
            filterAndDisplay();
        } else {
            showVipLocked(currentCategory);
        }
    }
}

// ==================== HISTORIQUE ====================
async function displayHistory() {
    const container = document.getElementById('history-container');
    if (!container) return;
    await loadData();
    if (!allData?.matches) {
        container.innerHTML = '<div class="no-events">Aucun historique disponible.</div>';
        return;
    }
    const today = new Date(); today.setHours(0,0,0,0);
    let history = allData.matches.filter(m => new Date(m.event_date) < today);
    if (history.length === 0) {
        container.innerHTML = '<div class="no-events">Aucun match dans cette période.</div>';
        return;
    }
    const catOrder = { vip:0, pro:1, simple:2 };
    history.sort((a,b) => {
        const oa = catOrder[a.category] ?? 3;
        const ob = catOrder[b.category] ?? 3;
        if (oa !== ob) return oa - ob;
        return new Date(b.event_date) - new Date(a.event_date);
    });
    const grouped = {};
    history.forEach(m => {
        const d = getLocalDateFromEvent(m.event_date);
        if (!grouped[d]) grouped[d] = [];
        grouped[d].push(m);
    });
    let html = '';
    const sortedDays = Object.keys(grouped).sort((a,b) => new Date(b) - new Date(a));
    sortedDays.forEach(day => {
        const dayDate = new Date(day+'T12:00:00');
        const formatted = dayDate.toLocaleDateString('fr-FR', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
        html += `<h2 class="day-header">${formatted}</h2>`;
        grouped[day].forEach(m => {
            const pred = m.prediction || {};
            const dc = pred.double_chance || 'N/A';
            const over25 = pred.over_25 ? 'Oui' : 'Non';
            let conf = pred.confidence || 0;
            if (typeof conf === 'string') conf = parseFloat(conf);
            if (isNaN(conf)) conf = 0;
            if (conf > 100) conf /= 100;
            conf = Math.min(100, Math.round(conf*10)/10);
            const time = formatMatchTime(m.event_date);
            const statusFr = translateStatus(m.status);
            const statusClass = getStatusClass(m.status);
            const verifiedDouble = m.verified_double ? 'checked' : '';
            const verifiedOver = m.verified_over ? 'checked' : '';
            const defaultLogo = 'assets/images/default-logo.png';
            const winnerClass = (m.verified_double && m.verified_over) ? 'winner' : '';
            const xBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';
            const premBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const catBadge = m.category ? `<span class="badge-category badge-${m.category}">${m.category.toUpperCase()}</span>` : '';

            html += `
                <div class="match-card ${winnerClass}">
                    <div class="match-info">
                        <div class="teams">
                            <div class="team"><img src="${m.home_logo || defaultLogo}" class="team-logo" onerror="this.src='${defaultLogo}'"><span class="team-name">${m.home_team}</span><span class="team-score">${m.home_score ?? '-'}</span></div>
                            <div class="vs">VS</div>
                            <div class="team"><img src="${m.away_logo || defaultLogo}" class="team-logo" onerror="this.src='${defaultLogo}'"><span class="team-name">${m.away_team}</span><span class="team-score">${m.away_score ?? '-'}</span></div>
                        </div>
                        <div class="match-meta"><span class="league-badge">${m.league||'Ligue'}</span><span class="status ${statusClass}">${statusFr}</span><span class="match-time"><i>🕒</i> ${time}</span></div>
                    </div>
                    <div class="analysis-panel">
                        <h4>Pronostic ${xBadge} ${catBadge}</h4>
                        <p><strong>Double chance :</strong> ${dc} <input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled></p>
                        <p><strong>Over 2.5 :</strong> ${over25} <input type="checkbox" class="prediction-checkbox" ${verifiedOver} disabled></p>
                        <p><strong>Fiabilité :</strong> ${conf}%</p>
                        ${premBadge}
                    </div>
                </div>
            `;
        });
    });
    container.innerHTML = html;
}

// ==================== BLOG, CONSEILS, INFOS, BONUS ====================
async function loadGeneratedContent() {
    try {
        const a = await fetch('articles.json?t='+Date.now());
        if (a.ok) window.generatedArticles = await a.json();
        const c = await fetch('conseils.json?t='+Date.now());
        if (c.ok) window.generatedConseils = await c.json();
    } catch (e) { console.error('Erreur chargement contenu généré:', e); }
}

function renderHorizontalList(items, containerId, type) {
    const cont = document.getElementById(containerId);
    if (!cont) return;
    if (!items || items.length === 0) { cont.style.display = 'none'; return; }
    cont.style.display = 'flex';
    let html = '';
    items.slice(0,8).forEach(item => {
        let img = item.image || item.image_url || 'assets/images/default-logo.png';
        let title = item.title || item.match || 'Sans titre';
        let slug = item.slug || null;
        let link = '#';
        if (type === 'blog' && slug) link = `article.html?slug=${slug}`;
        else if (type === 'conseils') link = `conseils.html#${item.id}`;
        else if (type === 'infos') link = `infos.html#${item.id}`;
        else if (type === 'bonus') link = `bonus.html#${item.id}`;
        html += `<div class="horizontal-item" onclick="window.location.href='${link}'"><img src="${img}" alt="${title}"><div class="item-title">${title}</div></div>`;
    });
    cont.innerHTML = html;
}

async function displayBlogList() {
    const cont = document.getElementById('blog-list');
    if (!cont) return;
    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const all = [...(window.generatedArticles||[]), ...(data?.blog||[])];
    renderHorizontalList(all, 'blog-horizontal-list', 'blog');
    if (all.length === 0) return;
    all.forEach(article => {
        let title = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
        let excerpt = article.excerpt || article.content.substring(0,200)+'...';
        let clean = excerpt.replace(/#+\s*/g,'').replace(/\*\*/g,'').replace(/\*/g,'').replace(/\[|\]/g,'').substring(0,150)+'...';
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h3><a href="article.html?slug=${article.slug}" style="color:var(--or);">${title}</a></h3>
            <div class="meta">${article.date} par ${article.author} ${article.match ? '• '+article.match : ''}</div>
            ${article.image_url ? `<img src="${article.image_url}" alt="${title}" style="max-width:100%; border-radius:8px; margin:10px 0;">` : ''}
            <p>${clean}</p>
            <a href="article.html?slug=${article.slug}" class="btn btn-secondary">Lire</a>
        `;
        cont.appendChild(card);
    });
}

async function displayBlogPost() {
    const cont = document.getElementById('blog-post');
    if (!cont) return;
    const params = new URLSearchParams(window.location.search);
    const slug = params.get('slug');
    if (!slug) { cont.innerHTML = '<p>Article non trouvé.</p>'; return; }
    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const all = [...(window.generatedArticles||[]), ...(data?.blog||[])];
    const article = all.find(a => a.slug === slug);
    if (!article) { cont.innerHTML = '<p>Article non trouvé.</p>'; return; }
    let title = article.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
    document.title = title + ' - Mr XPRONOS';
    let htmlContent = window.marked ? window.marked.parse(article.content) : article.content.replace(/\n/g,'<br>');
    cont.innerHTML = `
        <h1>${title}</h1>
        <div class="meta">${article.date} par ${article.author}</div>
        ${article.image_url ? `<img src="${article.image_url}" alt="${title}" style="max-width:100%; border-radius:8px; margin:20px 0;">` : ''}
        <div style="margin-top:2rem;">${htmlContent}</div>
        <a href="blog.html" class="btn btn-secondary" style="margin-top:2rem;">← Retour au blog</a>
    `;
}

async function displayConseils() {
    const cont = document.getElementById('conseils-list');
    if (!cont) return;
    if (!window.generatedConseils) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const all = [...(window.generatedConseils||[]), ...(data?.conseils||[])];
    renderHorizontalList(all, 'conseils-horizontal-list', 'conseils');
    if (all.length === 0) return;
    all.forEach(c => {
        let title = c.title.replace(/#+\s*/g,'').replace(/\*\*/g,'');
        let html = window.marked ? window.marked.parse(c.content) : c.content.replace(/\n/g,'<br>');
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<h3>${title}</h3>${c.image_url ? `<img src="${c.image_url}" alt="${title}" style="max-width:100%; border-radius:8px; margin:10px 0;">` : ''}<div>${html}</div>`;
        cont.appendChild(card);
    });
}

async function displayInfos() {
    const cont = document.getElementById('infos-list');
    if (!cont) return;
    const data = await loadDataGeneric();
    if (!data?.infos) return;
    renderHorizontalList(data.infos, 'infos-horizontal-list', 'infos');
    data.infos.forEach(i => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<h3>${i.title}</h3><p>${i.content}</p>`;
        cont.appendChild(card);
    });
}

async function displayBonus() {
    const cont = document.getElementById('bonus-grid');
    if (!cont) return;
    const data = await loadDataGeneric();
    const bonus = data?.bonus || [];
    const active = bonus.filter(b => b.active && new Date(b.end) >= new Date());
    renderHorizontalList(active, 'bonus-horizontal-list', 'bonus');
    if (active.length === 0) {
        cont.innerHTML = '<div class="no-events">Aucun bonus actif pour le moment.</div>';
        return;
    }
    let html = '';
    active.forEach(b => {
        html += `
            <div class="bonus-card">
                <img src="${b.image}" alt="${b.title}" class="bonus-image">
                <h3>${b.title}</h3>
                <p>${b.description}</p>
                <div class="bonus-footer">
                    <span>Valable du ${b.start.split('-').reverse().join('/')} au ${b.end.split('-').reverse().join('/')}</span>
                    ${b.link ? `<a href="${b.link}" target="_blank" class="btn btn-primary">Profiter</a>` : ''}
                </div>
            </div>
        `;
    });
    cont.innerHTML = html;
}

async function displayFootNews() {
    const cont = document.getElementById('foot-news-container');
    if (!cont) return;
    try {
        const resp = await fetch('footnews.json?t='+Date.now());
        if (!resp.ok) throw new Error();
        const news = await resp.json();
        if (news.length === 0) {
            cont.innerHTML = '<div class="no-events">Aucune actualité pour le moment.</div>';
            return;
        }
        let html = '';
        news.forEach(item => {
            html += `
                <div class="news-card card">
                    ${item.image ? `<img src="${item.image}" alt="${item.title}" style="width:100%; border-radius:8px; margin-bottom:10px;">` : ''}
                    <h3><a href="${item.link}" target="_blank" rel="noopener" style="color:var(--or);">${item.title}</a></h3>
                    <p class="meta">${new Date(item.published).toLocaleDateString('fr-FR')}</p>
                    <p>${item.summary}</p>
                    <a href="${item.link}" target="_blank" class="btn btn-secondary">Lire la suite</a>
                </div>
            `;
        });
        cont.innerHTML = html;
    } catch (e) {
        console.error(e);
        cont.innerHTML = '<div class="error">Impossible de charger les actualités.</div>';
    }
}

// ==================== TAUX DE RÉUSSITE ====================
function updateSuccessRate() {
    const cont = document.getElementById('success-rate-container');
    if (!cont) return;
    const matches = allData?.matches || [];
    const finished = matches.filter(m => m.status === 'finished' && m.verified_double !== undefined);
    if (finished.length === 0) { cont.style.display = 'none'; return; }
    const successful = finished.filter(m => m.verified_double && m.verified_over).length;
    const rate = ((successful / finished.length) * 100).toFixed(1);
    const stats = allData?.stats || {};
    const roi = stats.roi || 0;
    cont.innerHTML = `
        <div class="success-rate-item"><div class="success-rate-value">${rate}%</div><div class="success-rate-label">Réussite</div></div>
        <div class="success-rate-item"><div class="success-rate-value">${roi>0?'+':''}${roi}%</div><div class="success-rate-label">ROI</div></div>
    `;
    cont.style.display = 'flex';
}

function initScrollProgress() {
    const bar = document.createElement('div');
    bar.className = 'scroll-progress';
    document.body.appendChild(bar);
    window.addEventListener('scroll', () => {
        const win = document.body.scrollTop || document.documentElement.scrollTop;
        const h = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        bar.style.width = (win / h) * 100 + '%';
    });
}

// ==================== INITIALISATION ====================
document.addEventListener('DOMContentLoaded', () => {
    showIosGuideIfNeeded();
    loadCounters();

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', e => {
            searchTerm = e.target.value;
            applySearch();
        });
    }

    if (matchesContainer) {
        initPronostics();
    } else if (document.getElementById('history-container')) {
        displayHistory();
    } else if (document.getElementById('bonus-grid')) {
        displayBonus();
    } else {
        loadDataGeneric().then(data => {
            if (data) {
                renderBookmakers(data.bookmakers);
                updateShareCounter();
            }
        });
    }

    displayBlogList();
    displayBlogPost();
    displayConseils();
    displayInfos();
    displayFootNews();
    initScrollProgress();
});

async function initPronostics() {
    await loadData();
    if (allData) {
        hideEmptyTabs();
        maybeHideTabBar();
        setupEventListeners();
        updateSuccessRate();
        filterAndDisplay();
    } else {
        if (matchesContainer) matchesContainer.innerHTML = '<div class="error">❌ Erreur de chargement des données.</div>';
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
    document.getElementById('share-wa')?.addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg')?.addEventListener('click', () => share('telegram'));
    document.getElementById('close-popup')?.addEventListener('click', () => sharePopup.classList.remove('active'));
    document.getElementById('share-wa-locked')?.addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg-locked')?.addEventListener('click', () => share('telegram'));
}

// ==================== ÉVÉNEMENTS (statistiques) ====================
function recordEvent(type, page) {
    let events = JSON.parse(localStorage.getItem('userEvents')) || [];
    events.push({ type, page, timestamp: new Date().toISOString() });
    localStorage.setItem('userEvents', JSON.stringify(events));
    // Envoi à Supabase
    supabase.from('events').insert({ type, page, user_id: localStorage.getItem('userId') || 'anon' }).then();
}
if (!localStorage.getItem('userId')) {
    localStorage.setItem('userId', 'user_' + Math.random().toString(36).substr(2,9));
}
recordEvent('visit', window.location.pathname);