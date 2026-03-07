// vip.js – Point d'entrée pour la compatibilité avec les appels existants
export async function checkVipStatus() {
    return window.checkVipStatus ? window.checkVipStatus() : false;
}

export function getUserId() {
    return window.getUserId ? window.getUserId() : '';
}

export function showVipLoginForm(container) {
    if (window.showVipLoginForm) window.showVipLoginForm(container);
}