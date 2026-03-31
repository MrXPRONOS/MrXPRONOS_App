/**
 * pwa.js - Gestion PWA complète et corrigée
 * Rôles :
 * - enregistrer le Service Worker
 * - gérer beforeinstallprompt
 * - exposer l'état PWA global
 * - gérer les mises à jour du SW
 * - afficher/cacher le bouton d'installation
 */

(function () {
    'use strict';

    // Configuration des chemins
    const CONFIG = (() => {
        const isGitHubPages = location.hostname.includes('github.io');
        const path = location.pathname;
        
        // Détection automatique du chemin de base
        let base = '/';
        
        if (isGitHubPages) {
            // Pour GitHub Pages, on extrait le nom du repo
            const match = path.match(/^\/([^/]+)\//);
            if (match) {
                base = `/${match[1]}/`;
            }
        } else if (path.includes('/MrXPRONOS_App/')) {
            base = '/MrXPRONOS_App/';
        }
        
        return {
            swPath: `${base}service-worker.js`,
            scope: base,
            isGitHubPages
        };
    })();

    // ========================================================
    // FONCTIONS DE LOG - DÉFINIES AVANT TOUTE UTILISATION
    // ========================================================
    const isDev = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    
    function log(...args) {
        if (isDev) console.log('[PWA]', ...args);
    }
    
    function warn(...args) {
        if (isDev) console.warn('[PWA]', ...args);
    }
    
    function error(...args) {
        console.error('[PWA]', ...args);
    }

    // ========================================================
    // ÉTAT GLOBAL
    // ========================================================
    window.__MRXPWA__ = {
        registration: null,
        deferredPrompt: null,
        isInstalled: false,
        installAvailable: false,
        updateAvailable: false,
        platform: null
    };

    // ========================================================
    // FONCTIONS UTILITAIRES
    // ========================================================
    function getPlatform() {
        const ua = navigator.userAgent.toLowerCase();
        const platform = navigator.platform?.toLowerCase() || '';

        return {
            isIOS: /iphone|ipad|ipod/.test(ua) || (platform === 'macintel' && navigator.maxTouchPoints > 1),
            isAndroid: /android/.test(ua),
            isStandalone: window.matchMedia('(display-mode: standalone)').matches ||
                window.navigator.standalone === true ||
                localStorage.getItem('mx_pwa_installed') === 'true',
            isSafari: /^((?!chrome|android).)*safari/i.test(ua),
            isChrome: /chrome/.test(ua) && !/edge|edg/.test(ua),
            isFirefox: /firefox/.test(ua),
            isMobile: /mobile|android|iphone|ipad|ipod/i.test(ua)
        };
    }

    function updateGlobalState(partial) {
        Object.assign(window.__MRXPWA__, partial);
        window.dispatchEvent(new CustomEvent('mrx-pwa-state-change', {
            detail: window.__MRXPWA__
        }));
        
        // Mise à jour du bouton d'installation
        updateInstallButton();
    }

    function updateInstallButton() {
        const installBtn = document.getElementById('install-app');
        if (!installBtn) return;
        
        const platform = getPlatform();
        const shouldShow = !platform.isStandalone && window.__MRXPWA__.installAvailable;
        
        installBtn.style.display = shouldShow ? 'inline-flex' : 'none';
        
        if (shouldShow) {
            installBtn.classList.add('btn-primary');
            installBtn.classList.remove('btn-secondary');
            installBtn.innerHTML = '<i class="fas fa-download"></i> Installer l\'app';
        }
    }

    function showUpdateToast() {
        // Ne pas afficher si déjà affiché récemment
        const lastToast = localStorage.getItem('mx_update_toast');
        if (lastToast && Date.now() - parseInt(lastToast) < 3600000) return;
        
        localStorage.setItem('mx_update_toast', Date.now().toString());
        
        const toast = document.createElement('div');
        toast.textContent = '🔄 Nouvelle version disponible. Rafraîchissez la page.';
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            right: 20px;
            background: #D4AF37;
            color: #000;
            padding: 12px 16px;
            border-radius: 12px;
            font-weight: 600;
            text-align: center;
            z-index: 10001;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: slideUp 0.3s ease;
        `;
        
        toast.onclick = () => {
            window.location.reload();
        };
        
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 8000);
    }

    function showInstallSuccessToast() {
        const toast = document.createElement('div');
        toast.textContent = '✅ Mr XPRONOS installé sur votre appareil !';
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 12px 16px;
            border-radius: 12px;
            font-weight: 600;
            text-align: center;
            z-index: 10001;
            animation: slideUp 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
    }

    // ========================================================
    // SERVICE WORKER
    // ========================================================
    async function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            warn('⚠️ Service Worker non supporté');
            return null;
        }

        try {
            log('📦 Enregistrement SW avec chemin:', CONFIG.swPath);
            log('📦 Scope:', CONFIG.scope);
            
            const registration = await navigator.serviceWorker.register(CONFIG.swPath, {
                scope: CONFIG.scope,
                updateViaCache: 'imports'
            });

            log('✅ Service Worker enregistré:', registration.scope);
            updateGlobalState({ registration });

            // Vérifier si le SW est actif
            if (registration.active) {
                log('✅ SW actif');
            } else if (registration.installing) {
                log('⏳ SW en cours d\'installation');
            } else if (registration.waiting) {
                log('⏳ SW en attente');
                updateGlobalState({ updateAvailable: true });
            }

            // Détection de mise à jour
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                if (!newWorker) return;

                log('🔄 Nouvelle version du SW détectée');

                newWorker.addEventListener('statechange', () => {
                    log('🔄 État du nouveau SW:', newWorker.state);
                    
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        log('✅ Nouvelle version installée, mise à jour disponible');
                        updateGlobalState({ updateAvailable: true });
                        showUpdateToast();
                    }
                });
            });

            // Gestion des messages du SW
            navigator.serviceWorker.addEventListener('message', (event) => {
                log('📨 Message du SW:', event.data);
                
                if (event.data?.type === 'UPDATE_AVAILABLE') {
                    updateGlobalState({ updateAvailable: true });
                    showUpdateToast();
                }
            });

            return registration;
        } catch (err) {
            error('❌ Erreur enregistrement Service Worker:', err);
            return null;
        }
    }

    // ========================================================
    // GESTION DE L'INSTALLATION
    // ========================================================
    function setupInstallPromptHandling() {
        const platform = getPlatform();
        updateGlobalState({ platform });

        // Vérifier si déjà installée
        if (platform.isStandalone) {
            log('✅ App déjà installée');
            updateGlobalState({ isInstalled: true, installAvailable: false });
            return;
        }

        // Pour iOS, pas de beforeinstallprompt
        if (platform.isIOS) {
            log('📱 iOS détecté - installation via menu partage');
            updateGlobalState({ installAvailable: false });
            return;
        }

        // Écouter beforeinstallprompt (Android/Chrome)
        window.addEventListener('beforeinstallprompt', (e) => {
            log('📲 beforeinstallprompt capturé');
            e.preventDefault();
            
            updateGlobalState({
                deferredPrompt: e,
                installAvailable: true
            });

            window.dispatchEvent(new CustomEvent('mrx-beforeinstallprompt', {
                detail: window.__MRXPWA__
            }));
        });

        // Écouter l'installation réussie
        window.addEventListener('appinstalled', () => {
            log('🎉 App installée avec succès');
            updateGlobalState({
                deferredPrompt: null,
                isInstalled: true,
                installAvailable: false
            });

            try {
                localStorage.setItem('mx_pwa_installed', 'true');
            } catch (_) {}

            showInstallSuccessToast();
        });

        // Fallback : si pas de beforeinstallprompt après 5s, désactiver le bouton
        setTimeout(() => {
            if (!window.__MRXPWA__.installAvailable && !platform.isStandalone && !platform.isIOS) {
                log('⏰ Aucun beforeinstallprompt reçu, installation non disponible');
                updateGlobalState({ installAvailable: false });
            }
        }, 5000);
    }

    async function promptInstall() {
        const state = window.__MRXPWA__;
        const platform = getPlatform();
        
        // iOS : ouvrir le guide
        if (platform.isIOS) {
            log('📱 iOS - affichage du guide d\'installation');
            const guidePopup = document.getElementById('ios-guide-popup');
            if (guidePopup) {
                guidePopup.style.display = 'flex';
            } else {
                alert('Pour installer l\'application sur iPhone :\n1. Touchez "Partager"\n2. "Sur l\'écran d\'accueil"\n3. "Ajouter"');
            }
            return false;
        }
        
        // Android/Chrome
        if (!state.deferredPrompt) {
            warn('⚠️ Aucune installation disponible');
            return false;
        }

        try {
            log('📲 Déclenchement de l\'installation...');
            state.deferredPrompt.prompt();
            const result = await state.deferredPrompt.userChoice;

            log('📲 Résultat installation:', result?.outcome);

            updateGlobalState({
                deferredPrompt: null,
                installAvailable: false
            });

            return result?.outcome === 'accepted';
        } catch (err) {
            error('❌ Erreur prompt install:', err);
            return false;
        }
    }

    // ========================================================
    // GESTION DES MISES À JOUR
    // ========================================================
    async function checkForUpdates() {
        const registration = window.__MRXPWA__?.registration;
        if (!registration) return false;

        try {
            log('🔍 Recherche de mises à jour...');
            await registration.update();
            return true;
        } catch (err) {
            warn('⚠️ Impossible de vérifier les mises à jour:', err);
            return false;
        }
    }

    function skipWaitingAndReload() {
        const registration = window.__MRXPWA__?.registration;
        
        if (registration?.waiting) {
            log('🔄 Activation de la nouvelle version...');
            registration.waiting.postMessage('skipWaiting');
            
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                log('🔄 SW changé, rechargement...');
                window.location.reload();
            }, { once: true });
        } else {
            window.location.reload();
        }
    }

    // ========================================================
    // STYLES
    // ========================================================
    function addStyles() {
        if (document.getElementById('pwa-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'pwa-styles';
        style.textContent = `
            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            #install-app {
                transition: all 0.3s ease;
            }
            
            #install-app:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(212, 175, 55, 0.4);
            }
        `;
        document.head.appendChild(style);
    }

    // ========================================================
    // INITIALISATION
    // ========================================================
    async function init() {
        log('🚀 Initialisation PWA...');
        log('📦 Configuration:', CONFIG);
        
        addStyles();
        
        // Mettre à jour le platform dans l'état global
        updateGlobalState({ platform: getPlatform() });
        
        // Enregistrer le Service Worker
        await registerServiceWorker();
        
        // Configurer la gestion de l'installation
        setupInstallPromptHandling();
        
        // Vérifier périodiquement les mises à jour (toutes les heures)
        setInterval(() => {
            if (document.visibilityState === 'visible') {
                checkForUpdates();
            }
        }, 3600000);
        
        log('✅ PWA initialisé');
    }

    // ========================================================
    // API PUBLIQUE
    // ========================================================
    window.MrXPWA = {
        getState: () => window.__MRXPWA__,
        getPlatform: getPlatform,
        promptInstall: promptInstall,
        checkForUpdates: checkForUpdates,
        skipWaitingAndReload: skipWaitingAndReload,
        isInstallable: () => window.__MRXPWA__.installAvailable,
        isInstalled: () => getPlatform().isStandalone
    };
    
    // Exporter la fonction promptInstall globalement pour main.js
    window.promptPWAInstall = promptInstall;

    // Démarrer au chargement
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();