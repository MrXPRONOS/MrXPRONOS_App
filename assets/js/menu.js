// assets/js/menu.js
// Navigation mobile premium Mr XPRONOS — icônes locales, bottom bar + drawer.
(function () {
  'use strict';

  const ICON_BASE = 'assets/images/mobile-premium/';
  const LOGO = 'assets/images/mrxpronos-horizontal.webp?v=20261011-approved-mx1';
  const MOBILE_NAV_CSS = 'assets/css/mobile-nav-premium.css?v=20261012-mobile-nav1';

  function ensureMobileNavStyles() {
    if (document.querySelector('link[data-mx-mobile-nav="true"]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = MOBILE_NAV_CSS;
    link.dataset.mxMobileNav = 'true';
    document.head.appendChild(link);
  }

  const menuItems = [
    { name: 'Accueil', icon: 'icon-home.webp', url: 'index.html' },
    { name: 'Pronostics', icon: 'icon-pronostics.webp', url: 'pronos.html', featured: 'coupons', badge: 'TOP' },
    { name: 'LIVE', icon: 'icon-live.webp', url: 'live.html', vip: true, featured: 'vip', badge: 'LIVE' },
    { name: 'Historique', icon: 'icon-history.webp', url: 'historique.html' },
    { name: 'Blog', icon: 'icon-blog.webp', url: 'blog.html' },
    { name: 'Conseils', icon: 'icon-conseils.webp', url: 'conseils.html' },
    { name: 'Infos sport', icon: 'icon-infos.webp', url: 'infos.html' },
    { name: 'Bonus & Promo', icon: 'icon-bonus.webp', url: 'bonus.html' },
    { name: 'Contact', icon: 'icon-contact.webp', url: 'contact.html' }
  ];

  const bottomItems = [
    { name: 'Accueil', icon: 'icon-home.webp', url: 'index.html' },
    { name: 'Pronostics', icon: 'icon-pronostics.webp', url: 'pronos.html' },
    { name: 'LIVE', icon: 'icon-live.webp', url: 'live.html', live: true },
    { name: 'Bonus', icon: 'icon-bonus.webp', url: 'bonus.html' },
    { name: 'Menu', icon: 'icon-menu.webp', action: 'menu' }
  ];

  function currentFile() {
    const path = window.location.pathname || '/';
    if (path.endsWith('/')) return 'index.html';
    const file = path.split('/').pop() || '';
    return file.includes('.') ? file : 'index.html';
  }

  function currentSectionFile() {
    const file = currentFile();
    if (file === 'article.html') return 'blog.html';
    if (file === 'conseil.html') return 'conseils.html';
    if (file === 'bookmakers.html') return 'bonus.html';
    return file || 'index.html';
  }

  function isCurrentPage(url) {
    return currentSectionFile() === url;
  }

  function iconMarkup(file, className, alt = '') {
    return `<img class="${className}" src="${ICON_BASE}${file}" alt="${alt}" loading="eager" decoding="async">`;
  }

  function createBurgerButton() {
    if (document.getElementById('burger-btn')) return document.getElementById('burger-btn');

    const btn = document.createElement('button');
    btn.id = 'burger-btn';
    btn.className = 'burger-btn';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Ouvrir le menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', 'burger-overlay');
    btn.innerHTML = iconMarkup('icon-menu.webp', 'mx-burger-icon');
    return btn;
  }

  function createBurgerOverlay() {
    const existing = document.getElementById('burger-overlay');
    if (existing) return existing;

    const overlay = document.createElement('div');
    overlay.id = 'burger-overlay';
    overlay.className = 'burger-overlay';
    overlay.setAttribute('aria-hidden', 'true');

    overlay.innerHTML = `
      <div class="burger-drawer" role="dialog" aria-modal="true" aria-label="Navigation Mr XPRONOS">
        <div class="burger-menu-header">
          <a class="burger-menu-brand" href="index.html" aria-label="Mr XPRONOS — Accueil">
            <img src="${LOGO}" alt="Mr XPRONOS">
          </a>
          <button type="button" class="burger-close" aria-label="Fermer le menu"><span aria-hidden="true">×</span></button>
        </div>

        <div class="burger-menu-content">
          <div class="burger-menu-intro">
            <span>Navigation</span>
            <strong>Tout Mr XPRONOS</strong>
          </div>

          <div class="burger-menu-grid">
            ${menuItems.map(item => {
              const featuredClass = item.featured ? `featured featured-${item.featured}` : '';
              const activeClass = isCurrentPage(item.url) ? 'active' : '';
              const badge = item.badge ? `<span class="menu-badge">${item.badge}</span>` : '';
              const liveDot = item.featured === 'vip' ? '<span class="menu-live-dot" aria-hidden="true"></span>' : '';

              return `
                <a class="burger-menu-item ${activeClass} ${featuredClass}"
                   href="${item.url}"
                   ${activeClass ? 'aria-current="page"' : ''}
                   data-vip="${item.vip ? 'true' : 'false'}">
                  ${liveDot}
                  ${badge}
                  <span class="menu-icon">${iconMarkup(item.icon, 'menu-icon-img')}</span>
                  <span class="menu-label">${item.name}</span>
                </a>
              `;
            }).join('')}
          </div>

          <div class="burger-menu-foot">
            <span>Code promo</span>
            <button type="button" class="burger-promo-copy promo-copy" data-copy="XPVIP" aria-label="Copier le code promo XPVIP">
              <strong>XPVIP</strong><small>Toucher pour copier</small>
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    return overlay;
  }

  function createBottomNav() {
    const path = (location.pathname || '').toLowerCase();
    if (
      path.includes('admin') ||
      path.endsWith('offline.html') ||
      document.body.classList.contains('mx-live-page')
    ) return null;

    const existing = document.getElementById('bottom-nav');
    if (existing) return existing;

    const nav = document.createElement('nav');
    nav.id = 'bottom-nav';
    nav.className = 'bottom-nav';
    nav.setAttribute('aria-label', 'Navigation rapide');

    const inner = document.createElement('div');
    inner.className = 'inner';

    const section = currentSectionFile();
    const primaryFiles = new Set(['index.html', 'pronos.html', 'live.html', 'bonus.html']);
    const secondaryPage = !primaryFiles.has(section);

    inner.innerHTML = bottomItems.map(item => {
      const isMenu = item.action === 'menu';
      const isActive = isMenu ? secondaryPage : isCurrentPage(item.url);
      const common = `class="bottom-nav-item ${isActive ? 'active' : ''} ${item.live ? 'live' : ''} ${isMenu ? 'bottom-nav-menu' : ''}"`;

      const content = `
        <span class="bottom-nav-icon-wrap">
          ${iconMarkup(item.icon, 'bottom-nav-icon')}
          ${item.live ? '<span class="bottom-live-dot" aria-hidden="true"></span>' : ''}
        </span>
        <span class="bottom-nav-label">${item.name}</span>
      `;

      if (isMenu) {
        return `<button type="button" id="bottom-nav-menu" ${common} aria-label="Ouvrir le menu" aria-controls="burger-overlay" aria-expanded="false">${content}</button>`;
      }

      return `<a href="${item.url}" ${common} ${isActive ? 'aria-current="page"' : ''}>${content}</a>`;
    }).join('');

    nav.appendChild(inner);
    document.body.appendChild(nav);
    document.body.classList.add('has-bottom-nav');
    return nav;
  }

  function setExpanded(expanded) {
    const value = String(expanded);
    document.getElementById('burger-btn')?.setAttribute('aria-expanded', value);
    document.getElementById('bottom-nav-menu')?.setAttribute('aria-expanded', value);
  }

  function openMenu(overlay) {
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('menu-open');
    document.getElementById('bottom-nav-menu')?.classList.add('is-open');
    setExpanded(true);
  }

  function closeMenu(overlay) {
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('menu-open');
    document.getElementById('bottom-nav-menu')?.classList.remove('is-open');
    setExpanded(false);
  }

  function wirePromoCopy(root) {
    root.querySelectorAll('.promo-copy[data-copy]').forEach((button) => {
      if (button.dataset.copyReady === '1') return;
      button.dataset.copyReady = '1';

      button.addEventListener('click', async () => {
        const value = button.dataset.copy || '';
        if (!value) return;
        try {
          await navigator.clipboard.writeText(value);
          button.classList.add('copied');
          const small = button.querySelector('small');
          if (small) small.textContent = 'Copié !';
          setTimeout(() => {
            button.classList.remove('copied');
            if (small) small.textContent = 'Toucher pour copier';
          }, 1400);
        } catch (_) {
          // Le code reste visible même si le presse-papiers est refusé.
        }
      });
    });
  }

  function createMenu() {
    ensureMobileNavStyles();
    const overlay = createBurgerOverlay();
    const bottomNav = createBottomNav();
    const bottomMenu = bottomNav?.querySelector('#bottom-nav-menu');

    const header = document.querySelector('header');
    let burgerBtn = null;

    // Live possède déjà ses contrôles mobiles dédiés. Le menu reste accessible
    // via la barre inférieure, sans ajouter un quatrième bouton dans son header.
    if (header && !document.body.classList.contains('mx-live-page')) {
      burgerBtn = createBurgerButton();
      if (!burgerBtn.isConnected) {
        const actions = header.querySelector('.header-actions');
        if (actions) actions.appendChild(burgerBtn);
        else (header.querySelector('.container') || header).appendChild(burgerBtn);
      }
    }

    const drawer = overlay.querySelector('.burger-drawer');
    const closeBtn = overlay.querySelector('.burger-close');

    if (burgerBtn && burgerBtn.dataset.menuReady !== '1') {
      burgerBtn.dataset.menuReady = '1';
      burgerBtn.addEventListener('click', () => {
        overlay.classList.contains('open') ? closeMenu(overlay) : openMenu(overlay);
      });
    }

    if (bottomMenu && bottomMenu.dataset.menuReady !== '1') {
      bottomMenu.dataset.menuReady = '1';
      bottomMenu.addEventListener('click', () => {
        overlay.classList.contains('open') ? closeMenu(overlay) : openMenu(overlay);
      });
    }

    if (closeBtn && closeBtn.dataset.menuReady !== '1') {
      closeBtn.dataset.menuReady = '1';
      closeBtn.addEventListener('click', () => closeMenu(overlay));
    }

    if (overlay.dataset.menuReady !== '1') {
      overlay.dataset.menuReady = '1';
      overlay.addEventListener('click', (event) => {
        if (drawer && drawer.contains(event.target)) return;
        closeMenu(overlay);
      });

      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && overlay.classList.contains('open')) closeMenu(overlay);
      });
    }

    overlay.querySelectorAll('.burger-menu-item').forEach((link) => {
      if (link.dataset.itemReady === '1') return;
      link.dataset.itemReady = '1';
      link.addEventListener('click', (event) => {
        const isVip = link.getAttribute('data-vip') === 'true';
        closeMenu(overlay);
        if (!isVip) return;

        event.preventDefault();
        if (typeof window.handleVipClick === 'function') window.handleVipClick();
        else window.location.href = link.getAttribute('href');
      });
    });

    wirePromoCopy(overlay);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createMenu, { once: true });
  } else {
    createMenu();
  }
})();