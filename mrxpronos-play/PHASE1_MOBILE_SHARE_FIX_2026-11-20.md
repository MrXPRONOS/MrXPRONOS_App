# Mr XPRONOS Play — Phase 1 : correctifs prioritaires

**Date :** 20 novembre 2026  
**Périmètre :** partage public Telegram, débordements mobiles, missions, barre de navigation, cadre de partage PNG.  
**Branche/PR :** `fix/mrxp-phase1-mobile-layout-share` / [PR #502](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/502).

## 1. Invitation publique sécurisée

Le bouton **Amis → Partager Mr XPRONOS Play** ne transmet plus `location.href` : cette adresse pouvait contenir les paramètres de session `tgWebAppData` et ne constituait pas un lien d'invitation réutilisable.

Il construit désormais un lien de partage Telegram à partir du **seul lien public** `https://t.me/MrXpronosPlayBot`. Les chemins de repli ouvrent le partage dans un nouvel onglet ou copient le lien public. Le partage **Lien Telegram** et **Copier la preuve** des cartes de profil sont deux actions distinctes et continuent à utiliser la preuve signée dédiée, valide 30 jours.

Aucune donnée de connexion Telegram, aucun jeton de session, aucune valeur de `initData` n'est utilisée dans la nouvelle invitation.

## 2. Missions

- Le pictogramme de validation ajouté dans la zone `.reward` est borné à 17×17 px (15×15 px sur écrans très étroits).
- L'illustration de mission dans `.empty-icon` est bornée à 36×36 px (32×32 px sur très petit écran).
- Les cartes de missions utilisent une grille pour réserver la zone de récompense à droite sans écraser le texte central.
- La ligne « Bonus quotidien » possède une grille à deux colonnes, car elle n'a pas de pictogramme principal.
- Les textes, les barres de progression et les boutons ne doivent pas se superposer.
- Le raccourci NFT Legends conserve une icône officielle existante, avec le bouton « Voir » repositionné.

## 3. Sécurité de la mise en page mobile

- Largeurs des cartes limitées à la largeur réellement disponible ; éléments flexibles autorisés à rétrécir.
- Navigation inférieure devenue opaque pour masquer la page qui défilait visuellement derrière.
- Espace réservé en bas de l'application, y compris avec la zone de sécurité du téléphone.
- Bandeau Lucky Wheel et promotion XP disposés sans compression excessive du texte.
- Contrôles de partage et aperçu de profil contraints à la largeur du conteneur.
- Pourcentage de progression contenu dans son pictogramme actuel ; la refonte du composant est prévue séparément en **phase 3**.

## 4. Carte officielle : suppression des textes doubles

Les ressources de fond V2 `84-profile-card-square` et `85-profile-card-vertical` restent enregistrées et leurs SHA-256 restent vérifiés. Elles contiennent toutefois des titres/cadres pré-dessinés qui entraient en collision avec les statistiques réellement générées par Canvas. La phase 1 n'en superpose plus le contenu au Canvas dynamique.

Les données restent issues du **snapshot serveur signé** ; le nom et le rang ne peuvent pas déborder horizontalement et les mentions légales du format carré restent à l'intérieur du visuel. La refonte esthétique complète des cartes reste à effectuer en **phase 4**.

## 5. Validation

- Suite Node/Telegram : **81 tests de non-régression réussis**, dont deux nouveaux tests de partage sans session et d'encadrement des illustrations.
- Test Chromium, écran de **320, 360, 375, 390 et 430 px**, sur les **sept sections** : Accueil, Jeux, Missions, Amis, Profil, Boutique et NFT. Les 35 parcours de géométrie ont été validés sur la branche.
- Contrôles spécifiques à la taille de l'image de récompense, au partage, à la carte Lucky Wheel, à NFT Legends et aux boutons de profil.
- Contrôle de toutes les ressources V2 dans le manifeste et cohérence avec la décision de ne pas redessiner les anciens fonds de carte derrière les textes dynamiques.

## 6. Hors périmètre

La refonte détaillée du tableau Accueil / Jeux (phase 2), de l'identité et de la progression du Profil (phase 3), des cartes officielles (phase 4) et de l'écran Amis / harmonisation générale (phase 5) suivra séparément.

**Aucun changement** dans les règles de crédits MRXP, les montants XP, le comportement des boosts, les protections d'achat, le calcul des rangs, la signature des preuves HMAC ou la fréquence de synchronisation.
