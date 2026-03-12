// assets/js/menu.js
// Menu horizontal avec icônes Font Awesome, placé sous le logo et le code promo
// Logo et code promo sur la même ligne en haut, menu en dessous
// Effet de pulsation sur le code promo, barre sans bordures avec ombre en haut

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

        // Insérer le nav après le container (dans le header)
        const container = header.querySelector('.container');
        if (container) {
            container.insertAdjacentElement('afterend', nav);
        } else {
            header.appendChild(nav);
        }

        // Ajouter les styles
        addStyles();
    }

    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Header : deux lignes */
            header {
                display: flex;
                flex-direction: column;
                width: 100%;
            }
            /* Première ligne : logo et code promo côte à côte */
            header .container {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.8rem 15px;
                width: 100%;
                box-sizing: border-box;
                flex-wrap: nowrap; /* Force la ligne horizontale */
            }
            .logo {
                flex-shrink: 0;
                white-space: nowrap;
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
                margin-left: 10px;
                animation: gentle-pulse 2s infinite;
                box-shadow: 0 0 0 rgba(212, 175, 55, 0.4);
                transition: transform 0.3s, box-shadow 0.3s;
            }
            .promo-code:hover {
                animation: none;
                transform: scale(1.05);
                box-shadow: 0 0 15px rgba(212, 175, 55, 0.8);
            }

            /* Animation de pulsation */
            @keyframes gentle-pulse {
                0% {
                    box-shadow: 0 0 0 0 rgba(212, 175, 55, 0.4);
                }
                70% {
                    box-shadow: 0 0 0 10px rgba(212, 175, 55, 0);
                }
                100% {
                    box-shadow: 0 0 0 0 rgba(212, 175, 55, 0);
                }
            }

            /* Deuxième ligne : menu sans bordures avec ombre en haut */
            .icon-nav {
                width: 100%;
                background: linear-gradient(180deg, #0D0D0D 0%, #1a1a1a 100%);
                padding: 5px 10px;
                overflow-x: auto;
                white-space: nowrap;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: thin;
                scrollbar-color: #D4AF37 #0D0D0D;
                box-sizing: border-box;
                box-shadow: 0 -4px 8px rgba(0, 0, 0, 0.5), inset 0 1px 3px rgba(255, 255, 255, 0.2);
                position: relative;
                z-index: 10;
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
                font-size: 0.7rem;
                transition: color 0.3s;
                padding: 3px 0;
                border-radius: 8px;
                white-space: nowrap;
                width: 100%;
                max-width: 70px;
            }
            .icon-nav-list .nav-icon {
                font-size: 1.2rem;
                margin-bottom: 2px;
            }
            .icon-nav-list .nav-icon i {
                color: inherit;
            }
            .icon-nav-list .nav-label {
                font-size: 0.6rem;
                font-weight: 500;
            }
            .icon-nav-list a:hover,
            .icon-nav-list a.active {
                color: #D4AF37;
                background: rgba(212, 175, 55, 0.1);
            }

            /* Responsive : garantir que le logo et code promo restent sur la même ligne */
            @media (max-width: 600px) {
                header .container {
                    padding: 0.5rem 8px;
                }
                .logo a {
                    font-size: 1.2rem; /* Réduction pour mobile */
                }
                .promo-code {
                    font-size: 0.8rem; /* Réduction */
                    padding: 0.3rem 0.8rem;
                    margin-left: 5px;
                }
                .icon-nav-list .nav-icon {
                    font-size: 1.1rem;
                }
                .icon-nav-list .nav-label {
                    font-size: 0.55rem;
                }
                .icon-nav-list a {
                    max-width: 60px;
                }
            }
            @media (max-width: 400px) {
                .logo a {
                    font-size: 1rem; /* Encore plus petit */
                }
                .promo-code {
                    font-size: 0.7rem;
                    padding: 0.2rem 0.6rem;
                }
                .icon-nav-list .nav-icon {
                    font-size: 1rem;
                }
                .icon-nav-list .nav-label {
                    font-size: 0.5rem;
                }
                .icon-nav-list a {
                    max-width: 50px;
                }
            }
            @media (max-width: 320px) {
                .logo a {
                    font-size: 0.9rem;
                }
                .promo-code {
                    font-size: 0.65rem;
                    padding: 0.2rem 0.5rem;
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