/**
 * pwa.js - Gestion PWA complète et corrigée
 */

(function () {
    'use strict';

    // ========================================================
    // CONFIGURATION
    // ========================================================
    const CONFIG = (() => {
        const isGitHubPages = location.hostname.includes('github.io');
        const path = location.pathname;
        
        let base = '/';
        
        if (isGitHubPages) {
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
    // SIMPLE LOGGER (sans dépendance)
    // ========================================================
    const isDev = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    
    // Pas de fonction log complexe, on utilise console directement
    function pwaLog(msg) {
        if (isDev) console.log('[PWA]', msg);
    }
    
    function pwaWarn(msg) {
        if (isDev) console.warn('[PWA]', msg);
    }
    
    function pwaError(msg) {
        console.error('[PWA]', msg);
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
        `;
        
        toast.onclick = () => window.location.reload();
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
        `;
        
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
    }

    // ========================================================
    // SERVICE WORKER
    // ========================================================
    async function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            pwaWarn('Service Worker non supporté');
            return null;
        }

        try {
            pwaLog('Enregistrement SW: ' + CONFIG.swPath);
            
            const registration = await navigator.serviceWorker.register(CONFIG.swPath, {
                scope: CONFIG.scope,
                updateViaCache: 'imports'
            });

            pwaLog('SW enregistré: ' + registration.scope);
            updateGlobalState({ registration });

            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                if (!newWorker) return;
                pwaLog('Nouvelle version SW détectée');

                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        pwaLog('Mise à jour disponible');
                        updateGlobalState({ updateAvailable: true });
                        showUpdateToast();
                    }
                });
            });

            return registration;
        } catch (err) {
            pwaError('Erreur SW: ' + err.message);
            return null;
        }
    }

    // ========================================================
    // GESTION DE L'INSTALLATION
    // ========================================================
    function setupInstallPromptHandling() {
        const platform = getPlatform();
        updateGlobalState({ platform });

        if (platform.isStandalone) {
            pwaLog('App déjà installée');
            updateGlobalState({ isInstalled: true, installAvailable: false });
            return;
        }

        if (platform.isIOS) {
            pwaLog('iOS - installation via menu partage');
            updateGlobalState({ installAvailable: false });
            return;
        }

        window.addEventListener('beforeinstallprompt', (e) => {
            pwaLog('beforeinstallprompt capturé');
            e.preventDefault();
            
            updateGlobalState({
                deferredPrompt: e,
                installAvailable: true
            });
        });

        window.addEventListener('appinstalled', () => {
            pwaLog('App installée avec succès');
            updateGlobalState({
                deferredPrompt: null,
                isInstalled: true,
                installAvailable: false
            });
            localStorage.setItem('mx_pwa_installed', 'true');
            showInstallSuccessToast();
        });

        setTimeout(() => {
            if (!window.__MRXPWA__.installAvailable && !platform.isStandalone && !platform.isIOS) {
                pwaLog('Aucune installation disponible');
                updateGlobalState({ installAvailable: false });
            }
        }, 5000);
    }

    async function promptInstall() {
        const state = window.__MRXPWA__;
        const platform = getPlatform();
        
        if (platform.isIOS) {
            const guidePopup = document.getElementById('ios-guide-popup');
            if (guidePopup) {
                guidePopup.style.display = 'flex';
            } else {
                alert('Pour installer sur iPhone :\n1. Touchez "Partager"\n2. "Sur l\'écran d\'accueil"\n3. "Ajouter"');
            }
            return false;
        }
        
        if (!state.deferredPrompt) {
            pwaWarn('Aucune installation disponible');
            return false;
        }

        try {
            state.deferredPrompt.prompt();
            const result = await state.deferredPrompt.userChoice;
            pwaLog('Résultat installation: ' + result?.outcome);

            updateGlobalState({
                deferredPrompt: null,
                installAvailable: false
            });

            return result?.outcome === 'accepted';
        } catch (err) {
            pwaError('Erreur install: ' + err.message);
            return false;
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
    function init() {
        pwaLog('Initialisation PWA...');
        pwaLog('Config: ' + JSON.stringify(CONFIG));
        
        addStyles();
        updateGlobalState({ platform: getPlatform() });
        
        registerServiceWorker();
        setupInstallPromptHandling();
        
        setInterval(() => {
            if (document.visibilityState === 'visible') {
                window.__MRXPWA__?.registration?.update().catch(() => {});
            }
        }, 3600000);
        
        pwaLog('PWA initialisé');
    }

    // ========================================================
    // API PUBLIQUE
    // ========================================================
    window.MrXPWA = {
        getState: () => window.__MRXPWA__,
        getPlatform: getPlatform,
        promptInstall: promptInstall,
        isInstallable: () => window.__MRXPWA__.installAvailable,
        isInstalled: () => getPlatform().isStandalone
    };
    
    window.promptPWAInstall = promptInstall;

    // Démarrer
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();