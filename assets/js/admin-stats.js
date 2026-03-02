/**
 * admin-stats.js - Statistiques réelles pour l'admin
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
const totalVisitsEl = document.getElementById('total-visits');
const totalSharesEl = document.getElementById('total-shares');
const newUsersEl = document.getElementById('new-users');
const oldUsersEl = document.getElementById('old-users');
const onlineUsersEl = document.getElementById('online-users');
const offlineUsersEl = document.getElementById('offline-users');
const avgVisitsEl = document.getElementById('avg-visits');

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

    // Charger les événements depuis localStorage
    const events = JSON.parse(localStorage.getItem('userEvents')) || [];
    const filteredEvents = events.filter(e => {
        const d = new Date(e.timestamp);
        return d >= start && d <= end;
    });

    // Compter les utilisateurs uniques (par userId)
    let userId = localStorage.getItem('userId');
    if (!userId) {
        userId = 'user_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('userId', userId);
    }

    // Extraire tous les userId des événements
    // En pratique, on stockerait l'userId avec chaque événement.
    // Pour l'instant, on simule : on prend les événements filtrés et on extrait un userId basé sur la date.
    // Pour une vraie application, il faudrait associer un userId à chaque événement.
    // Ici, on va générer des IDs fictifs basés sur les timestamps pour avoir une variété.
    const uniqueUsers = new Set();
    filteredEvents.forEach(e => {
        // Simule un userId à partir du timestamp (pas réaliste mais pour la démo)
        const fakeId = Math.floor(new Date(e.timestamp).getTime() / (1000*60*60)) % 100;
        uniqueUsers.add(fakeId);
    });
    const totalUsers = uniqueUsers.size;

    // Visites : nombre d'événements de type 'visit'
    const visits = filteredEvents.filter(e => e.type === 'visit').length;

    // Partages
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
    const newUsers = isNew ? 1 : 0;
    const oldUsers = (firstVisitDate < start) ? 1 : 0;

    // Utilisateurs en ligne : ceux qui ont visité dans les 5 dernières minutes
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000);
    const online = filteredEvents.filter(e => e.type === 'visit' && new Date(e.timestamp) >= fiveMinAgo).length;
    const onlineUsers = online;

    // Hors ligne : totalUsers - onlineUsers
    const offlineUsers = totalUsers - onlineUsers;

    // Moyenne de visites par jour dans la période
    const days = Math.max(1, Math.ceil((end - start) / (1000*60*60*24)));
    const avgVisits = (visits / days).toFixed(1);

    // Mise à jour des éléments
    totalUsersEl.textContent = totalUsers;
    totalVisitsEl.textContent = visits;
    totalSharesEl.textContent = shares;
    newUsersEl.textContent = newUsers;
    oldUsersEl.textContent = oldUsers;
    onlineUsersEl.textContent = onlineUsers;
    offlineUsersEl.textContent = offlineUsers;
    avgVisitsEl.textContent = avgVisits;
}