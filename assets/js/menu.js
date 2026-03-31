// assets/js/menu.js
// Menu burger premium + mise en valeur LIVE VIP + COUPONS
(function () {
  'use strict';

  const menuItems = [
    { name: 'Accueil', icon: 'fa-home', url: 'index.html' },

    // ⭐ Mis en valeur
    { name: 'COUPONS', icon: 'fa-ticket', url: 'pronos.html', featured: 'coupons', badge: 'TOP' },

    // ⭐ Mis en valeur + VIP gating
    { name: 'LIVE VIP', icon: 'fa-bolt', url: 'live.html', vip: true, featured: 'vip', badge: 'VIP' },

    { name: 'Historique', icon: 'fa-clock-rotate-left', url: 'historique.html' },
    { name: 'Bonus', icon: 'fa-gift', url: 'bonus.html' },
    { name: 'Blog', icon: 'fa-newspaper', url: 'blog.html' },
    { name: 'Conseils', icon: 'fa-lightbulb', url: 'conseils.html' },
    { name: 'Actus Foot', icon: 'fa-futbol', url: 'infos.html' },
    { name: 'Contact', icon: 'fa-envelope', url: 'contact.html' }
  ];

  function ensureFontAwesome() {
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

  function injectMenuHighlightStyles() {
    if (document.getElementById('mx-menu-featured-style')) return;

    const style = document.createElement('style');
    style.id = 'mx-menu-featured-style';
    style.textContent = `
      @keyframes mxFeaturedPulse {
        0%, 100% { box-shadow: 0 0 0 rgba(212,175,55,0.0); transform: translateY(0); }
        50% { box-shadow: 0 0 22px rgba(212,175,55,0.22); transform: translateY(-1px); }
      }

      .burger-menu-item.featured {
        position: relative;
        border: 1px solid rgba(212,175,55,0.55) !important;
        background: linear-gradient(180deg, rgba(212,175,55,0.12), rgba(255,255,255,0.03)) !important;
        box-shadow: 0 14px 35px rgba(0,0,0,0.45), 0 0 0 3px rgba(212,175,55,0.08);
        animation: mxFeaturedPulse 2.2s ease-in-out infinite;
      }
      .burger-menu-item.featured:hover {
        border-color: rgba(212,175,55,0.85) !important;
        box-shadow: 0 18px 45px rgba(0,0,0,0.55), 0 0 28px rgba(212,175,55,0.18);
      }

      .burger-menu-item.featured .menu-label {
        font-weight: 900 !important;
        letter-spacing: 0.3px;
      }

      .burger-menu-item.featured-vip .menu-icon { color: #D4AF37 !important; }
      .burger-menu-item.featured-coupons .menu-icon { color: #22C55E !important; }

      .burger-menu-item .menu-badge {
        position: absolute;
        top: 8px;
        right: 8px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 900;
        border-radius: 999px;
        border: 1px solid rgba(212,175,55,0.5);
        background: rgba(0,0,0,0.55);
        color: #D4AF37;
        text-transform: uppercase;
      }
      .burger-menu-item.featured-coupons .menu-badge {
        border-color: rgba(34,197,94,0.55);
        color: #22C55E;
      }
    `;
    document.head.appendChild(style);
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
            ${menuItems.map(item => {
              const featuredClass = item.featured ? `featured featured-${item.featured}` : '';
              const activeClass = isCurrentPage(item.url) ? 'active' : '';
              const badge = item.badge ? `<span class="menu-badge">${item.badge}</span>` : '';

              return `
                <a class="burger-menu-item ${activeClass} ${featuredClass}"
                   href="${item.url}"
                   data-vip="${item.vip ? 'true' : 'false'}">
                  ${badge}
                  <span class="menu-icon"><i class="fas ${item.icon}"></i></span>
                  <span class="menu-label">${item.name}</span>
                </a>
              `;
            }).join('')}
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
    injectMenuHighlightStyles();

    const header = document.querySelector('header');
    if (!header) return;

    // Supprime l'ancien menu horizontal si présent
    header.querySelector('.icon-nav')?.remove();

    const btn = createBurgerButton();
    const overlay = createBurgerOverlay();
    if (!btn || !overlay) return;

    // Placement dans header-actions (à droite)
    const actions = header.querySelector('.header-actions');
    if (actions) {
      actions.appendChild(btn);
    } else {
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

    // clic sur backdrop ferme
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

    // VIP item : garde la logique existante (handleVipClick)
    overlay.querySelectorAll('.burger-menu-item').forEach((a) => {
      const isVip = a.getAttribute('data-vip') === 'true';

      // Ferme le menu quand on clique n'importe quel lien (plus propre)
      a.addEventListener('click', () => closeMenu(btn, overlay), { passive: true });

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