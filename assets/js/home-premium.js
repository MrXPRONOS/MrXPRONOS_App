/* Accueil : partage volontaire et date de copyright, sans porte d'accès. */
(function () {
  'use strict';
  const year = document.getElementById('mx-current-year');
  if (year) year.textContent = String(new Date().getFullYear());

  // Les explications secondaires restent facultatives sur desktop et mobile.
  const mobileDetails = document.querySelectorAll('[data-mobile-collapsible]');
  mobileDetails.forEach((detail) => detail.removeAttribute('open'));
  const share = document.querySelector('.mx-share-site');
  if (!share) return;
  share.addEventListener('click', async () => {
    const url = 'https://mrxpronos.github.io/MrXPRONOS_App/';
    const title = 'Mr XPRONOS — Pronostics football';
    const text = 'Découvre les analyses football Pro et VIP, les résultats et les analyses sur Mr XPRONOS.';
    if (navigator.share) {
      try { await navigator.share({ title, text, url }); } catch (error) {
        if (error && error.name !== 'AbortError') console.warn('Partage non disponible', error);
      }
      return;
    }
    const message = `${text}\n${url}`;
    const target = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(target, '_blank', 'noopener,noreferrer');
  });
})();