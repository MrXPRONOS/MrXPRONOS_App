# Mr XPRONOS Play — Phases 2 et 3 : refonte mobile

**Date :** 20 novembre 2026  
**Périmètre :** refonte complète de l'Accueil/Jeux/navigation (phase 2) puis du Profil/progression/solde (phase 3).  
**Contraintes :** présentation mobile en premier, conserver intégralement les identifiants DOM, commandes, handlers, règles du Worker et les réponses serveur.

## Phase 2 — Accueil et Jeux

- En-tête et deux cartes XP/énergie plus compacts, avec une hiérarchie typographique claire.
- Pièce MX légèrement réduite, six raccourcis conservés et rendus plus réguliers, espacement sans débordement.
- Indicateur du boost, instruction « TAPOTER POUR GAGNER » et action de bonus conservés.
- Carte Lucky Wheel : illustration réduite, titre + une phrase sur la première ligne visuelle, puis **bouton JOUER en dessous sur toute la largeur**. La fonction `openWheel()` reste identique.
- Promotion XP : titre **« Gagne des XP Points » sur une seule ligne**, puis sous-titre lisible. Illustration des pièces conservée ; deuxième fusée décorative supprimée pour restaurer la place du texte.
- Espace Jeux : deux tuiles plus équilibrées, Lucky Wheel jouable et Snake toujours désactivé « À VENIR », roue et récompenses adaptées aux petites largeurs.
- Barre de navigation cinq onglets : fond bleu nuit opaque, visuels réduits à 30–34 px, libellés lisibles, onglet actif simplifié, respect de la zone de sécurité Telegram.

## Phase 3 — Profil et progression

- Portrait et badge sont désormais dans **deux colonnes séparées visuellement**, espacées, et non superposées. Étoiles placées sous le badge, nom / rang / identité dans un ordre compréhensible.
- Tous les IDs `avatar`, `mrxp-rank-badge`, `mrxp-rank-image`, `mrxp-rank-stars`, `profile-name`, `profile-level`, etc. sont conservés, avec récupération dynamique des données du serveur.
- Section publique « **MA PROGRESSION** » plutôt que « PROGRESSION V2 » : pourcentage en petite pastille à droite, **sans l'anneau décoratif** qui causait des décalages ; une seule barre de progression principale.
- Bloc « Prochain rang » allégé : icônes réduites, textes alignés et exigences XP/défis officielles inchangées.
- Lignes XP confirmés, attente et synchronisation raccourcies visuellement, sans changer les valeurs affichées.
- Solde MRXP : titre « SOLDE MRXP », étiquette « GRATUITS », montant prioritaire, texte de sécurité toujours présent.
- Boutons de boutique raccourcis en « BOUTIQUE DE BOOSTS » et boutons de rafraîchissement en « ACTUALISER » ; les classes et écouteurs originaux sont inchangés.

## Vérifications et conservation

- Contrôles géométriques Chromium prévus à **320, 360, 375, 390, 430 px** : 7 sections, home/wheel, alignement avatar/badge, pas de chevauchement dans les titres/boutons ni dans la barre de navigation.
- Tests métier non régressifs sur le bot Telegram, la D1, la progression officielle, les boosts MRXP, la signature et la synchronisation.
- Anciennes icônes, 11 avatars, rangs et fichiers graphique conservés. Aucun changement de prix, de transaction, de solde, d'XP, de token ou de temps de synchronisation.
- Les cartes PNG partageables ont été protégées contre les doublons de texte en phase 1 ; leur redesign graphique complet relève de la **phase 4**.
- L'onglet Amis et les missions feront l'objet des améliorations de **phase 5**.

## Publication

**Statut : en production à 100 %** le 20 novembre 2026.

- GitHub : [PR #506](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/506) fusionnée avec le commit `3d02ec2e9a5f2ef1268635cb3311b8ccf412246f`.
- Cloudflare : Worker `mrxpronos-play` **version 50**, identifiant de version `fa6517ff-a161-4fab-a414-c770f19dc971`, 100 % du trafic.
- Contrôles avant fusion : tests Telegram/Worker verts, contrôle des 25 ressources graphiques et de leurs SHA-256 vert, matrice Chromium **5 largeurs × 7 sections** réussie.
- Le test navigateur vérifie explicitement que Lucky Wheel a le bouton au-dessous de l'image, que le titre promotionnel XP ne déborde pas, que le portrait et le badge sont espacés, que le pourcentage ne possède plus de cercle décoratif, et que la navigation reste lisible.
- Contrôle réel du canari 10 % : 6 réponses V50 sur 60, état de santé Telegram/D1 positif.
- Contrôle après bascule à 100 % : **60 réponses V50 sur 60**, bot, identité, signature et base D1 toujours opérationnels.
- Liaisons `BOT_TOKEN`, `WEBHOOK_SECRET`, `DB` et `DEV_MODE` préservées par héritage strict.
- Recette visuelle et tactile spécifique Telegram Android/iPhone : encore à faire depuis les appareils. Le rendu local Chromium ne reproduit pas toutes les particularités des WebViews mobiles.
