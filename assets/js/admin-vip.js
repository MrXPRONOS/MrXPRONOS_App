/**
 * admin-vip.js - Panneau d'administration des codes VIP
 */

import { supabase } from './supabase-client.js';

// Authentification admin simple (à améliorer)
const ADMIN_PASSWORD = 'admin123'; // À changer ou à récupérer depuis un secret

async function authAdmin() {
    const pwd = prompt('Mot de passe admin :');
    if (pwd !== ADMIN_PASSWORD) {
        alert('Accès refusé');
        throw new Error('Unauthorized');
    }
}

// Génération d'un code unique
function generateVipCode() {
    return 'VIP-' + Math.random().toString(36).substring(2, 10).toUpperCase() +
           '-' + Math.random().toString(36).substring(2, 6).toUpperCase();
}

// Créer un nouvel accès VIP
async function createVipAccess(userId, ip, durationDays) {
    await authAdmin();

    const code = generateVipCode();
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + durationDays);

    const { error } = await supabase
        .from('vip_users')
        .insert({
            user_id: userId,
            vip_code: code,
            ip_address: ip || '',
            expires_at: expiresAt.toISOString(),
            is_active: true
        });

    if (error) throw error;
    return code;
}

// Charger la liste des VIP actifs
async function loadActiveVips() {
    const { data, error } = await supabase
        .from('vip_users')
        .select('*')
        .eq('is_active', true)
        .order('expires_at', { ascending: true });

    if (error) throw error;
    return data;
}

// Désactiver un VIP
async function deactivateVip(code) {
    await supabase
        .from('vip_users')
        .update({ is_active: false })
        .eq('vip_code', code);
}

// Récupérer l'IP d'un utilisateur (via son ID) – optionnel
async function getUserIp(userId) {
    // À implémenter si vous stockez les IP dans une table de logs
    return '';
}

// Interface DOM
document.addEventListener('DOMContentLoaded', async () => {
    const form = document.getElementById('vip-form');
    const listDiv = document.getElementById('vip-list');

    if (!form) return;

    // Charger la liste au démarrage
    try {
        const vips = await loadActiveVips();
        listDiv.innerHTML = vips.map(v => `
            <div class="vip-item">
                <span>${v.user_id}</span> - Code: ${v.vip_code} - Expire: ${new Date(v.expires_at).toLocaleDateString()}
                <button class="btn-deactivate" data-code="${v.vip_code}">Désactiver</button>
            </div>
        `).join('');

        document.querySelectorAll('.btn-deactivate').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const code = e.target.dataset.code;
                await deactivateVip(code);
                window.location.reload();
            });
        });
    } catch (e) {
        listDiv.innerHTML = '<p class="error">Erreur de chargement</p>';
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userId = document.getElementById('user-id').value.trim();
        const ip = document.getElementById('ip-address').value.trim();
        const duration = parseInt(document.getElementById('duration').value);

        try {
            const code = await createVipAccess(userId, ip, duration);
            document.getElementById('result').innerHTML = `<p>Code généré : <strong>${code}</strong></p>`;
            window.location.reload(); // recharge la liste
        } catch (err) {
            alert('Erreur : ' + err.message);
        }
    });
});