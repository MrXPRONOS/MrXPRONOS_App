// assets/js/back-to-top.js
// Version allégée - CSS géré dans style.css

(function () {
    'use strict';

    function createButton() {
        if (document.getElementById('back-to-top')) return;

        const btn = document.createElement('button');
        btn.id = 'back-to-top';
        btn.setAttribute('aria-label', 'Retour en haut');
        btn.type = 'button';
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 20V4M5 11l7-7 7 7"/></svg>';
        document.body.appendChild(btn);

        btn.addEventListener('click', function () {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });

        window.addEventListener('scroll', toggleVisibility, { passive: true });
        toggleVisibility();
    }

    function toggleVisibility() {
        const btn = document.getElementById('back-to-top');
        if (!btn) return;

        if (window.scrollY > 300) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createButton);
    } else {
        createButton();
    }
})();