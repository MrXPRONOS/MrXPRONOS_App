/**
 * admin-stats.js - Gestion des statistiques pour l'admin
 */

// Périodes disponibles
const periods = {
    today: 'Aujourd\'hui',
    yesterday: 'Hier',
    currentWeek: 'Semaine en cours',
    lastWeek: 'Semaine passée',
    currentMonth: 'Mois en cours',
    lastMonth: 'Mois passé',
    currentYear: 'Année en cours',
    lastYear: 'Année passée',
    custom: 'Personnalisé'
};

let currentPeriod = 'today';
let customStart = null;
let customEnd = null;

// Éléments DOM
const periodSelect = document.getElementById('period-select');
const customDateRange = document.getElementById('custom-date-range');
const startDateInput = document.getElementById('start-date');
const endDateInput = document.getElementById('end-date');
const applyCustomBtn = document.getElementById('apply-custom');

const totalUsersEl = document.getElementById('total-users');
const onlineUsersEl = document.getElementById('online-users');
const offlineUsersEl = document.getElementById('offline-users');
const totalSharesEl = document.getElementById('total-shares');
const newUsersEl = document.getElementById('new-users');
const oldUsersEl = document.getElementById('old-users');
const invitedUsersEl = document.getElementById('invited-users');
const avgUsageEl = document.getElementById('avg-usage');

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    initStats();
    setupEventListeners();
    updateStats();
});

function initStats() {
    // Remplir le select des périodes
    for (const [value, label] of Object.entries(periods)) {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        periodSelect.appendChild(option);
    }
    periodSelect.value = currentPeriod;
}

function setupEventListeners() {
    periodSelect.addEventListener('change', () => {
        currentPeriod = periodSelect.value;
        if (currentPeriod === 'custom') {
            customDateRange.style.display = 'flex';
        } else {
            customDateRange.style.display = 'none';
            updateStats();
        }
    });

    applyCustomBtn.addEventListener('click', () => {
        customStart = startDateInput.value;
        customEnd = endDateInput.value;
        if (customStart && customEnd) {
            updateStats();
        } else {
            alert('Veuillez sélectionner une période valide.');
        }
    });
}

function getDateRange() {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    let start, end;

    switch (currentPeriod) {
        case 'today':
            start = today;
            end = new Date(today.getTime() + 24*60*60*1000 - 1);
            break;
        case 'yesterday':
            start = new Date(today.getTime() - 24*60*60*1000);
            end = new Date(today.getTime() - 1);
            break;
        case 'currentWeek':
            // Semaine commence lundi
            const dayOfWeek = today.getDay() || 7; // dimanche = 0, on veut lundi = 1
            const monday = new Date(today);
            monday.setDate(today.getDate() - dayOfWeek + 1);
            start = monday;
            end = new Date(today.getTime() + 24*60*60*1000 - 1);
            break;
        case 'lastWeek':
            const lastMonday = new Date(today);
            lastMonday.setDate(today.getDate() - (today.getDay() || 7) - 6);
            start = lastMonday;
            end = new Date(lastMonday.getTime() + 7*24*60*60*1000 - 1);
            break;
        case 'currentMonth':
            start = new Date(today.getFullYear(), today.getMonth(), 1);
            end = new Date(today.getFullYear(), today.getMonth() + 1, 0, 23, 59, 59);
            break;
        case 'lastMonth':
            start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            end = new Date(today.getFullYear(), today.getMonth(), 0, 23, 59, 59);
            break;
        case 'currentYear':
            start = new Date(today.getFullYear(), 0, 1);
            end = new Date(today.getFullYear(), 11, 31, 23, 59, 59);
            break;
        case 'lastYear':
            start = new Date(today.getFullYear() - 1, 0, 1);
            end = new Date(today.getFullYear() - 1, 11, 31, 23, 59, 59);
            break;
        case 'custom':
            if (customStart && customEnd) {
                start = new Date(customStart);
                end = new Date(customEnd);
                end.setHours(23, 59, 59);
            } else {
                start = today;
                end = new Date(today.getTime() + 24*60*60*1000 - 1);
            }
            break;
        default:
            start = today;
            end = new Date(today.getTime() + 24*60*60*1000 - 1);
    }
    return { start, end };
}

function updateStats() {
    const { start, end } = getDateRange();
    const events = JSON.parse(localStorage.getItem('userEvents')) || [];

    // Filtrer les événements dans la période
    const filteredEvents = events.filter(e => {
        const d = new Date(e.timestamp);
        return d >= start && d <= end;
    });

    // Compter les visiteurs uniques (par IP simulée ? On utilise un identifiant aléatoire stocké dans localStorage)
    let userId = localStorage.getItem('userId');
    if (!userId) {
        userId = 'user_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('userId', userId);
    }

    // Pour les stats, on va générer des données fictives basées sur les événements réels
    // Nombre total d'utilisateurs (simulé)
    const totalUsers = 150 + Math.floor(Math.random() * 50); // fictif

    // Utilisateurs en ligne : ceux qui ont visité dans les 5 dernières minutes
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000);
    const online = events.filter(e => e.type === 'visit' && new Date(e.timestamp) >= fiveMinAgo).length;
    const onlineUsers = Math.min(online, totalUsers);

    // Utilisateurs hors ligne
    const offlineUsers = totalUsers - onlineUsers;

    // Nombre de partages dans la période
    const shares = filteredEvents.filter(e => e.type === 'share').length;

    // Nouveaux utilisateurs : ceux dont la première visite est dans la période
    // On stocke la première visite dans localStorage
    let firstVisit = localStorage.getItem('firstVisit');
    if (!firstVisit) {
        firstVisit = new Date().toISOString();
        localStorage.setItem('firstVisit', firstVisit);
    }
    const firstVisitDate = new Date(firstVisit);
    const isNew = firstVisitDate >= start && firstVisitDate <= end;

    // Anciens utilisateurs : ceux dont la première visite est avant la période
    const isOld = firstVisitDate < start;

    // Nombre de personnes invitées (simulé)
    const invited = Math.floor(Math.random() * 30);

    // Durée moyenne d'utilisation (en jours) - simulée
    const avgDays = Math.floor(Math.random() * 30) + 10;

    // Mise à jour des éléments
    totalUsersEl.textContent = totalUsers;
    onlineUsersEl.textContent = onlineUsers;
    offlineUsersEl.textContent = offlineUsers;
    totalSharesEl.textContent = shares;
    newUsersEl.textContent = isNew ? 'Oui' : 'Non';
    oldUsersEl.textContent = isOld ? 'Oui' : 'Non';
    invitedUsersEl.textContent = invited;
    avgUsageEl.textContent = avgDays + ' jours';
}