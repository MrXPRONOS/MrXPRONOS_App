/**
 * main.js - Script principal pour Mr XPRONOS
 * Version avec onglets Pro/VIP toujours visibles et icônes PNG.
 */

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

let shareCount = parseInt(localStorage.getItem('shareCount') || '0');
const shareLimits = { pro: 5, vip: 10 };

// Liste des ligues les plus populaires (ordre de priorité)
const POPULAR_LEAGUES = [
    "Premier League",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Eredivisie",
    "Primeira Liga",
    "Super Lig",
    "Russian Premier League",
    "MLS",
    "Brasileirão",
    "Liga Profesional",
    "Jupiler Pro League",
    "Super League",
    "Championship",
    "Liga Portugal",
    "Trendyol Super Lig"
];

// =======================================================
// INITIALISATION
// =======================================================
document.addEventListener('DOMContentLoaded', () => {
    if (matchesContainer) {
        initPronostics();
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

// =======================================================
// FONCTIONS POUR LA PAGE PRONOSTICS
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
        matchesContainer.innerHTML = '<div class="error">❌ Erreur de chargement des données.</div>';
    }
}

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
            matchesContainer.innerHTML = '<div class="warning">⚠️ Données en cache.</div>';
            renderBookmakers(allData.bookmakers);
        } else {
            matchesContainer.innerHTML = '<div class="error">❌ Impossible de charger.</div>';
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

function hideEmptyTabs() {
    const counts = { simple: 0, pro: 0, vip: 0 };
    allData.matches.forEach(m => counts[m.category]++);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        const cat = btn.dataset.cat;
        if (cat === 'pro' || cat === 'vip') {
            // Toujours afficher les onglets Pro et VIP, même sans matchs
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

    // Boutons de partage standard
    document.getElementById('share-wa')?.addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg')?.addEventListener('click', () => share('telegram'));
    document.getElementById('close-popup')?.addEventListener('click', () => {
        sharePopup.classList.remove('active');
    });

    // Boutons de l'overlay VIP
    document.getElementById('share-wa-locked')?.addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg-locked')?.addEventListener('click', () => share('telegram'));
}

function handleCategoryChange() {
    if (currentCategory === 'simple') {
        hideVipLocked();
        filterAndDisplay();
    } else {
        const target = shareLimits[currentCategory];
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
        const remaining = target - shareCount;
        vipLockedOverlay.querySelector('h3').textContent = `🔒 ${category === 'pro' ? 'Pronostics Pro' : 'Pronostics VIP'} verrouillés`;
        vipLockedOverlay.querySelector('p').innerHTML = `Partagez ce lien à <strong>${remaining}</strong> ami(s) pour débloquer.`;
        document.getElementById('share-count-locked').textContent = shareCount;
        document.getElementById('share-target-locked').textContent = target;
        vipLockedOverlay.style.display = 'flex';
        matchesContainer.style.display = 'none';
    } else {
        const target = shareLimits[category];
        showSharePopup(category, target - shareCount);
    }
}

function hideVipLocked() {
    if (vipLockedOverlay) {
        vipLockedOverlay.style.display = 'none';
        matchesContainer.style.display = 'grid';
    }
}

function showSharePopup(category, remaining) {
    if (!sharePopup) return;
    shareRemaining.textContent = remaining;
    shareCurrent.textContent = shareCount;
    shareTarget.textContent = shareLimits[category];
    shareMessage.innerHTML = `Pour accéder aux pronostics ${category === 'pro' ? 'Pro' : 'VIP'}, partagez ce lien à <span id="share-remaining">${remaining}</span> amis.`;
    sharePopup.classList.add('active');
}

function share(platform) {
    // Messages personnalisés selon la plateforme
    let message = '';
    let url = '';

    if (platform === 'whatsapp') {
        message = `🔥 *Mr XPRONOS* - Des pronostics fiables qui font la différence !\n\n📊 Hier encore, nos coupons ont rapporté gros. Aujourd'hui, ne rate pas les analyses exclusives.\n\n👉 Rejoins la communauté et débloque les pronostics Pro/VIP en partageant ce lien :\n\nhttps://votre-site.com\n\n⚽ Arrête d'acheter des coupons qui perdent chaque jour. Un vrai pronostiqueur ne vend pas ses analyses si elles sont gagnantes. Rejoins-nous gratuitement !`;
        url = `https://wa.me/?text=${encodeURIComponent(message)}`;
    } else { // Telegram
        message = `🔥 *Mr XPRONOS* - Des pronostics fiables qui font la différence !\n\n📊 Hier encore, nos coupons ont rapporté gros. Aujourd'hui, ne rate pas les analyses exclusives.\n\n👉 Rejoins la communauté et débloque les pronostics Pro/VIP en partageant ce lien :\n\nhttps://votre-site.com\n\n⚽ Arrête d'acheter des coupons qui perdent chaque jour. Un vrai pronostiqueur ne vend pas ses analyses si elles sont gagnantes. Rejoins-nous gratuitement !`;
        url = `https://t.me/share/url?url=${encodeURIComponent('https://votre-site.com')}&text=${encodeURIComponent(message)}`;
    }

    window.open(url, '_blank');

    // Incrémenter le compteur
    shareCount++;
    localStorage.setItem('shareCount', shareCount);
    updateShareCounter();
    recordEvent('share');

    const target = shareLimits[currentCategory];
    if (shareCount >= target) {
        hideVipLocked();
        filterAndDisplay();
    } else {
        if (vipLockedOverlay && vipLockedOverlay.style.display === 'flex') {
            showVipLocked(currentCategory);
        } else {
            showSharePopup(currentCategory, target - shareCount);
        }
    }
}

function updateShareCounter() {
    const counter = document.getElementById('share-counter');
    if (counter) counter.textContent = `🔥 ${shareCount} partages aujourd'hui`;
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
        matchesContainer.innerHTML = '<div class="no-events">Aucun match disponible.</div>';
        return;
    }

    const targetDate = getLocalDateString(currentDay);

    // Plus de cas "analyses", on garde uniquement le filtrage par catégorie
    const targetCat = (currentCategory === 'vip' && currentSubcat === 'pronostics') ? 'vip' : currentCategory;
    const filtered = allData.matches.filter(m => {
        const eventLocalDate = getLocalDateFromEvent(m.event_date);
        return m.category === targetCat && eventLocalDate === targetDate;
    });

    const sorted = sortMatchesByLeague(filtered);
    renderMatches(sorted);
}

function formatMatchTime(isoString) {
    if (!isoString) return 'Horaire inconnu';
    const date = new Date(isoString);
    if (isNaN(date)) return 'Horaire inconnu';
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function renderMatches(matches) {
    if (matches.length === 0) {
        matchesContainer.innerHTML = '<div class="no-events">Aucun match.</div>';
        return;
    }

    // Regrouper par ligue
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

            const verifiedDouble = m.verified_double ? 'checked' : '';
            const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
            const defaultLogo = 'assets/images/default-logo.png';

            const isWinner = m.verified_double;
            const winnerClass = isWinner ? 'winner' : '';

            // Badge XPRONOS
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
                            ${m.date === getLocalDateString('yesterday') ? `<input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled>` : ''}
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

    // Animer les barres de confiance
    document.querySelectorAll('.confidence-fill').forEach(bar => {
        let value = bar.getAttribute('data-value');
        setTimeout(() => {
            bar.style.width = value + '%';
        }, 300);
    });

    // Ajouter les étincelles pour les matchs gagnants
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

function renderBookmakers(bookmakers) {
    if (!bookmakers) return;
    if (bookmakersFooter) {
        bookmakersFooter.innerHTML = '';
        bookmakers.forEach(b => {
            const a = document.createElement('a');
            a.href = b.url;
            a.target = '_blank';
            const img = document.createElement('img');
            img.src = b.logo;
            img.alt = b.name;
            a.appendChild(img);
            bookmakersFooter.appendChild(a);
        });
    }
    if (bookmakersBonus) {
        bookmakersBonus.innerHTML = '';
        bookmakers.forEach(b => {
            const div = document.createElement('div');
            div.className = 'bookmaker-card';
            div.innerHTML = `
                <img src="${b.logo}" alt="${b.name}">
                <h3>${b.name}</h3>
                <p>Bonus de bienvenue jusqu'à 130€</p>
                <a href="${b.url}" class="btn btn-primary" target="_blank">S'inscrire</a>
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
        timestamp: new Date().toISOString()
    });
    localStorage.setItem('userEvents', JSON.stringify(events));
}
recordEvent('visit');

// =======================================================
// FONCTIONS POUR LES AUTRES PAGES
// =======================================================

async function loadGeneratedContent() {
    try {
        const articlesResp = await fetch('articles.json?t=' + Date.now());
        if (articlesResp.ok) {
            window.generatedArticles = await articlesResp.json();
        }
        const conseilsResp = await fetch('conseils.json?t=' + Date.now());
        if (conseilsResp.ok) {
            window.generatedConseils = await conseilsResp.json();
        }
    } catch (error) {
        console.error('Erreur chargement contenu généré:', error);
    }
}

async function displayBlogList() {
    const container = document.getElementById('blog-list');
    if (!container) return;
    if (!window.generatedArticles) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const allArticles = [...(window.generatedArticles || []), ...(data?.blog || [])];
    if (allArticles.length === 0) return;
    allArticles.forEach(article => {
        let cleanTitle = article.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
        let excerpt = article.excerpt || article.content.substring(0, 200) + '...';
        let cleanExcerpt = excerpt.replace(/#+\s*/g, '').replace(/\*\*/g, '').replace(/\*/g, '').replace(/\[|\]/g, '').substring(0, 150) + '...';
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h3><a href="article.html?slug=${article.slug}" style="color: var(--or);">${cleanTitle}</a></h3>
            <div class="meta">${article.date} par ${article.author} ${article.match ? '• ' + article.match : ''}</div>
            ${article.image_url ? `<img src="${article.image_url}" alt="${cleanTitle}" style="max-width:100%; border-radius:8px; margin:10px 0;">` : ''}
            <p>${cleanExcerpt}</p>
            <a href="article.html?slug=${article.slug}" class="btn btn-secondary">Lire</a>
        `;
        container.appendChild(card);
    });
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

async function displayConseils() {
    const container = document.getElementById('conseils-list');
    if (!container) return;
    if (!window.generatedConseils) await loadGeneratedContent();
    const data = await loadDataGeneric();
    const allConseils = [...(window.generatedConseils || []), ...(data?.conseils || [])];
    if (allConseils.length === 0) return;
    allConseils.forEach(c => {
        let cleanTitle = c.title.replace(/#+\s*/g, '').replace(/\*\*/g, '');
        let htmlContent = window.marked ? window.marked.parse(c.content) : c.content.replace(/\n/g, '<br>');
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h3>${cleanTitle}</h3>
            ${c.image_url ? `<img src="${c.image_url}" alt="${cleanTitle}" style="max-width:100%; border-radius:8px; margin:10px 0;">` : ''}
            <div>${htmlContent}</div>
        `;
        container.appendChild(card);
    });
}

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
// NOUVELLES FONCTIONS (taux de réussite, scroll)
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
    const successful = finished.filter(m => m.verified_double).length;
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