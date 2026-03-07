/**
 * vip.js - Gestion de l'accès VIP payant pour Mr XPRONOS
 * Utilise Supabase pour vérifier les codes et gérer les abonnements
 * 
 * Fonctions exportées :
 * - getUserId() : retourne l'ID unique de l'utilisateur (créé si nécessaire)
 * - checkVipStatus() : vérifie si l'utilisateur a un code VIP valide (basé sur localStorage)
 * - showVipLoginForm(container) : affiche le formulaire de connexion VIP dans le conteneur donné
 */

// =======================================================
// IMPORT SUPABASE (utilisation du CDN)
// =======================================================
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Configuration Supabase - À MODIFIER avec vos vraies clés
// Idéalement, ces valeurs devraient être importées depuis config.js
const supabaseUrl = 'https://votre-projet.supabase.co';
const supabaseAnonKey = 'votre-clé-anon';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// =======================================================
// FONCTIONS UTILITAIRES
// =======================================================

/**
 * Retourne l'ID unique de l'utilisateur stocké dans localStorage.
 * Si inexistant, en génère un nouveau.
 * @returns {string} ID utilisateur (format MX-XXXXXXXX)
 */
export function getUserId() {
    let userId = localStorage.getItem('mx_user_id');
    if (!userId) {
        userId = 'MX-' + Math.random().toString(36).substring(2, 10).toUpperCase();
        localStorage.setItem('mx_user_id', userId);
    }
    return userId;
}

/**
 * Récupère l'adresse IP publique du client (via api.ipify.org).
 * Utilisé pour lier le code à une IP (optionnel mais recommandé).
 * @returns {Promise<string>} Adresse IP ou chaîne vide
 */
async function getClientIp() {
    try {
        const resp = await fetch('https://api.ipify.org?format=json');
        const data = await resp.json();
        return data.ip;
    } catch (e) {
        console.warn('Impossible de récupérer IP', e);
        return '';
    }
}

// =======================================================
// VÉRIFICATION DU STATUT VIP
// =======================================================

/**
 * Vérifie si le code VIP stocké dans localStorage est toujours valide.
 * Interroge Supabase et compare avec l'ID utilisateur et l'IP.
 * @returns {Promise<boolean>} true si le code est valide et non expiré, false sinon
 */
export async function checkVipStatus() {
    const userId = getUserId();
    const storedCode = localStorage.getItem('mx_vip_code');
    if (!storedCode) return false;

    try {
        const { data, error } = await supabase
            .from('vip_users')
            .select('expires_at, is_active, ip_address')
            .eq('user_id', userId)
            .eq('vip_code', storedCode)
            .single();

        if (error || !data) return false;

        // Vérification IP (optionnelle) : si une IP est enregistrée, elle doit correspondre
        if (data.ip_address) {
            const currentIp = await getClientIp();
            if (data.ip_address !== currentIp) {
                console.warn('IP mismatch, accès refusé');
                return false;
            }
        }

        const now = new Date();
        const expires = new Date(data.expires_at);
        return data.is_active && expires > now;
    } catch (e) {
        console.error('Erreur vérification VIP:', e);
        return false;
    }
}

// =======================================================
// AFFICHAGE DU FORMULAIRE DE CONNEXION VIP
// =======================================================

/**
 * Affiche le formulaire de connexion VIP dans le conteneur donné.
 * Le formulaire montre l'ID utilisateur, des liens de contact,
 * un champ pour entrer le code, et un bouton d'activation.
 * @param {HTMLElement} container - Élément DOM où insérer le formulaire
 */
export function showVipLoginForm(container) {
    const userId = getUserId();

    // On vide le conteneur et on y place le formulaire
    container.innerHTML = `
        <div class="vip-locked-content" style="display:block;">
            <div class="lock-icon">💎</div>
            <h3>🔐 Accès VIP Payant</h3>
            <p><strong>Votre ID :</strong> ${userId}</p>
            <p>Pour obtenir un code VIP (5000 FCFA/mois), contactez-nous sur WhatsApp ou Telegram avec votre ID.</p>
            <div style="display: flex; gap: 10px; justify-content: center; margin: 20px 0;">
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

    // Gestionnaire d'activation
    document.getElementById('vip-activate-btn').addEventListener('click', async () => {
        const code = document.getElementById('vip-code-input').value.trim();
        if (!code) {
            alert('Veuillez entrer un code.');
            return;
        }

        const userId = getUserId();
        const ip = await getClientIp(); // facultatif

        const { data, error } = await supabase
            .from('vip_users')
            .select('expires_at, is_active')
            .eq('user_id', userId)
            .eq('vip_code', code)
            .single();

        if (error || !data) {
            alert('Code invalide ou expiré.');
            return;
        }

        const now = new Date();
        const expires = new Date(data.expires_at);
        if (!data.is_active || expires <= now) {
            alert('Code expiré ou désactivé.');
            return;
        }

        // Tout est bon : on stocke le code et on recharge
        localStorage.setItem('mx_vip_code', code);
        window.location.reload();
    });

    // Gestionnaire de fermeture (masque le conteneur)
    document.getElementById('vip-close-btn').addEventListener('click', () => {
        container.style.display = 'none';
        // On pourrait aussi remettre l'affichage des matchs si nécessaire
        const matchesContainer = document.getElementById('matches-container');
        if (matchesContainer) matchesContainer.style.display = 'grid';
    });
}

// =======================================================
// FONCTION DE DÉCONNEXION VIP (optionnelle)
// =======================================================

/**
 * Supprime le code VIP du localStorage, forçant une nouvelle connexion.
 */
export function logoutVip() {
    localStorage.removeItem('mx_vip_code');
    window.location.reload();
}