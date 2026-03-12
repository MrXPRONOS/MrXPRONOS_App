// assets/js/back-to-top.js
// Bouton flottant "Retour en haut" en bas à gauche
// Masqué automatiquement quand l'assistant est ouvert (classe .assistant-open sur body)

(function() {
    'use strict';

    // Créer le bouton
    const btn = document.createElement('button');
    btn.id = 'back-to-top';
    btn.setAttribute('aria-label', 'Retour en haut');
    btn.innerHTML = '<i class="fas fa-arrow-up"></i>';
    document.body.appendChild(btn);

    // Ajouter les styles
    const style = document.createElement('style');
    style.textContent = `
        #back-to-top {
            position: fixed;
            bottom: 35px;
            left: 20px;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #D4AF37;
            color: #000;
            border: 2px solid #D4AF37;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            transition: all 0.3s ease;
            z-index: 10000;
            opacity: 0.8;
        }
        #back-to-top:hover {
            transform: scale(1.1) translateY(-3px);
            opacity: 1;
            background: #000;
            color: #D4AF37;
            border-color: #D4AF37;
            box-shadow: 0 6px 15px rgba(212,175,55,0.4);
        }
        #back-to-top.visible {
            display: flex;
        }
        /* Cacher le bouton quand l'assistant est ouvert */
        body.assistant-open #back-to-top {
            display: none !important;
        }
        @media (max-width: 768px) {
            #back-to-top {
                width: 40px;
                height: 40px;
                font-size: 1.2rem;
                bottom: 25px;
                left: 15px;
            }
        }
    `;
    document.head.appendChild(style);

    // Afficher/masquer le bouton en fonction du défilement
    window.addEventListener('scroll', function() {
        if (window.scrollY > 300) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
    });

    // Action de remonter en haut
    btn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
})();