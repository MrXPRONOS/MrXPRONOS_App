/**
 * main.js - Script principal pour Mr XPRONOS
 * Version avec sous-onglets VIP (pronostics/analyses) et analyses ML complètes.
 * Correction : affichage des heures dans le fuseau local de l'utilisateur.
 * Mise à jour : hideEmptyTabs() gère désormais les sous-onglets VIP.
 * Chemins relatifs.
 */

// =======================================================
// VARIABLES GLOBALES
// =======================================================
let allData = null;
let currentCategory = 'simple';
let currentSubcat = 'pronostics'; // pour VIP : 'pronostics' ou 'analyses'
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
const defaultLogo = 'assets/images/default-logo.png';

let shareCount = parseInt(localStorage.getItem('shareCount') || '0');
const shareLimits = { pro: 5, vip: 10 };

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

/**
 * Met à jour l'affichage des onglets principaux et des sous-onglets VIP
 * en fonction des données disponibles.
 */
function hideEmptyTabs() {
    // Compter les matchs par catégorie
    const counts = { simple: 0, pro: 0, vip: 0 };
    let hasML = 0; // nombre de matchs avec données ML complètes
    allData.matches.forEach(m => {
        counts[m.category]++;
        if (m.ml_full) hasML++;
    });

    // Gérer les onglets principaux
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const cat = btn.dataset.cat;
        if (cat === 'vip') {
            // L'onglet VIP est visible s'il y a des matchs classés VIP OU des matchs avec ML
            btn.style.display = (counts.vip > 0 || hasML > 0) ? 'inline-block' : 'none';
        } else {
            btn.style.display = counts[cat] > 0 ? 'inline-block' : 'none';
        }
    });

    // Si la catégorie courante est masquée, basculer sur la première visible
    const visibleTabs = Array.from(document.querySelectorAll('.tab-btn')).filter(btn => btn.style.display !== 'none');
    if (visibleTabs.length > 0) {
        const currentActive = document.querySelector('.tab-btn.active');
        if (!currentActive || currentActive.style.display === 'none') {
            // Activer le premier onglet visible
            visibleTabs[0].classList.add('active');
            currentCategory = visibleTabs[0].dataset.cat;
            if (currentCategory !== 'vip') currentSubcat = 'pronostics';
        }
    } else {
        // Aucun onglet visible, on cache la barre
        const tabBar = document.querySelector('.category-tabs');
        if (tabBar) tabBar.style.display = 'none';
    }

    // Gérer les sous-onglets VIP
    if (vipSubtabs) {
        const showPronostics = counts.vip > 0;
        const showAnalyses = hasML > 0;
        const subtabBtns = vipSubtabs.querySelectorAll('.subtab-btn');
        if (subtabBtns.length >= 2) {
            subtabBtns[0].style.display = showPronostics ? 'inline-block' : 'none'; // Pronostics
            subtabBtns[1].style.display = showAnalyses ? 'inline-block' : 'none';   // Analyses
        }
        // Afficher la barre des sous-onglets si au moins un est visible
        vipSubtabs.style.display = (showPronostics || showAnalyses) ? 'flex' : 'none';
        
        // Si le sous-onglet actif est masqué, basculer sur l'autre ou sur pronostics par défaut
        const activeSub = vipSubtabs.querySelector('.subtab-btn.active');
        if (activeSub && activeSub.style.display === 'none') {
            // Chercher le premier sous-onglet visible
            const firstVisible = Array.from(subtabBtns).find(btn => btn.style.display !== 'none');
            if (firstVisible) {
                firstVisible.classList.add('active');
                currentSubcat = firstVisible.dataset.subcat;
            } else {
                // Aucun sous-onglet visible, on désactive
                currentSubcat = 'pronostics'; // fallback
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
    // Onglets principaux
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.cat;
            if (currentCategory !== 'vip') {
                currentSubcat = 'pronostics'; // reset
            }
            handleCategoryChange();
        });
    });

    // Sous-onglets VIP
    document.querySelectorAll('.subtab-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.subtab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSubcat = btn.dataset.subcat;
            filterAndDisplay();
        });
    });

    // Filtres jour
    document.querySelectorAll('.day-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.day-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentDay = btn.dataset.day;
            filterAndDisplay();
        });
    });

    // Boutons de partage
    document.getElementById('share-wa')?.addEventListener('click', () => share('whatsapp'));
    document.getElementById('share-tg')?.addEventListener('click', () => share('telegram'));
    document.getElementById('close-popup')?.addEventListener('click', () => {
        sharePopup.classList.remove('active');
    });
}

function handleCategoryChange() {
    if (currentCategory === 'simple') {
        filterAndDisplay();
    } else {
        const target = shareLimits[currentCategory];
        if (shareCount >= target) {
            filterAndDisplay();
        } else {
            showSharePopup(currentCategory, target - shareCount);
        }
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
    const message = encodeURIComponent('Rejoignez Mr XPRONOS pour des pronostics sportifs de qualité ! https://votre-site.com');
    const url = platform === 'whatsapp' ? `https://wa.me/?text=${message}` : `https://t.me/share/url?url=${encodeURIComponent('https://votre-site.com')}&text=${message}`;
    window.open(url, '_blank');

    shareCount++;
    localStorage.setItem('shareCount', shareCount);
    updateShareCounter();

    // Enregistrer l'événement de partage pour les stats
    recordEvent('share');

    const target = shareLimits[currentCategory];
    if (shareCount >= target) {
        sharePopup.classList.remove('active');
        filterAndDisplay();
    } else {
        showSharePopup(currentCategory, target - shareCount);
    }
}

function updateShareCounter() {
    const counter = document.getElementById('share-counter');
    if (counter) counter.textContent = `🔥 ${shareCount} partages aujourd'hui`;
}

/**
 * Retourne la date locale du jour demandé sous forme de chaîne YYYY-MM-DD.
 * @param {string} day - 'today', 'tomorrow', 'yesterday'
 * @returns {string}
 */
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

/**
 * Convertit la date/heure d'un événement (au format ISO avec fuseau) en date locale YYYY-MM-DD.
 * @param {string} isoString
 * @returns {string}
 */
function getLocalDateFromEvent(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    if (isNaN(date)) return null;
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function filterAndDisplay() {
    if (!allData || !allData.matches) {
        matchesContainer.innerHTML = '<div class="no-events">Aucun match disponible.</div>';
        return;
    }

    const targetDate = getLocalDateString(currentDay);

    let filtered;
    if (currentCategory === 'vip' && currentSubcat === 'analyses') {
        // Analyses VIP : tous les matchs (quelle que soit leur catégorie) avec des prédictions ML
        filtered = allData.matches.filter(m => {
            const eventLocalDate = getLocalDateFromEvent(m.event_date);
            return eventLocalDate === targetDate && m.ml_full;
        });
    } else {
        // Sinon : filtrer par catégorie (simple, pro, ou vip-pronostics)
        const targetCat = (currentCategory === 'vip' && currentSubcat === 'pronostics') ? 'vip' : currentCategory;
        filtered = allData.matches.filter(m => {
            const eventLocalDate = getLocalDateFromEvent(m.event_date);
            return m.category === targetCat && eventLocalDate === targetDate;
        });
    }

    renderMatches(filtered);
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

    let html = '';
    matches.forEach(m => {
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
        const premiumBadge = (m.category !== 'simple') ? '<span class="badge-premium">🔒 Premium</span>' : '';
        const defaultLogo = 'assets/images/default-logo.png';

        // Partie commune (info match)
        let matchHtml = `
            <div class="match-card">
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
        `;

        // Partie analyse (différente selon le mode)
        if (currentCategory === 'vip' && currentSubcat === 'analyses' && m.ml_full) {
            // Affichage complet des données ML
            const ml = m.ml_full;
            matchHtml += `
                <div class="analysis-panel analysis-full">
                    <h4>Analyse ML complète</h4>
                    <p><strong>Probabilités :</strong> H: ${ml.prob_home_win?.toFixed(1)}% | N: ${ml.prob_draw?.toFixed(1)}% | A: ${ml.prob_away_win?.toFixed(1)}%</p>
                    <p><strong>Résultat prédit :</strong> ${ml.predicted_result}</p>
                    <p><strong>Buts attendus :</strong> domicile ${ml.expected_home_goals?.toFixed(2)} - extérieur ${ml.expected_away_goals?.toFixed(2)}</p>
                    <p><strong>Over 2.5 :</strong> ${ml.prob_over_25?.toFixed(1)}% (recommandé: ${ml.over_25_recommend ? 'Oui' : 'Non'})</p>
                    <p><strong>BTTS :</strong> ${ml.prob_btts_yes?.toFixed(1)}% (recommandé: ${ml.btts_recommend ? 'Oui' : 'Non'})</p>
                    <p><strong>Score probable :</strong> ${ml.most_likely_score}</p>
                    <p><strong>Favori :</strong> ${ml.favorite === 'H' ? 'Domicile' : ml.favorite === 'A' ? 'Extérieur' : 'Aucun'} (${ml.favorite_prob?.toFixed(1)}%)</p>
                    <p><strong>Confiance modèle :</strong> ${(ml.confidence * 100).toFixed(1)}%</p>
                </div>
            `;
        } else {
            // Affichage standard (pronostic simple)
            matchHtml += `
                <div class="analysis-panel">
                    <h4>Pronostic</h4>
                    <p>
                        <strong>Double chance :</strong> ${doubleChance}
                        ${m.date === getLocalDateString('yesterday') ? `<input type="checkbox" class="prediction-checkbox" ${verifiedDouble} disabled>` : ''}
                    </p>
                    <p>
                        <strong>Over 2.5 :</strong> ${over25}
                        ${m.date === getLocalDateString('yesterday') ? `<input type="checkbox" class="prediction-checkbox" ${verifiedOver} disabled>` : ''}
                    </p>
                    <p><strong>Fiabilité :</strong> ${confidence}%</p>
                    ${premiumBadge}
                </div>
            `;
        }

        matchHtml += `</div>`;
        html += matchHtml;
    });
    matchesContainer.innerHTML = html;
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

// Enregistre un événement (visite, partage, etc.)
function recordEvent(type) {
    let events = JSON.parse(localStorage.getItem('userEvents')) || [];
    events.push({
        type: type,
        timestamp: new Date().toISOString()
    });
    localStorage.setItem('userEvents', JSON.stringify(events));
}

// À chaque chargement de page, enregistrer une visite
recordEvent('visit');

// =======================================================
// FONCTIONS POUR LES AUTRES PAGES
// =======================================================

async function displayBlogList() {
    const container = document.getElementById('blog-list');
    if (!container) return;
    const data = await loadDataGeneric();
    if (!data || !data.blog) return;
    data.blog.forEach(article => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <h3><a href="article.html?slug=${article.slug}" style="color: var(--or);">${article.title}</a></h3>
            <div class="meta">${article.date} par ${article.author}</div>
            <p>${article.excerpt}</p>
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
    const data = await loadDataGeneric();
    if (!data || !data.blog) return;
    const article = data.blog.find(a => a.slug === slug);
    if (!article) { container.innerHTML = '<p>Article non trouvé.</p>'; return; }
    document.title = article.title + ' - Mr XPRONOS';
    container.innerHTML = `
        <h1>${article.title}</h1>
        <div class="meta">${article.date} par ${article.author}</div>
        <div>${article.content}</div>
        <a href="blog.html" class="btn btn-secondary">← Retour</a>
    `;
}

async function displayConseils() {
    const container = document.getElementById('conseils-list');
    if (!container) return;
    const data = await loadDataGeneric();
    if (!data || !data.conseils) return;
    data.conseils.forEach(c => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<h3>${c.title}</h3><p>${c.content}</p>`;
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
