/**
 * pwa.js - Gestion PWA simplifiée et compatible avec main.js
 * Rôles :
 * - enregistrer le Service Worker
 * - gérer beforeinstallprompt
 * - exposer l'état PWA global
 * - gérer les mises à jour du SW
 *
 * Le reste (UI, bouton installer, popup iOS) est géré par main.js
 */

(function () {
    'use strict';

    const CONFIG = {
        swPath: '/service-worker.js',
        scope: '/'
    };

    const IS_DEV =
        location.hostname === 'localhost' ||
        location.hostname.includes('127.0.0.1');

    const log = IS_DEV ? console.log.bind(console) : () => {};
    const warn = IS_DEV ? console.warn.bind(console) : () => {};

    if (!window.__MRXPWA__) {
        window.__MRXPWA__ = {
            deferredPrompt: null,
            registration: null,
            isInstalled: false,
            installAvailable: false,
            updateAvailable: false
        };
    }

    function getPlatform() {
        const ua = navigator.userAgent.toLowerCase();
        const platform = navigator.platform.toLowerCase();

        return {
            isIOS: /iphone|ipad|ipod/.test(ua) || (platform === 'macintel' && navigator.maxTouchPoints > 1),
            isAndroid: /android/.test(ua),
            isStandalone: window.matchMedia('(display-mode: standalone)').matches ||
                window.navigator.standalone === true,
            isSafari: /^((?!chrome|android).)*safari/i.test(ua),
            isChrome: /chrome/.test(ua) && !/edge|edg/.test(ua),
            isFirefox: /firefox/.test(ua)
        };
    }

    function updateGlobalState(partial) {
        Object.assign(window.__MRXPWA__, partial);
        window.dispatchEvent(new CustomEvent('mrx-pwa-state-change', {
            detail: window.__MRXPWA__
        }));
    }

    async function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            warn('⚠️ Service Worker non supporté');
            return null;
        }

        try {
            const registration = await navigator.serviceWorker.register(CONFIG.swPath, {
                scope: CONFIG.scope,
                updateViaCache: 'imports'
            });

            log('✅ Service Worker enregistré:', registration.scope);
            updateGlobalState({ registration });

            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                if (!newWorker) return;

                log('🔄 Nouvelle version du SW détectée');

                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        updateGlobalState({ updateAvailable: true });
                        window.dispatchEvent(new CustomEvent('mrx-pwa-update-available', {
                            detail: { worker: newWorker }
                        }));
                    }
                });
            });

            navigator.serviceWorker.addEventListener('message', (event) => {
                if (event.data?.type === 'UPDATE_AVAILABLE') {
                    updateGlobalState({ updateAvailable: true });
                    window.dispatchEvent(new CustomEvent('mrx-pwa-update-available', {
                        detail: { worker: null }
                    }));
                }
            });

            return registration;
        } catch (error) {
            console.error('❌ Erreur enregistrement Service Worker:', error);
            return null;
        }
    }

    function setupInstallPromptHandling() {
        const platform = getPlatform();

        updateGlobalState({
            isInstalled: platform.isStandalone,
            installAvailable: false
        });

        if (platform.isStandalone) {
            log('✅ App déjà installée');
            return;
        }

        window.addEventListener('beforeinstallprompt', (e) => {
            log('📲 beforeinstallprompt capturé');
            e.preventDefault();

            updateGlobalState({
                deferredPrompt: e,
                installAvailable: !platform.isIOS
            });

            window.dispatchEvent(new CustomEvent('mrx-beforeinstallprompt', {
                detail: window.__MRXPWA__
            }));
        });

        window.addEventListener('appinstalled', () => {
            log('🎉 App installée');
            updateGlobalState({
                deferredPrompt: null,
                isInstalled: true,
                installAvailable: false
            });

            try {
                localStorage.setItem('mx_pwa_installed', 'true');
            } catch (_) {}
        });
    }

    async function promptInstall() {
        const state = window.__MRXPWA__;
        if (!state.deferredPrompt) return false;

        try {
            state.deferredPrompt.prompt();
            const result = await state.deferredPrompt.userChoice;

            log('📲 Résultat installation:', result?.outcome);

            updateGlobalState({
                deferredPrompt: null,
                installAvailable: false
            });

            return result?.outcome === 'accepted';
        } catch (error) {
            console.error('❌ Erreur prompt install:', error);
            return false;
        }
    }

    async function checkForUpdates() {
        const registration = window.__MRXPWA__?.registration;
        if (!registration) return false;

        try {
            await registration.update();
            return true;
        } catch (error) {
            warn('⚠️ Impossible de vérifier les mises à jour SW:', error);
            return false;
        }
    }

    function skipWaitingAndReload() {
        const registration = window.__MRXPWA__?.registration;
        if (!registration?.waiting) {
            window.location.reload();
            return;
        }

        registration.waiting.postMessage('skipWaiting');

        navigator.serviceWorker.addEventListener('controllerchange', () => {
            window.location.reload();
        }, { once: true });
    }

    async function init() {
        log('🚀 Initialisation PWA...');
        await registerServiceWorker();
        setupInstallPromptHandling();
        log('✅ PWA prêt');
    }

    // API publique légère
    window.MrXPWA = {
        getState() {
            return window.__MRXPWA__;
        },
        getPlatform,
        promptInstall,
        checkForUpdates,
        skipWaitingAndReload
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();