// assets/js/menu.js
// Menu horizontal avec icônes Font Awesome, bordures haute et basse, sur une seule ligne
// Placé en dessous du logo et du code promo
(function() {
    'use strict';

    const menuItems = [
        { name: 'Accueil', icon: 'fa-home', url: 'index.html' },
        { name: 'Coupons', icon: 'fa-chart-line', url: 'pronos.html' },
        { name: 'LIVE VIP', icon: 'fa-bolt', url: 'live.html' },
        { name: 'Histo', icon: 'fa-clock-rotate-left', url: 'historique.html' },
        { name: 'Bonus', icon: 'fa-gift', url: 'bonus.html' },
        { name: 'Blog', icon: 'fa-newspaper', url: 'blog.html' },
        { name: 'Conseils', icon: 'fa-lightbulb', url: 'conseils.html' },
        { name: 'Contact', icon: 'fa-envelope', url: 'contact.html' }
    ];

    function createMenu() {
        const header = document.querySelector('header');
        if (!header) return;

        // Supprimer l'ancien menu s'il existe (dans le header ou en dessous)
        const oldNav = header.querySelector('nav');
        if (oldNav) oldNav.remove();
        const oldMenuRow = document.querySelector('.menu-row');
        if (oldMenuRow) oldMenuRow.remove();

        // Créer le nouveau menu
        const nav = document.createElement('nav');
        nav.className = 'icon-nav';

        const ul = document.createElement('ul');
        ul.className = 'icon-nav-list';

        menuItems.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = item.url;
            a.innerHTML = `<span class="nav-icon"><i class="fas ${item.icon}"></i></span><span class="nav-label">${item.name}</span>`;

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

        // Créer une ligne pour le menu en dessous du header
        const menuRow = document.createElement('div');
        menuRow.className = 'menu-row';
        menuRow.appendChild(nav);

        // Insérer le menu après le header
        header.insertAdjacentElement('afterend', menuRow);

        // Ajouter les styles
        addStyles();
    }

    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Styles du menu à icônes */
            .menu-row {
                background: #0D0D0D;
                border-top: 2px solid #D4AF37;
                border-bottom: 2px solid #D4AF37;
                padding: 5px 0;
                width: 100%;
            }
            .icon-nav {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                justify-content: center;
                overflow-x: auto;
                white-space: nowrap;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: thin;
                scrollbar-color: #D4AF37 #0D0D0D;
                padding: 0 10px;
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
                gap: 0;
                flex-wrap: nowrap;
                width: 100%;
                justify-content: space-around;
            }
            .icon-nav-list li {
                display: flex;
                flex: 1;
                min-width: 0;
                justify-content: center;
            }
            .icon-nav-list a {
                display: flex;
                flex-direction: column;
                align-items: center;
                color: #fff;
                text-decoration: none;
                font-size: 0.75rem;
                transition: color 0.3s;
                padding: 5px 0;
                border-radius: 8px;
                white-space: nowrap;
                width: 100%;
                max-width: 80px;
            }
            .icon-nav-list .nav-icon {
                font-size: 1.3rem;
                margin-bottom: 2px;
            }
            .icon-nav-list .nav-icon i {
                color: inherit;
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
            /* Ajustement du header pour logo à gauche et promo à droite */
            header .container {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: nowrap;
                padding: 0.8rem 15px;
                max-width: 1200px;
                margin: 0 auto;
            }
            .logo {
                flex-shrink: 0;
            }
            .logo a {
                font-size: 1.6rem;
                white-space: nowrap;
                color: #D4AF37;
                text-decoration: none;
            }
            .logo span {
                color: #fff;
            }
            .promo-code {
                flex-shrink: 0;
                white-space: nowrap;
                font-size: 1rem;
                background: #D4AF37;
                color: #000;
                padding: 0.5rem 1.2rem;
                border-radius: 30px;
                font-weight: 700;
            }
            /* Responsive */
            @media (max-width: 600px) {
                .logo a {
                    font-size: 1.4rem;
                }
                .promo-code {
                    font-size: 0.9rem;
                    padding: 0.4rem 1rem;
                }
            }
            @media (max-width: 400px) {
                .logo a {
                    font-size: 1.2rem;
                }
                .promo-code {
                    font-size: 0.8rem;
                    padding: 0.3rem 0.8rem;
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