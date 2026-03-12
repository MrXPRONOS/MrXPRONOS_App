// assets/js/menu.js
// Menu horizontal avec icônes, bordures haute et basse, sur une seule ligne
(function() {
    'use strict';

    const menuItems = [
        { name: 'Accueil', icon: '🏠', url: 'index.html' },
        { name: 'Pronostics', icon: '📊', url: 'pronos.html' },
        { name: 'LIVE VIP', icon: '🔴', url: 'live.html' },
        { name: 'Historique', icon: '📜', url: 'historique.html' },
        { name: 'Bonus', icon: '🎁', url: 'bonus.html' },
        { name: 'Blog', icon: '📝', url: 'blog.html' },
        { name: 'Conseils', icon: '💡', url: 'conseils.html' },
        { name: 'Contact', icon: '📞', url: 'contact.html' }
    ];

    function createMenu() {
        const header = document.querySelector('header .container');
        if (!header) return;

        // Supprimer l'ancien menu s'il existe
        const oldNav = header.querySelector('nav');
        if (oldNav) oldNav.remove();

        // Créer le nouveau menu
        const nav = document.createElement('nav');
        nav.className = 'icon-nav';

        const ul = document.createElement('ul');
        ul.className = 'icon-nav-list';

        menuItems.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = item.url;
            a.innerHTML = `<span class="nav-icon">${item.icon}</span><span class="nav-label">${item.name}</span>`;

            // Marquer le lien actif
            const currentPath = window.location.pathname;
            if (currentPath.endsWith(item.url) || 
                (item.url === 'index.html' && (currentPath === '/' || currentPath.endsWith('/')))) {
                a.classList.add('active');
            }
            li.appendChild(a);
            ul.appendChild(li);
        });
        nav.appendChild(ul);

        // Insérer le nav après le logo
        const logo = header.querySelector('.logo');
        if (logo) {
            logo.insertAdjacentElement('afterend', nav);
        } else {
            header.appendChild(nav);
        }

        // Ajouter les styles
        addStyles();
    }

    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Styles du menu à icônes */
            .icon-nav {
                flex: 1;
                display: flex;
                justify-content: center;
                margin: 0 10px;
                border-top: 2px solid #D4AF37;
                border-bottom: 2px solid #D4AF37;
                padding: 5px 0;
                overflow-x: auto;
                white-space: nowrap;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: thin;
                scrollbar-color: #D4AF37 #0D0D0D;
            }
            .icon-nav::-webkit-scrollbar {
                height: 4px;
            }
            .icon-nav::-webkit-scrollbar-thumb {
                background: #D4AF37;
                border-radius: 4px;
            }
            .icon-nav-list {
                display: flex;
                list-style: none;
                margin: 0;
                padding: 0;
                gap: 1.2rem;
                flex-wrap: nowrap;
            }
            .icon-nav-list li {
                display: inline-block;
            }
            .icon-nav-list a {
                display: flex;
                flex-direction: column;
                align-items: center;
                color: #fff;
                text-decoration: none;
                font-size: 0.75rem;
                transition: color 0.3s;
                padding: 5px;
                border-radius: 8px;
                white-space: nowrap;
            }
            .icon-nav-list .nav-icon {
                font-size: 1.3rem;
                margin-bottom: 2px;
            }
            .icon-nav-list .nav-label {
                font-size: 0.65rem;
                font-weight: 500;
            }
            .icon-nav-list a:hover,
            .icon-nav-list a.active {
                color: #D4AF37;
                background: rgba(212, 175, 55, 0.1);
            }
            /* Ajustement du header pour contenir le menu */
            header .container {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: nowrap;
            }
            .logo {
                flex-shrink: 0;
            }
            .promo-code {
                flex-shrink: 0;
                white-space: nowrap;
                margin-left: 10px;
            }
            /* Sur les petits écrans, on réduit l'espacement */
            @media (max-width: 1000px) {
                .icon-nav-list {
                    gap: 0.8rem;
                }
                .icon-nav-list .nav-icon {
                    font-size: 1.1rem;
                }
                .icon-nav-list .nav-label {
                    font-size: 0.6rem;
                }
            }
            @media (max-width: 800px) {
                .icon-nav-list {
                    gap: 0.5rem;
                }
                .icon-nav-list a {
                    padding: 3px;
                }
            }
        `;
        document.head.appendChild(style);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createMenu);
    } else {
        createMenu();
    }
})();