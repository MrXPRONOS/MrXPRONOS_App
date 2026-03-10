/**
 * pwa.js - Gestion PWA complète
 * Enregistrement du service worker et gestion de l'installation
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        swPath: '/service-worker.js',  // Chemin absolu depuis la racine
        scope: '/'
    };

    // État global
    let deferredPrompt = null;
    let isInstalled = false;

    // Utilitaires
    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => document.querySelectorAll(selector);

    // Détection de la plateforme
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

    // Enregistrement du Service Worker
    async function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            console.log('⚠️ Service Workers non supportés');
            return false;
        }

        try {
            const registration = await navigator.serviceWorker.register(CONFIG.swPath, {
                scope: CONFIG.scope,
                updateViaCache: 'imports'
            });

            console.log('✅ Service Worker enregistré:', registration.scope);

            // Gestion des mises à jour
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                console.log('🔄 Nouvelle version du SW détectée');
                
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // Nouvelle version disponible
                        showUpdateNotification(newWorker);
                    }
                });
            });

            // Écouter les messages du SW
            navigator.serviceWorker.addEventListener('message', (event) => {
                if (event.data.type === 'UPDATE_AVAILABLE') {
                    showUpdateNotification();
                }
            });

            return registration;

        } catch (error) {
            console.error('❌ Erreur enregistrement SW:', error);
            return false;
        }
    }

    // Notification de mise à jour
    function showUpdateNotification(worker) {
        const toast = document.createElement('div');
        toast.className = 'update-toast';
        toast.innerHTML = `
            <div class="update-toast-content">
                <span>🎉 Nouvelle version disponible !</span>
                <button id="update-app" class="btn btn-primary btn-sm">Mettre à jour</button>
            </div>
        `;
        document.body.appendChild(toast);

        $('#update-app')?.addEventListener('click', () => {
            if (worker) {
                worker.postMessage('skipWaiting');
            }
            window.location.reload();
        });

        setTimeout(() => toast.remove(), 10000);
    }

    // Gestion de l'installation
    function initInstallPrompt() {
        const platform = getPlatform();
        const installBtn = $('#install-app');

        if (!installBtn) return;

        // Cacher le bouton par défaut
        installBtn.style.display = 'none';

        // Déjà installé ?
        if (platform.isStandalone) {
            isInstalled = true;
            console.log('✅ App déjà installée');
            return;
        }

        // Écouter l'événement beforeinstallprompt
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('📲 beforeinstallprompt capturé');
            e.preventDefault();
            deferredPrompt = e;
            
            // Afficher le bouton sauf sur iOS (qui n'a pas ce support)
            if (!platform.isIOS) {
                installBtn.style.display = 'inline-flex';
            }
        });

        // Clic sur le bouton installer
        installBtn.addEventListener('click', async () => {
            if (!deferredPrompt) {
                // Fallback pour iOS ou si l'événement n'a pas été déclenché
                if (platform.isIOS) {
                    showIOSInstallGuide();
                } else {
                    showManualInstallInstructions();
                }
                return;
            }

            deferredPrompt.prompt();
            
            const { outcome } = await deferredPrompt.userChoice;
            console.log('📲 Résultat installation:', outcome);
            
            if (outcome === 'accepted') {
                isInstalled = true;
                installBtn.style.display = 'none';
                localStorage.setItem('mx_pwa_installed', 'true');
            }
            
            deferredPrompt = null;
        });

        // App installée
        window.addEventListener('appinstalled', () => {
            console.log('🎉 App installée avec succès');
            isInstalled = true;
            installBtn.style.display = 'none';
            deferredPrompt = null;
            localStorage.setItem('mx_pwa_installed', 'true');
            
            // Notification de succès
            showToast('Application installée avec succès !', 'success');
        });
    }

    // Guide d'installation iOS
    function showIOSInstallGuide() {
        const popup = $('#ios-guide-popup');
        if (popup) {
            popup.style.display = 'flex';
            popup.setAttribute('aria-hidden', 'false');
        }
    }

    // Instructions manuelles d'installation
    function showManualInstallInstructions() {
        const platform = getPlatform();
        let message = 'Pour installer cette application :\n\n';
        
        if (platform.isChrome) {
            message += 'Chrome : Menu (⋮) → "Installer Mr XPRONOS" ou "Ajouter à l\'écran d\'accueil"';
        } else if (platform.isFirefox) {
            message += 'Firefox : Menu (☰) → "Ajouter à l\'écran d\'accueil"';
        } else if (platform.isSafari) {
            message += 'Safari : Partager (⬆) → "Sur l\'écran d\'accueil"';
        } else {
            message += 'Utilisez le menu de votre navigateur pour ajouter à l\'écran d\'accueil';
        }
        
        alert(message);
    }

    // Toast notification
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: ${type === 'success' ? '#4CAF50' : '#2196F3'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            font-weight: 600;
            animation: slideIn 0.3s ease;
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    // Gestion du menu mobile
    function initMobileMenu() {
        const toggle = $('.mobile-menu-toggle');
        const nav = $('#main-nav');
        
        if (!toggle || !nav) return;

        toggle.addEventListener('click', () => {
            const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', !isExpanded);
            nav.classList.toggle('active');
        });

        // Fermer le menu au clic sur un lien
        nav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                nav.classList.remove('active');
                toggle.setAttribute('aria-expanded', 'false');
            });
        });
    }

    // Gestion des modales iOS
    function initIOSGuide() {
        const closeBtn = $('#close-ios-guide');
        const closeBtn2 = $('#close-ios-guide-btn');
        const popup = $('#ios-guide-popup');

        const closeGuide = () => {
            if (popup) {
                popup.style.display = 'none';
                popup.setAttribute('aria-hidden', 'true');
            }
            localStorage.setItem('mx_ios_guide_closed', Date.now().toString());
        };

        closeBtn?.addEventListener('click', closeGuide);
        closeBtn2?.addEventListener('click', closeGuide);

        // Afficher automatiquement si jamais fermé ou +24h
        const lastClosed = localStorage.getItem('mx_ios_guide_closed');
        const platform = getPlatform();
        
        if (platform.isIOS && !platform.isStandalone) {
            if (!lastClosed) {
                setTimeout(showIOSInstallGuide, 3000);
            } else {
                const hoursSince = (Date.now() - parseInt(lastClosed)) / (1000 * 60 * 60);
                if (hoursSince > 24) {
                    setTimeout(showIOSInstallGuide, 3000);
                }
            }
        }
    }

    // Vérifier les permissions de notification
    async function initNotifications() {
        if (!('Notification' in window)) return;
        
        const permission = await Notification.requestPermission();
        console.log('🔔 Permission notifications:', permission);
    }

    // Initialisation
    function init() {
        console.log('🚀 Initialisation PWA...');
        
        // Enregistrer le SW
        registerServiceWorker();
        
        // Initialiser les composants
        initInstallPrompt();
        initMobileMenu();
        initIOSGuide();
        
        // Demander permission notifications (différé)
        if ('Notification' in window && Notification.permission === 'default') {
            setTimeout(initNotifications, 5000);
        }

        console.log('✅ PWA initialisé');
    }

    // Démarrer quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();