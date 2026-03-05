// assets/js/pwa.js - Enregistrement du Service Worker + mise à jour fluide

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // ←←← CHEMIN ABSOLU depuis la racine (obligatoire sur GitHub Pages)
        navigator.serviceWorker.register('/service-worker.js')
            .then(reg => {
                console.log('✅ Service Worker enregistré avec succès ! Scope:', reg.scope);

                // Détection de nouvelle version
                reg.onupdatefound = () => {
                    const installingWorker = reg.installing;
                    if (!installingWorker) return;

                    installingWorker.onstatechange = () => {
                        if (installingWorker.state === 'installed') {
                            if (navigator.serviceWorker.controller) {
                                console.log('📦 Nouvelle version disponible !');

                                // Option 1 : Rechargement automatique silencieux (recommandé)
                                // window.location.reload();

                                // Option 2 : Demander à l'utilisateur (plus sympa)
                                if (confirm('🎉 Une nouvelle version de Mr XPRONOS est disponible !\n\nVoulez-vous recharger maintenant ?')) {
                                    window.location.reload();
                                }
                            }
                        }
                    };
                };
            })
            .catch(err => {
                console.error('❌ Échec enregistrement Service Worker:', err);
            });
    });

    // Rechargement automatique quand le nouveau SW prend le contrôle
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
            refreshing = true;
            console.log('🔄 Nouveau Service Worker activé → rechargement automatique');
            window.location.reload();
        }
    });
}