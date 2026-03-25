// assets/js/menu.js
// Menu burger premium + icônes au-dessus du texte (comme l'ancien menu)

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

  function ensureFontAwesome() {
    // Certaines pages n'importent pas FA, donc on le charge ici pour garantir les icônes
    const already =
      document.querySelector('link[href*="font-awesome"]') ||
      document.querySelector('link[href*="fontawesome"]') ||
      document.querySelector('link[data-fa-global="true"]');

    if (already) return;

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css';
    link.crossOrigin = 'anonymous';
    link.referrerPolicy = 'no-referrer';
    link.dataset.faGlobal = 'true';
    document.head.appendChild(link);
  }

  function isCurrentPage(url) {
    const currentPath = window.location.pathname;
    return (
      currentPath.endsWith(url) ||
      (url === 'index.html' && (currentPath === '/' || currentPath.endsWith('/')))
    );
  }

  function createBurgerButton() {
    if (document.getElementById('burger-btn')) return null;

    const btn = document.createElement('button');
    btn.id = 'burger-btn';
    btn.className = 'burger-btn';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Ouvrir le menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '<i class="fas fa-bars"></i>';
    return btn;
  }

  function createBurgerOverlay() {
    if (document.getElementById('burger-overlay')) return null;

    const overlay = document.createElement('div');
    overlay.id = 'burger-overlay';
    overlay.className = 'burger-overlay';
    overlay.innerHTML = `
      <div class="burger-drawer" role="dialog" aria-modal="true" aria-label="Menu">
        <div class="burger-menu-header">
          <div class="burger-menu-title">Menu</div>
          <button type="button" class="burger-close" aria-label="Fermer le menu">&times;</button>
        </div>
        <div class="burger-menu-content">
          <div class="burger-menu-grid">
            ${menuItems.map(item => `
              <a class="burger-menu-item ${isCurrentPage(item.url) ? 'active' : ''}"
                 href="${item.url}"
                 data-vip="${item.vip ? 'true' : 'false'}">
                <span class="menu-icon"><i class="fas ${item.icon}"></i></span>
                <span class="menu-label">${item.name}</span>
              </a>
            `).join('')}
          </div>
        </div>
      </div>
    `;
    return overlay;
  }

  function openMenu(btn, overlay) {
    overlay.classList.add('open');
    document.body.classList.add('menu-open');
    btn.setAttribute('aria-expanded', 'true');
  }

  function closeMenu(btn, overlay) {
    overlay.classList.remove('open');
    document.body.classList.remove('menu-open');
    btn.setAttribute('aria-expanded', 'false');
  }

  function createMenu() {
    ensureFontAwesome();

    const header = document.querySelector('header');
    if (!header) return;

    // Supprime l'ancien menu horizontal si présent
    header.querySelector('.icon-nav')?.remove();

    const btn = createBurgerButton();
    const overlay = createBurgerOverlay();
    if (!btn || !overlay) return;

    // Placement : dans la zone header-actions (à droite), pour garder la beauté du header
    const actions = header.querySelector('.header-actions');
    if (actions) {
      actions.appendChild(btn);
    } else {
      // fallback si une page n'a pas .header-actions
      const container = header.querySelector('.container') || header;
      container.appendChild(btn);
    }

    document.body.appendChild(overlay);

    const drawer = overlay.querySelector('.burger-drawer');
    const closeBtn = overlay.querySelector('.burger-close');

    btn.addEventListener('click', () => {
      const isOpen = overlay.classList.contains('open');
      if (isOpen) closeMenu(btn, overlay);
      else openMenu(btn, overlay);
    });

    closeBtn.addEventListener('click', () => closeMenu(btn, overlay));

    // clic sur le backdrop ferme (mais pas clic dans le drawer)
    overlay.addEventListener('click', (e) => {
      if (drawer && drawer.contains(e.target)) return;
      closeMenu(btn, overlay);
    });

    // ESC ferme
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay.classList.contains('open')) {
        closeMenu(btn, overlay);
      }
    });

    // VIP item : conserve la logique existante (handleVipClick)
    overlay.querySelectorAll('.burger-menu-item').forEach(a => {
      const isVip = a.getAttribute('data-vip') === 'true';
      if (!isVip) return;

      a.addEventListener('click', (e) => {
        e.preventDefault();
        closeMenu(btn, overlay);

        if (typeof window.handleVipClick === 'function') {
          window.handleVipClick();
        } else {
          window.location.href = a.getAttribute('href');
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createMenu);
  } else {
    createMenu();
  }
})();