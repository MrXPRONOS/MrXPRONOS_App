// assets/js/mobile-menu.js
// Menu mobile moderne : barre supérieure avec hamburger + tiroir

(function() {
    'use strict';

    // Configuration des liens
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

    // Créer le bouton hamburger et le drawer
    function createMobileMenu() {
        // Trouver le header existant
        const header = document.querySelector('header .container');
        if (!header) return;

        // Vérifier si le menu mobile existe déjà
        if (document.querySelector('.mobile-menu-btn')) return;

        // Créer le bouton hamburger
        const menuBtn = document.createElement('button');
        menuBtn.className = 'mobile-menu-btn';
        menuBtn.setAttribute('aria-label', 'Menu');
        menuBtn.innerHTML = '<span></span><span></span><span></span>'; // trois barres

        // Insérer le bouton à côté du logo (par exemple après le logo)
        const logo = header.querySelector('.logo');
        if (logo) {
            logo.parentNode.insertBefore(menuBtn, logo.nextSibling);
        } else {
            header.appendChild(menuBtn);
        }

        // Créer le drawer (tiroir)
        const drawer = document.createElement('div');
        drawer.className = 'mobile-drawer';
        drawer.setAttribute('aria-hidden', 'true');
        drawer.innerHTML = `
            <div class="mobile-drawer-header">
                <span class="mobile-drawer-title">Menu</span>
                <button class="mobile-drawer-close">&times;</button>
            </div>
            <ul class="mobile-drawer-menu">
                ${menuItems.map(item => `
                    <li><a href="${item.url}" class="${window.location.pathname.endsWith(item.url) ? 'active' : ''}">${item.name}</a></li>
                `).join('')}
            </ul>
        `;
        document.body.appendChild(drawer);

        // Overlay pour fermer en cliquant à l'extérieur
        const overlay = document.createElement('div');
        overlay.className = 'mobile-drawer-overlay';
        overlay.setAttribute('aria-hidden', 'true');
        document.body.appendChild(overlay);

        // Gestion des événements
        menuBtn.addEventListener('click', () => {
            drawer.classList.add('open');
            overlay.classList.add('open');
            document.body.style.overflow = 'hidden'; // Empêcher le scroll
        });

        const closeDrawer = () => {
            drawer.classList.remove('open');
            overlay.classList.remove('open');
            document.body.style.overflow = '';
        };

        drawer.querySelector('.mobile-drawer-close').addEventListener('click', closeDrawer);
        overlay.addEventListener('click', closeDrawer);

        // Ajouter les styles
        addStyles();
    }

    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Bouton hamburger */
            .mobile-menu-btn {
                background: transparent;
                border: none;
                cursor: pointer;
                display: flex;
                flex-direction: column;
                justify-content: space-around;
                width: 30px;
                height: 30px;
                padding: 0;
                margin-left: 15px;
            }
            .mobile-menu-btn span {
                display: block;
                width: 100%;
                height: 3px;
                background: #D4AF37;
                border-radius: 3px;
                transition: all 0.3s;
            }
            /* Cacher l'ancien menu */
            header nav {
                display: none;
            }
            /* Drawer (tiroir) */
            .mobile-drawer {
                position: fixed;
                top: 0;
                left: -280px;
                width: 280px;
                height: 100%;
                background: #0D0D0D;
                border-right: 2px solid #D4AF37;
                box-shadow: 2px 0 10px rgba(0,0,0,0.5);
                z-index: 2000;
                transition: left 0.3s ease;
                font-family: 'Montserrat', sans-serif;
                overflow-y: auto;
            }
            .mobile-drawer.open {
                left: 0;
            }
            .mobile-drawer-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px;
                border-bottom: 1px solid #D4AF37;
            }
            .mobile-drawer-title {
                color: #D4AF37;
                font-size: 1.2rem;
                font-weight: 600;
            }
            .mobile-drawer-close {
                background: transparent;
                border: none;
                color: #D4AF37;
                font-size: 2rem;
                cursor: pointer;
                line-height: 1;
            }
            .mobile-drawer-menu {
                list-style: none;
                padding: 20px;
                margin: 0;
            }
            .mobile-drawer-menu li {
                margin-bottom: 15px;
            }
            .mobile-drawer-menu a {
                color: #fff;
                text-decoration: none;
                font-size: 1rem;
                display: block;
                padding: 10px;
                border-radius: 8px;
                transition: background 0.3s;
            }
            .mobile-drawer-menu a:hover,
            .mobile-drawer-menu a.active {
                background: rgba(212, 175, 55, 0.2);
                color: #D4AF37;
            }
            /* Overlay */
            .mobile-drawer-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1999;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s;
            }
            .mobile-drawer-overlay.open {
                opacity: 1;
                visibility: visible;
            }
            /* Sur desktop, on peut réafficher le menu normal si on veut */
            @media (min-width: 769px) {
                header nav {
                    display: flex; /* ou block selon le design original */
                }
                .mobile-menu-btn {
                    display: none;
                }
                .mobile-drawer,
                .mobile-drawer-overlay {
                    display: none;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // Lancer au chargement du DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createMobileMenu);
    } else {
        createMobileMenu();
    }
})();