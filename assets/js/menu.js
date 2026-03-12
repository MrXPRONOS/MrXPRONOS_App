// assets/js/menu.js - Barre de navigation inférieure pour mobile
(function() {
    'use strict';

    // Configuration des éléments de navigation
    const navItems = [
        { name: 'Accueil', icon: '🏠', url: 'index.html' },
        { name: 'Pronostics', icon: '📊', url: 'pronos.html' },
        { name: 'LIVE VIP', icon: '🔴', url: 'live.html' },
        { name: 'Historique', icon: '📜', url: 'historique.html' },
        { name: 'Bonus', icon: '🎁', url: 'bonus.html' }
    ];

    // Créer la barre de navigation
    function createBottomNav() {
        const nav = document.createElement('nav');
        nav.className = 'mobile-bottom-nav';
        nav.setAttribute('aria-label', 'Navigation principale');

        const ul = document.createElement('ul');
        navItems.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = item.url;
            a.innerHTML = `<span class="nav-icon">${item.icon}</span><span class="nav-label">${item.name}</span>`;

            // Vérifier si l'URL correspond à la page courante
            const currentPath = window.location.pathname;
            if (currentPath.endsWith(item.url) || 
                (item.url === 'index.html' && (currentPath === '/' || currentPath.endsWith('/')))) {
                a.classList.add('active');
            }
            li.appendChild(a);
            ul.appendChild(li);
        });
        nav.appendChild(ul);
        return nav;
    }

    // Initialisation
    function init() {
        const nav = createBottomNav();
        document.body.appendChild(nav);

        // Ajouter un padding-bottom au body pour éviter que le contenu soit caché
        document.body.style.paddingBottom = '70px';

        // Styles de la barre (intégrés ici pour éviter un fichier CSS supplémentaire)
        const style = document.createElement('style');
        style.textContent = `
            .mobile-bottom-nav {
                position: fixed;
                bottom: 0;
                left: 0;
                width: 100%;
                background: #0D0D0D;
                border-top: 2px solid #D4AF37;
                box-shadow: 0 -2px 10px rgba(0,0,0,0.5);
                z-index: 1000;
                font-family: 'Montserrat', sans-serif;
            }
            .mobile-bottom-nav ul {
                display: flex;
                justify-content: space-around;
                align-items: center;
                list-style: none;
                margin: 0;
                padding: 8px 0;
            }
            .mobile-bottom-nav li {
                flex: 1;
                text-align: center;
            }
            .mobile-bottom-nav a {
                display: flex;
                flex-direction: column;
                align-items: center;
                color: #888;
                text-decoration: none;
                font-size: 0.7rem;
                transition: color 0.3s;
            }
            .mobile-bottom-nav a.active {
                color: #D4AF37;
            }
            .mobile-bottom-nav .nav-icon {
                font-size: 1.5rem;
                margin-bottom: 2px;
            }
            .mobile-bottom-nav .nav-label {
                font-size: 0.6rem;
            }
            @media (min-width: 769px) {
                .mobile-bottom-nav {
                    display: none;
                }
                body {
                    padding-bottom: 0 !important;
                }
            }
        `;
        document.head.appendChild(style);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();