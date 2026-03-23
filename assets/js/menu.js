// assets/js/menu.js
// Menu horizontal propre, sans CSS injecté

(function () {
    'use strict';

    const menuItems = [
        { name: 'Accueil', icon: 'fa-home', url: 'index.html' },
        { name: 'Coupons', icon: 'fa-chart-line', url: 'pronos.html' },
        { name: 'LIVE VIP', icon: 'fa-bolt', url: 'live.html', vip: true },
        { name: 'Histo', icon: 'fa-clock-rotate-left', url: 'historique.html' },
        { name: 'Bonus', icon: 'fa-gift', url: 'bonus.html' },
        { name: 'Blog', icon: 'fa-newspaper', url: 'blog.html' },
        { name: 'Conseils', icon: 'fa-lightbulb', url: 'conseils.html' },
        { name: 'Contact', icon: 'fa-envelope', url: 'contact.html' }
    ];

    function isCurrentPage(url) {
        const currentPath = window.location.pathname;
        return currentPath.endsWith(url) || (url === 'index.html' && (currentPath === '/' || currentPath.endsWith('/')));
    }

    function createMenu() {
        const header = document.querySelector('header');
        if (!header) return;

        const oldNav = header.querySelector('.icon-nav');
        if (oldNav) oldNav.remove();

        const nav = document.createElement('nav');
        nav.className = 'icon-nav';
        nav.setAttribute('aria-label', 'Navigation principale');

        const ul = document.createElement('ul');
        ul.className = 'icon-nav-list';

        menuItems.forEach(item => {
            const li = document.createElement('li');

            const a = document.createElement('a');
            a.href = item.url;
            a.innerHTML = `
                <span class="nav-icon"><i class="fas ${item.icon}"></i></span>
                <span class="nav-label">${item.name}</span>
            `;

            if (isCurrentPage(item.url)) {
                a.classList.add('active');
                a.setAttribute('aria-current', 'page');
            }

            if (item.vip) {
                a.addEventListener('click', function (e) {
                    e.preventDefault();
                    if (typeof window.handleVipClick === 'function') {
                        window.handleVipClick();
                    } else {
                        window.location.href = item.url;
                    }
                });
            }

            li.appendChild(a);
            ul.appendChild(li);
        });

        nav.appendChild(ul);

        const container = header.querySelector('.container');
        if (container) {
            container.insertAdjacentElement('afterend', nav);
        } else {
            header.appendChild(nav);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createMenu);
    } else {
        createMenu();
    }
})();