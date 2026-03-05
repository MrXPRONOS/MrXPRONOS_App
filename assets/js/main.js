/**
 * main.js - Mr XPRONOS – Version complète et robuste offline avancé
 */

// =======================================================
// IMPORT CONFIGURATION SUPABASE (optionnel)
// =======================================================
let supabase = null;
let supabaseAvailable = false;

try {
    const { supabaseUrl, supabaseAnonKey } = await import('./config.js');
    const { createClient } = await import('https://esm.sh/@supabase/supabase-js@2');
    supabase = createClient(supabaseUrl, supabaseAnonKey);
    supabaseAvailable = true;
    console.log('✅ Supabase connecté');
} catch (error) {
    console.warn('⚠️ Supabase non configuré, utilisation des compteurs locaux');
}

// =======================================================
// VARIABLES GLOBALES
// =======================================================
let allData = null;
let currentCategory = 'simple';
let currentSubcat = 'pronostics';
let currentDay = 'today';

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

const shareLimits = { pro: 2, vip: 5 };

const POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
];

// =======================================================
// FONCTIONS SUPABASE (AVEC FALLBACK)
// =======================================================
async function getCounterValue(counterName) {
    if (supabaseAvailable) {
        const { data, error } = await supabase
            .from('counters')
            .select('value')
            .eq('name', counterName)
            .single();
        if (!error && data) return data.value;
    }
    const local = localStorage.getItem('counter_' + counterName);
    return local ? parseInt(local) : (counterName === 'total_users' ? 1000 : 10000);
}

async function incrementCounter(counterName) {
    if (supabaseAvailable) {
        const { data, error } = await supabase.rpc('increment_counter', { counter_name: counterName });
        if (!error) return data;
        const current = await getCounterValue(counterName);
        if (current === null) return;
        const newValue = current + 1;
        await supabase
            .from('counters')
            .update({ value: newValue, updated_at: new Date().toISOString() })
            .eq('name', counterName);
        return newValue;
    } else {
        const current = parseInt(localStorage.getItem('counter_' + counterName) || '0');
        const newValue = current + 1;
        localStorage.setItem('counter_' + counterName, newValue);
        return newValue;
    }
}

async function updateDisplayedCounters() {
    const totalUsers = await getCounterValue('total_users');
    const totalShares = await getCounterValue('total_shares');
    const usersEl = document.getElementById('total-users-count');
    const sharesEl = document.getElementById('total-shares-count');
    if (usersEl) usersEl.textContent = totalUsers.toLocaleString();
    if (sharesEl) sharesEl.textContent = totalShares.toLocaleString();
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

// =======================================================
// GESTION DE L'INSTALLATION PWA
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
    return window.matchMedia('(display-mode: standalone)').matches || 
           window.navigator.standalone === true;
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
// INITIALISATION
// =======================================================
document.addEventListener('DOMContentLoaded', () => {
    showIosGuideIfNeeded();
    updateDisplayedCounters();

    if (matchesContainer) {
        initPronostics();
    } else if (document.getElementById('history-container')) {
        displayHistory();
    } else if (document.getElementById('bonus-bookmaker-select')) {
        initBonusPage();
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
    displayBonusList();
    displayFootNews();
    initScrollProgress();

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            searchTerm = e.target.value;
            applySearchFilter();
        });
    }
});

// =======================================================
// FONCTIONS PRONOSTICS (AVEC LOAD DATA ROBUSTE)
// =======================================================
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

async function loadData() {
    console.log('🔄 Chargement pronostics (mode avancé offline)...');
    
    const container = document.getElementById('matches-container');
    if (container) {
        container.innerHTML = `
            <div style="text-align:center; padding:80px 20px; color:#aaa;">
                <div style="font-size:60px; margin-bottom:20px;">⏳</div>
                <div>Chargement des matchs...</div>
            </div>`;
    }

    let dataLoaded = false;

    try {
        // Tentative réseau avec timeout (8 secondes)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);

        const resp = await fetch('data.json?t=' + Date.now(), { 
            signal: controller.signal,
            cache: 'no-cache'
        });
        
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

    // FALLBACK CACHE
    if (!dataLoaded) {
        const cached = localStorage.getItem('cachedData');
        if (cached) {
            try {
                allData = JSON.parse(cached);
                console.log('📦 Pronos chargés depuis le cache local (' + allData.matches.length + ' matchs)');
                dataLoaded = true;
            } catch (e) {
                console.error('❌ Cache corrompu', e);
            }
        }
    }

    if (dataLoaded && allData) {
        // Affichage du mode offline si nécessaire
        if (container && !navigator.onLine) {
            container.insertAdjacentHTML('afterbegin', `
                <div style="background:#ffcc00; color:#000; text-align:center; padding:8px; font-weight:700; font-size:0.95rem;">
                    📴 MODE HORS LIGNE — Pronostics du cache (${new Date().toLocaleDateString('fr-FR')})
                </div>
            `);
        }

        hideEmptyTabs();
        maybeHideTabBar();
        setupEventListeners();
        updateSuccessRate();
        filterAndDisplay();   // ← AFFICHE LES MATCHS !
    } 
    else if (container) {
        container.innerHTML = `
            <div class="error" style="text-align:center; padding:60px;">
                ❌ Aucune donnée disponible.<br>
                <small>Connectez-vous une première fois pour charger le cache.</small>
            </div>`;
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

function hideEmptyTabs() {
    const counts = { simple: 0, pro: 0, vip: 0 };
    allData.matches.forEach(m => counts[m.category]++);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        const cat = btn.dataset.cat;
        if (cat === 'pro' || cat === 'vip') {
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
        const showPronostics = counts.vip > 0;
        const subtabBtns = vipSubtabs.querySelectorAll('.subtab-btn');
        if (subtabBtns.length >= 1) {
            subtabBtns[0].style.display = showPronostics ? 'inline-block' : 'none';
        }
        vipSubtabs.style.display = showPronostics ? 'flex' : 'none';

        const activeSub = vipSubtabs.querySelector('.subtab-btn.active');
        if (activeSub && activeSub.style.display === 'none') {
            const firstVisible = Array.from(subtabBtns).find(btn => btn.style.display !== 'none');
            if (firstVisible) {
                firstVisible.classList.add('active');
                currentSubcat = firstVisible.dataset.subcat;
            } else {
                currentSubcat = 'pronostics';
            }
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

    const shareWaLocked = document.getElementById('share-wa-locked');
    const shareTgLocked = document.getElementById('share-tg-locked');
    if (shareWaLocked) shareWaLocked.addEventListener('click', () => share('whatsapp'));
    if (shareTgLocked) shareTgLocked.addEventListener('click', () => share('telegram'));
}

function handleCategoryChange() {
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
    if (vipLockedOverlay) {
        const target = shareLimits[category];
        const shareCount = getDailyShareCount();
        const remaining = target - shareCount;
        vipLockedOverlay.querySelector('h3').textContent = `🔒 ${category === 'pro' ? 'Pronostics Pro' : 'Pronostics VIP'} verrouillés`;
        vipLockedOverlay.querySelector('p').innerHTML = `Partagez ce lien à <strong>${remaining}</strong> ami(s) pour débloquer.`;
        const shareCountLocked = document.getElementById('share-count-locked');
        const shareTargetLocked = document.getElementById('share-target-locked');
        if (shareCountLocked) shareCountLocked.textContent = shareCount;
        if (shareTargetLocked) shareTargetLocked.textContent = target;
        vipLockedOverlay.style.display = 'flex';
        if (matchesContainer) matchesContainer.style.display = 'none';
    } else {
        const target = shareLimits[category];
        const shareCount = getDailyShareCount();
        showSharePopup(category, target - shareCount);
    }
}

function hideVipLocked() {
    if (vipLockedOverlay) {
        vipLockedOverlay.style.display = 'none';
        if (matchesContainer) matchesContainer.style.display = 'grid';
    }
}

function showSharePopup(category, remaining) {
    if (!sharePopup) return;
    const shareCount = getDailyShareCount();
    if (shareRemaining) shareRemaining.textContent = remaining;
    if (shareCurrent) shareCurrent.textContent = shareCount;
    if (shareTarget) shareTarget.textContent = shareLimits[category];
    if (shareMessage) shareMessage.innerHTML = `Pour accéder aux pronostics ${category === 'pro' ? 'Pro' : 'VIP'}, partagez ce lien à <span id="share-remaining">${remaining}</span> amis.`;
    sharePopup.classList.add('active');
}

function share(platform) {
    const siteUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    let message = '';
    let url = '';

    if (platform === 'whatsapp') {
        message = `🔥 *Mr XPRONOS* - Des pronostics fiables qui font la différence !\n\n📊 Hier encore, nos coupons ont rapporté gros. Aujourd'hui, ne rate pas les analyses exclusives.\n\n👉 Rejoins la communauté et débloque les pronostics Pro/VIP en partageant ce lien :\n\n${siteUrl}\n\n⚽ Arrête d'acheter des coupons qui perdent chaque jour. Un vrai pronostiqueur ne vend pas ses analyses si elles sont gagnantes. Rejoins-nous gratuitement !`;
        url = `https://wa.me/?text=${encodeURIComponent(message)}`;
    } else {
        message = `🔥 *Mr XPRONOS* - Des pronostics fiables qui font la différence !\n\n📊 Hier encore, nos coupons ont rapporté gros. Aujourd'hui, ne rate pas les analyses exclusives.\n\n👉 Rejoins la communauté et débloque les pronostics Pro/VIP en partageant ce lien :\n\n${siteUrl}\n\n⚽ Arrête d'acheter des coupons qui perdent chaque jour. Un vrai pronostiqueur ne vend pas ses analyses si elles sont gagnantes. Rejoins-nous gratuitement !`;
        url = `https://t.me/share/url?url=${encodeURIComponent(siteUrl)}&text=${encodeURIComponent(message)}`;
    }

    window.open(url, '_blank');

    const newCount = incrementShareCount();
    updateShareCounter();
    incrementCounter('total_shares');
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

function updateShareCounter() {
    const counter = document.getElementById('share-counter');
    if (counter) {
        const count = getDailyShareCount();
        counter.textContent = `🔥 ${count} partages aujourd'hui`;
    }
}

function getLocalDateString(day) {
    const now = new Date();
    const target = new Date(now);
    if (day === 'tomorrow') {
        target.setDate(now.getDate() + 1);
    } else if (day === 'yesterday') {
        target.setDate(now.getDate() - 1);
    }
    const year = target.getFullYear();
    const month = String(target.getMonth() + 1).padStart(2, '0');
    const dayOfMonth = String(target.getDate()).padStart(2, '0');
    return `${year}-${month}-${dayOfMonth}`;
}

function getLocalDateFromEvent(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    if (isNaN(date)) return null;
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

let filteredMatchesWithoutSearch = [];
let searchTerm = '';

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
            const over25 = pred.over_25 ? 'Oui' : 'Non';
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
            const verifiedOver = (eventDate === yesterdayStr && m.verified_over) ? 'checked' : '';

            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const defaultLogo = 'assets/images/default-logo.png';

            const isWinner = m.verified_double && m.verified_over;
            const winnerClass = isWinner ? 'winner' : '';

            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';

            html += `
                <div class="match-card ${winnerClass}" data-match-id="${m.id}">
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
                            <span class="match-time"><i>🕒</i> ${matchTime}</span>
                            ${m.venue ? `<span class="match-venue"><i>🏟️</i> ${m.venue}</span>` : ''}
                        </div>
                    </div>
                    <div class="analysis-panel ticket ${winnerClass}">
                        <h4>Pronostic ${xpronosBadge}</h4>
                        <p>
                            <strong>Double chance :</strong> ${doubleChance}
                            ${eventDate === yesterdayStr ? `<input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled>` : ''}
                        </p>
                        <p>
                            <strong>Over 2.5 :</strong> ${over25}
                            ${eventDate === yesterdayStr ? `<input type="checkbox" class="prediction-checkbox" ${verifiedOver} disabled>` : ''}
                        </p>
                        <div class="confidence-bar">
                            <div class="confidence-fill" data-value="${confidence}"></div>
                        </div>
                        <p><strong>Fiabilité :</strong> <span class="confidence-text">${confidence}%</span></p>
                        ${premiumBadge}
                    </div>
                </div>
            `;
        });
    });
    matchesContainer.innerHTML = html;

    document.querySelectorAll('.confidence-fill').forEach(bar => {
        let value = bar.getAttribute('data-value');
        setTimeout(() => {
            bar.style.width = value + '%';
        }, 300);
    });

    document.querySelectorAll('.match-card.winner').forEach(card => {
        for (let i = 0; i < 20; i++) {
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
        setTimeout(() => {
            card.querySelectorAll('.spark').forEach(s => s.remove());
        }, 1000);
    });
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
    if (!status) return '';
    const s = status.toLowerCase();
    if (s.includes('finished') || s.includes('terminé')) return 'finished';
    if (s.includes('inprogress') || s.includes('live') || s.includes('en cours')) return 'live';
    return '';
}

// =======================================================
// RENDER BOOKMAKERS (VERSION CORRIGÉE AVEC FALLBACK ROBUSTE)
// =======================================================
function renderBookmakers(bookmakers) {
    console.log('📢 renderBookmakers appelée avec:', bookmakers);
    if (!bookmakers || bookmakers.length === 0) {
        console.warn("⚠️ Aucun bookmaker dans data.json → utilisation du fallback");
        bookmakers = [
            { name: "1xBet",     logo: "assets/images/1xbet.png",     url: "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599" },
            { name: "1win",      logo: "assets/images/1win.png",      url: "https://1wrbgb.com/?open=register&p=qqcw" },
            { name: "Betwinner", logo: "assets/images/betwinner.png", url: "https://bwredir.com/299Y" },
            { name: "Melbet",    logo: "assets/images/melbet.png",    url: "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041" },
            { name: "Linebet",   logo: "assets/images/linebet.png",   url: "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611" },
            { name: "BetClic",   logo: "assets/images/betclic.png",   url: "https://betpari-click.com/2vY0?extid=USD" }
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
            img.onerror = function() {
                console.log('❌ Image non chargée pour', b.name);
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
            img.onerror = function() {
                console.log('❌ Image non chargée pour', b.name);
                this.style.display = 'none';
                const span = document.createElement('span');
                span.textContent = b.name;
                span.style.display = 'block';
                span.style.marginBottom = '0.5rem';
                span.style.color = 'var(--or)';
                div.insertBefore(span, div.firstChild);
            };
            div.appendChild(img);
            div.innerHTML += `
                <h3>${b.name}</h3>
                <p>Bonus de bienvenue jusqu'à 130€</p>
                <a href="${b.url}" class="btn btn-primary" target="_blank">S'inscrire avec XPVIP</a>
            `;
            bookmakersBonus.appendChild(div);
        });
    }
}

// =======================================================
// FONCTIONS POUR LES STATISTIQUES (admin)
// =======================================================
function recordEvent(type) {
    let events = JSON.parse(localStorage.getItem('userEvents')) || [];
    events.push({
        type: type,
        timestamp: new Date().toISOString(),
        userId: localStorage.getItem('userId') || 'unknown'
    });
    localStorage.setItem('userEvents', JSON.stringify(events));
}
recordEvent('visit');

// =======================================================
// FONCTIONS POUR LE CONTENU GÉNÉRÉ
// =======================================================
async function loadGeneratedContent() {
    try {
        const articlesResp = await fetch('articles.json?t=' + Date.now());
        if (articlesResp.ok) window.generatedArticles = await articlesResp.json();
        const conseilsResp = await fetch('conseils.json?t=' + Date.now());
        if (conseilsResp.ok) window.generatedConseils = await conseilsResp.json();
    } catch (error) {
        console.error('Erreur chargement contenu généré:', error);
    }
}

// =======================================================
// BLOG
// =======================================================
async function displayBlogList() {
    const container = document.getElementById('blog-list');
    if (!container) return;

    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const allArticles = [...(window.generatedArticles || []), ...(data?.blog || [])];

    if (allArticles.length === 0) {
        container.innerHTML = '<div class="no-events">Aucun article.</div>';
        return;
    }

    const horizontalContainer = document.getElementById('blog-horizontal-list');
    if (horizontalContainer) {
        let hHtml = '';
        allArticles.slice(0, 8).forEach(article => {
            const title = article.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
            hHtml += `
                <div class="horizontal-item" onclick="window.location.href='article.html?slug=${article.slug}'">
                    <img src="${article.image_url || 'assets/images/default-logo.png'}" alt="${title}">
                    <div class="item-title">${title}</div>
                </div>
            `;
        });
        horizontalContainer.innerHTML = hHtml;
    }

    let html = '';
    allArticles.forEach(article => {
        let cleanTitle = article.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
        let excerpt = article.excerpt || article.content.substring(0, 200) + '...';
        let cleanExcerpt = excerpt.replace(/#+\s*/g, '').replace(/\*\*/g, '').replace(/\*/g, '').replace(/\[|\]/g, '').substring(0, 150) + '...';

        html += `
            <div class="card">
                ${article.image_url ? `<img src="${article.image_url}" alt="${cleanTitle}" style="width:100%; height:150px; object-fit:cover; border-radius:8px; margin-bottom:10px;">` : ''}
                <h3><a href="article.html?slug=${article.slug}" style="color: var(--or);">${cleanTitle}</a></h3>
                <div class="meta">${article.date} par ${article.author} ${article.match ? '• ' + article.match : ''}</div>
                <p>${cleanExcerpt}</p>
                <a href="article.html?slug=${article.slug}" class="btn btn-secondary">Lire</a>
            </div>
        `;
    });
    container.innerHTML = html;
}

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

    let cleanTitle = article.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
    document.title = cleanTitle + ' - Mr XPRONOS';
    let htmlContent = window.marked ? window.marked.parse(article.content) : article.content.replace(/\n/g, '<br>');
    container.innerHTML = `
        <h1>${cleanTitle}</h1>
        <div class="meta">${article.date} par ${article.author}</div>
        ${article.image_url ? `<img src="${article.image_url}" alt="${cleanTitle}" style="max-width:100%; border-radius:8px; margin:20px 0;">` : ''}
        <div style="margin-top: 2rem;">${htmlContent}</div>
        <a href="blog.html" class="btn btn-secondary" style="margin-top: 2rem;">← Retour au blog</a>
    `;
}

// =======================================================
// CONSEILS
// =======================================================
async function displayConseils() {
    const container = document.getElementById('conseils-list');
    if (!container) return;

    if (!window.generatedConseils) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const allConseils = [...(window.generatedConseils || []), ...(data?.conseils || [])];

    if (allConseils.length === 0) {
        container.innerHTML = '<div class="no-events">Aucun conseil.</div>';
        return;
    }

    const horizontalContainer = document.getElementById('conseils-horizontal-list');
    if (horizontalContainer) {
        let hHtml = '';
        allConseils.slice(0, 8).forEach(conseil => {
            const title = conseil.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
            hHtml += `
                <div class="horizontal-item" onclick="showConseilDetail(${conseil.id})">
                    <img src="${conseil.image_url || 'assets/images/default-logo.png'}" alt="${title}">
                    <div class="item-title">${title}</div>
                </div>
            `;
        });
        horizontalContainer.innerHTML = hHtml;
    }

    window.conseilsData = allConseils;

    let html = '';
    allConseils.forEach(c => {
        let cleanTitle = c.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
        let htmlContent = window.marked ? window.marked.parse(c.content) : c.content.replace(/\n/g, '<br>');
        html += `
            <div class="card">
                ${c.image_url ? `<img src="${c.image_url}" alt="${cleanTitle}" style="width:100%; height:150px; object-fit:cover; border-radius:8px; margin-bottom:10px;">` : ''}
                <h3>${cleanTitle}</h3>
                <div>${htmlContent}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

window.showConseilDetail = function(id) {
    const conseil = window.conseilsData.find(c => c.id === id);
    if (!conseil) return;
    const modal = document.getElementById('conseil-modal');
    if (!modal) return;
    document.getElementById('conseil-modal-title').textContent = conseil.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
    document.getElementById('conseil-modal-image').src = conseil.image_url || 'assets/images/default-logo.png';
    document.getElementById('conseil-modal-content').innerHTML = window.marked ? window.marked.parse(conseil.content) : conseil.content.replace(/\n/g, '<br>');
    modal.style.display = 'flex';
};

window.closeConseilModal = function() {
    const modal = document.getElementById('conseil-modal');
    if (modal) modal.style.display = 'none';
};

// =======================================================
// INFOS
// =======================================================
async function displayInfos() {
    const container = document.getElementById('infos-list');
    if (!container) return;
    const data = await loadDataGeneric();
    if (!data || !data.infos) return;
    data.infos.forEach(i => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<h3>${i.title}</h3><p>${i.content}</p>`;
        container.appendChild(card);
    });
}

// =======================================================
// ACTUALITÉS (RSS)
// =======================================================
async function displayFootNews() {
    const container = document.getElementById('foot-news-container');
    if (!container) return;
    try {
        const resp = await fetch('footnews.json?t=' + Date.now());
        if (!resp.ok) throw new Error('Erreur chargement');
        const news = await resp.json();
        if (news.length === 0) {
            container.innerHTML = '<div class="no-events">Aucune actualité pour le moment.</div>';
            return;
        }
        let html = '';
        news.forEach(item => {
            html += `
                <div class="news-card card">
                    ${item.image ? `<img src="${item.image}" alt="${item.title}" class="news-image" style="width:100%; border-radius:8px; margin-bottom:10px;">` : ''}
                    <h3><a href="${item.link}" target="_blank" rel="noopener noreferrer" style="color: var(--or);">${item.title}</a></h3>
                    <p class="meta">${new Date(item.published).toLocaleDateString('fr-FR')}</p>
                    <p>${item.summary}</p>
                    <a href="${item.link}" target="_blank" class="btn btn-secondary" style="margin-top:10px;">Lire la suite</a>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (error) {
        console.error('Erreur chargement actualités:', error);
        container.innerHTML = '<div class="error">Impossible de charger les actualités.</div>';
    }
}

// =======================================================
// BONUS
// =======================================================
let allBonus = [];

async function initBonusPage() {
    const data = await loadDataGeneric();
    allBonus = data?.bonus || [];

    const select = document.getElementById('bonus-bookmaker-select');
    if (!select) return;

    const bookmakers = [...new Set(allBonus.map(b => b.bookmaker))].filter(Boolean);
    bookmakers.sort();

    bookmakers.forEach(bm => {
        const option = document.createElement('option');
        option.value = bm;
        option.textContent = bm;
        select.appendChild(option);
    });

    select.addEventListener('change', (e) => {
        currentBookmaker = e.target.value;
        displayBonusThumbnails();
    });

    if (bookmakers.length > 0) {
        select.value = bookmakers[0];
        currentBookmaker = bookmakers[0];
        displayBonusThumbnails();
    } else {
        document.getElementById('bonus-thumbnails').innerHTML = '<p>Aucun bonus disponible.</p>';
    }
}

let currentBookmaker = null;

function displayBonusThumbnails() {
    const container = document.getElementById('bonus-thumbnails');
    if (!container) return;

    const filtered = allBonus.filter(b => b.bookmaker === currentBookmaker && b.active && new Date(b.end_date) >= new Date());

    if (filtered.length === 0) {
        container.innerHTML = '<p>Aucun bonus actif pour ce bookmaker.</p>';
        return;
    }

    let html = '';
    filtered.forEach(b => {
        html += `
            <div class="bonus-thumb" onclick="showBonusDetail(${b.id})">
                <img src="${b.image}" alt="${b.title}">
                <div class="bonus-thumb-title">${b.title}</div>
            </div>
        `;
    });
    container.innerHTML = html;

    window.bonusDetails = filtered;
}

window.showBonusDetail = function(id) {
    const bonus = window.bonusDetails.find(b => b.id === id);
    if (!bonus) return;

    const modal = document.getElementById('bonus-modal');
    if (!modal) return;
    document.getElementById('bonus-modal-title').textContent = bonus.title;
    document.getElementById('bonus-modal-image').src = bonus.image;
    document.getElementById('bonus-modal-description').innerHTML = bonus.description;
    document.getElementById('bonus-modal-footer').innerHTML = bonus.footer || '';
    document.getElementById('bonus-modal-link').href = bonus.link || '#';
    modal.style.display = 'flex';
};

window.closeBonusModal = function() {
    const modal = document.getElementById('bonus-modal');
    if (modal) modal.style.display = 'none';
};

async function displayBonusList() {
    const container = document.getElementById('bonus-grid');
    if (!container) return;

    const data = await loadDataGeneric();
    const bonus = data?.bonus || [];
    const activeBonus = bonus.filter(b => b.active && new Date(b.end_date) >= new Date());

    if (activeBonus.length === 0) {
        container.innerHTML = '<div class="no-events">Aucun bonus actif pour le moment.</div>';
        return;
    }

    let html = '';
    activeBonus.forEach(b => {
        html += `
            <div class="bonus-card">
                <img src="${b.image}" alt="${b.title}" class="bonus-image">
                <h3>${b.title}</h3>
                <p>${b.description}</p>
                <div class="bonus-footer">
                    <span>Valable du ${formatDate(b.start_date)} au ${formatDate(b.end_date)}</span>
                    ${b.link ? `<a href="${b.link}" target="_blank" class="btn btn-primary">Profiter</a>` : ''}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function formatDate(dateStr) {
    const [y, m, d] = dateStr.split('-');
    return `${d}/${m}/${y}`;
}

// =======================================================
// HISTORIQUE
// =======================================================
async function displayHistory() {
    const container = document.getElementById('history-container');
    if (!container) return;

    await loadData();
    if (!allData || !allData.matches) {
        container.innerHTML = '<div class="no-events">Aucun historique disponible.</div>';
        return;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let historyMatches = allData.matches.filter(m => {
        const matchDate = new Date(m.event_date);
        return matchDate < today;
    });

    if (historyMatches.length === 0) {
        container.innerHTML = '<div class="no-events">Aucun match dans cette période.</div>';
        return;
    }

    const catOrder = { vip: 0, pro: 1, simple: 2 };
    historyMatches.sort((a, b) => {
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
    const sortedDays = Object.keys(groupedByDay).sort((a, b) => new Date(b) - new Date(a));

    sortedDays.forEach(day => {
        const dayDate = new Date(day + 'T12:00:00');
        const formattedDate = dayDate.toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        html += `<h2 class="day-header" style="color: var(--or); margin-top: 2rem;">${formattedDate}</h2>`;

        groupedByDay[day].forEach(m => {
            const pred = m.prediction || {};
            const doubleChance = pred.double_chance || 'N/A';
            const over25 = pred.over_25 ? 'Oui' : 'Non';
            let confidence = pred.confidence || 0;
            if (typeof confidence === 'string') confidence = parseFloat(confidence);
            if (isNaN(confidence)) confidence = 0;
            if (confidence > 100) confidence = confidence / 100;
            confidence = Math.min(100, Math.round(confidence * 10) / 10);

            const matchTime = formatMatchTime(m.event_date);
            const statusFr = translateStatus(m.status);
            const statusClass = getStatusClass(m.status);

            const verifiedDouble = m.verified_double ? 'checked' : '';
            const verifiedOver = m.verified_over ? 'checked' : '';
            const defaultLogo = 'assets/images/default-logo.png';
            const winnerClass = (m.verified_double && m.verified_over) ? 'winner' : '';

            const xpronosBadge = m.badge ? `<span class="xpronos-badge">${m.badge}</span>` : '';
            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const categoryBadge = m.category ? `<span class="badge-category badge-${m.category}">${m.category.toUpperCase()}</span>` : '';

            html += `
                <div class="match-card ${winnerClass}">
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
                            <span class="match-time"><i>🕒</i> ${matchTime}</span>
                        </div>
                    </div>
                    <div class="analysis-panel">
                        <h4>Pronostic ${xpronosBadge} ${categoryBadge}</h4>
                        <p><strong>Double chance :</strong> ${doubleChance} <input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled></p>
                        <p><strong>Over 2.5 :</strong> ${over25} <input type="checkbox" class="prediction-checkbox" ${verifiedOver} disabled></p>
                        <p><strong>Fiabilité :</strong> ${confidence}%</p>
                        ${premiumBadge}
                    </div>
                </div>
            `;
        });
    });
    container.innerHTML = html;
}

// =======================================================
// TAUX DE RÉUSSITE ET SCROLL PROGRESS
// =======================================================
function updateSuccessRate() {
    const container = document.getElementById('success-rate-container');
    if (!container) return;
    const matches = allData.matches || [];
    const finished = matches.filter(m => m.status === 'finished' && (m.verified_double !== undefined));
    if (finished.length === 0) {
        container.style.display = 'none';
        return;
    }
    const successful = finished.filter(m => m.verified_double && m.verified_over).length;
    const rate = ((successful / finished.length) * 100).toFixed(1);
    const stats = allData.stats || {};
    const roi = stats.roi || 0;
    container.innerHTML = `
        <div class="success-rate-item">
            <div class="success-rate-value">${rate}%</div>
            <div class="success-rate-label">Réussite</div>
        </div>
        <div class="success-rate-item">
            <div class="success-rate-value">${roi > 0 ? '+' : ''}${roi}%</div>
            <div class="success-rate-label">ROI</div>
        </div>
    `;
    container.style.display = 'flex';
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