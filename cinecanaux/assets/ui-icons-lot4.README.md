# Ciné Radar — Icônes originales du lot 4

Les dix illustrations ont été vérifiées visuellement et compressées en un seul atlas `ui-icons-lot4.webp` (**560 × 56 px**, 10 cases de 56 × 56 px, transparence conservée). Les images d'origine PNG sont disponibles dans l'archive créée au moment de la préparation.

## Correspondance des dix cases, de gauche à droite

1. `football` — Actu Foot MRXP, publicité
2. `crypto` — Actu Crypto 24H/7, publicité
3. `pronos` — MR X PRONOS FR, publicité
4. `private` — mention Canal privé
5. `star` — notation sur les fiches et choix de note
6. `evaluate` — invitation communautaire à donner un avis
7. `play` — ouverture des affiches Telegram depuis À l'affiche
8. `series` — affiche/fallback et pastille Séries
9. `thanks` — confirmation après note
10. `popcorn` — aide de navigation sur l'accueil

Le composant CSS `.cine-lot4-icon` utilise `background-size:1000% 100%` et les positions de 0 à 100% par pas de 11,111111%. `cineLot4Icon(key)` crée une image décorative (avec `aria-hidden`) ; les boutons conservent leurs textes et libellés accessibles.

La route Worker `/assets/ui-icons-lot4.webp` récupère le fichier depuis la branche publique `main`. Garder la route et l'atlas ensemble lors de la publication.

Ne pas supprimer les trois premiers lots, les vrais avatars Telegram ni les conditions d'âge sur les contenus de pronostics.
