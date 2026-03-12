// assets/js/menu.js
// Menu moderne responsive pour Mr XPRONOS
(function() {
    'use strict';

    const menuItems = [
        { name: 'Accueil', url: 'index.html' },
        { name: 'Pronostics', url: 'pronos.html' },
        { name: 'LIVE VIP', url: 'live.html' },
        { name: 'Historique', url: 'historique.html' },
        { name: 'Bonus', url: 'bonus.html' },
        { name: 'Blog', url: 'blog.html' },
        { name: 'Conseils', url: 'conseils.html' },
        { name: 'Contact', url: 'contact.html' }
    ];

    function createMenu() {
        const header = document.querySelector('header .container');
        if (!header) return;

        // Supprimer l'ancien menu s'il existe
        const oldNav = header.querySelector('nav');
        if (oldNav) oldNav.remove();

        // Créer le nouveau menu
        const nav = document.createElement('nav');
        nav.className = 'main-nav';

        // Bouton hamburger pour mobile
        const hamburger = document.createElement('button');
        hamburger.className = 'hamburger';
        hamburger.setAttribute('aria-label', 'Menu');
        hamburger.innerHTML = '<span></span><span></span><span></span>';
        nav.appendChild(hamburger);

        // Liste des liens
        const ul = document.createElement('ul');
        ul.className = 'nav-links';

        menuItems.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = item.url;
            a.textContent = item.name;

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

        // Gestion du hamburger
        const overlay = document.createElement('div');
        overlay.className = 'nav-overlay';
        document.body.appendChild(overlay);

        hamburger.addEventListener('click', () => {
            ul.classList.toggle('open');
            overlay.classList.toggle('open');
            document.body.style.overflow = ul.classList.contains('open') ? 'hidden' : '';
        });

        overlay.addEventListener('click', () => {
            ul.classList.remove('open');
            overlay.classList.remove('open');
            document.body.style.overflow = '';
        });

        ul.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                ul.classList.remove('open');
                overlay.classList.remove('open');
                document.body.style.overflow = '';
            });
        });

        // Ajouter les styles modifiés
        addStyles();
    }

    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Styles du nouveau menu */
            .main-nav {
                display: flex;
                align-items: center;
                /* Supprimé margin-left: auto pour éviter conflit avec promo-code */
                margin-right: 20px; /* Espace avant le code promo */
            }

            .hamburger {
                display: none;
                flex-direction: column;
                justify-content: space-around;
                width: 30px;
                height: 30px;
                background: transparent;
                border: none;
                cursor: pointer;
                padding: 0;
                z-index: 1001;
            }
            .hamburger span {
                display: block;
                width: 100%;
                height: 3px;
                background: #D4AF37;
                border-radius: 3px;
                transition: all 0.3s;
            }

            .nav-links {
                display: flex;
                list-style: none;
                margin: 0;
                padding: 0;
                gap: 1.5rem;
            }
            .nav-links a {
                color: #fff;
                text-decoration: none;
                font-weight: 500;
                font-size: 0.9rem;
                transition: color 0.3s;
                position: relative;
                padding-bottom: 5px;
            }
            .nav-links a::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                width: 0;
                height: 2px;
                background-color: #D4AF37;
                transition: width 0.3s;
            }
            .nav-links a:hover::after,
            .nav-links a.active::after {
                width: 100%;
            }
            .nav-links a:hover,
            .nav-links a.active {
                color: #D4AF37;
            }

            /* Overlay pour mobile */
            .nav-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 999;
                opacity: 0;
                transition: opacity 0.3s;
            }
            .nav-overlay.open {
                display: block;
                opacity: 1;
            }

            /* Responsive mobile */
            @media (max-width: 768px) {
                .hamburger {
                    display: flex;
                }
                .nav-links {
                    position: fixed;
                    top: 0;
                    right: -300px;
                    width: 280px;
                    height: 100vh;
                    background: #0D0D0D;
                    flex-direction: column;
                    padding: 80px 20px 20px;
                    gap: 1rem;
                    transition: right 0.3s ease;
                    z-index: 1000;
                    border-left: 2px solid #D4AF37;
                    box-shadow: -2px 0 10px rgba(0,0,0,0.5);
                }
                .nav-links.open {
                    right: 0;
                }
                .nav-links a {
                    display: block;
                    padding: 12px;
                    font-size: 1.1rem;
                    border-radius: 8px;
                }
                .nav-links a:hover,
                .nav-links a.active {
                    background: rgba(212,175,55,0.2);
                }
                .nav-links a::after {
                    display: none;
                }
                .main-nav {
                    margin-right: 0; /* pas de marge sur mobile */
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