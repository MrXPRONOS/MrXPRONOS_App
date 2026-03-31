// assets/js/menu.js
// Menu burger premium + mise en valeur LIVE VIP (vert) + COUPONS (vert)
(function () {
  'use strict';

  const menuItems = [
    { name: 'Accueil', icon: 'fa-home', url: 'index.html' },

    // ⭐ Mis en valeur (vert)
    { name: 'COUPONS', icon: 'fa-ticket', url: 'pronos.html', featured: 'coupons', badge: 'TOP' },

    // ⭐⭐ Très mis en valeur (vert aussi, mais plus premium)
    { name: 'LIVE VIP', icon: 'fa-bolt', url: 'live.html', vip: true, featured: 'vip', badge: 'LIVE' },

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
      :root{
        --mx-green:#22C55E;
        --mx-green-strong:#16A34A;
      }

      @keyframes mxFeaturedPulse {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-1px); }
      }
      @keyframes mxLiveDot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: .35; transform: scale(.78); }
      }

      /* Base featured */
      .burger-menu-item.featured{
        position: relative;
        overflow: hidden;
        animation: mxFeaturedPulse 2.2s ease-in-out infinite;
      }

      /* ✅ COUPONS : vert */
      .burger-menu-item.featured-coupons{
        border: 1px solid rgba(34,197,94,0.55) !important;
        background: linear-gradient(180deg, rgba(34,197,94,0.10), rgba(255,255,255,0.03)) !important;
        box-shadow: 0 14px 35px rgba(0,0,0,0.45), 0 0 0 3px rgba(34,197,94,0.07);
      }
      .burger-menu-item.featured-coupons:hover{
        border-color: rgba(34,197,94,0.85) !important;
        box-shadow: 0 18px 45px rgba(0,0,0,0.55), 0 0 28px rgba(34,197,94,0.18);
      }
      .burger-menu-item.featured-coupons .menu-icon{ color: var(--mx-green) !important; }
      .burger-menu-item.featured-coupons .menu-label{ font-weight: 900 !important; letter-spacing: .3px; }

      /* ✅✅ LIVE VIP : vert aussi, mais plus premium (glow + dot + gradient) */
      .burger-menu-item.featured-vip{
        border: 1px solid rgba(34,197,94,0.75) !important;
        background:
          radial-gradient(circle at top left, rgba(34,197,94,0.20), transparent 55%),
          radial-gradient(circle at bottom right, rgba(34,197,94,0.12), transparent 60%),
          linear-gradient(180deg, rgba(34,197,94,0.14), rgba(255,255,255,0.03)) !important;
        box-shadow:
          0 18px 60px rgba(0,0,0,0.62),
          0 0 0 3px rgba(34,197,94,0.10),
          0 0 40px rgba(34,197,94,0.22);
      }
      .burger-menu-item.featured-vip:hover{
        border-color: rgba(34,197,94,0.95) !important;
        box-shadow:
          0 22px 70px rgba(0,0,0,0.72),
          0 0 0 3px rgba(34,197,94,0.14),
          0 0 55px rgba(34,197,94,0.28);
      }
      .burger-menu-item.featured-vip .menu-icon{ color: var(--mx-green) !important; }
      .burger-menu-item.featured-vip .menu-label{
        font-weight: 950 !important;
        letter-spacing: .45px;
      }

      /* point LIVE qui pulse (vert) */
      .burger-menu-item.featured-vip .menu-live-dot{
        position: absolute;
        top: 10px;
        left: 10px;
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--mx-green);
        box-shadow: 0 0 16px rgba(34,197,94,0.75);
        animation: mxLiveDot 1.3s infinite;
      }

      /* badge */
      .burger-menu-item .menu-badge{
        position: absolute;
        top: 8px;
        right: 8px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 900;
        border-radius: 999px;
        background: rgba(0,0,0,0.55);
        text-transform: uppercase;
      }

      .burger-menu-item.featured-coupons .menu-badge{
        border: 1px solid rgba(34,197,94,0.55);
        color: var(--mx-green);
      }
      .burger-menu-item.featured-vip .menu-badge{
        border: 1px solid rgba(34,197,94,0.75);
        color: var(--mx-green);
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
              const liveDot = item.featured === 'vip' ? `<span class="menu-live-dot"></span>` : '';

              return `
                <a class="burger-menu-item ${activeClass} ${featuredClass}"
                   href="${item.url}"
                   data-vip="${item.vip ? 'true' : 'false'}">
                  ${liveDot}
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

    // Placement dans header-actions
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

    overlay.addEventListener('click', (e) => {
      if (drawer && drawer.contains(e.target)) return;
      closeMenu(btn, overlay);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay.classList.contains('open')) {
        closeMenu(btn, overlay);
      }
    });

    // VIP item : conserve la logique existante (handleVipClick)
    overlay.querySelectorAll('.burger-menu-item').forEach((a) => {
      const isVip = a.getAttribute('data-vip') === 'true';

      // ferme le menu sur tous les clics
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