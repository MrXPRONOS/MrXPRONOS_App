# Mr XPRONOS Play — Phases 4 et 5 : cartes officielles, Amis et Missions
**Date :** 20 novembre 2026  
**Déploiement ciblé :** Worker `mrxpronos-play` V51.  
**Branche :** `feat/mrxp-phase4-5-share-social-missions`

## Phase 4 — Deux cartes officielles reconstruites
- Dessin Canvas **1080 × 1080** et **1080 × 1920** avec géométries indépendantes.
- Fond bleu nuit dégradé, bordure dorée discrète, portrait centré découpé et délimité.
- Nom / rang signé, badge officiel correspondant au **niveau confirmé** et non au portrait cosmétique sélectionné.
- Trois valeurs vérifiées par serveur : XP confirmés, missions réussies et maîtrises.
- Mention horodatée serveur, renvoi au lien de vérification et avertissement « points virtuels sans valeur monétaire ».
- Les anciennes images pleine carte 84/85 restent dans le catalogue et sont contrôlées, mais ne sont pas superposées sous les statistiques.
- Si un fichier de badge officiel ne peut pas être chargé, le dessin fait appel à un emblème de secours MX ; le portrait est obligatoire comme avant.
- L'option « masquer mon nom » est toujours appliquée côté serveur, sans divulguer l'identifiant Telegram ni l'URL de session.
- Actions conservées : création signée `POST /api/share/profile`, prévisualisation, enregistrement PNG, partage natif du fichier, lien de vérification Telegram et copie de la preuve (durée : 30 jours).
- Icône photographique vectorielle, simple et lisible à 24 px, en remplacement des sombres miniatures des cartes dans le formulaire de partage.

## Phase 5 — Amis
- Suppression du tableau de bord fictif : aucun classement, statistique ou gain par parrainage non effectivement mesuré.
- Une invitation concise avec l'icône Amis existante, un bouton **Partager le jeu** et un bouton **Copier le lien**.
- Les deux actions utilisent exclusivement `https://t.me/MrXpronosPlayBot`, jamais `location.href` ni `tgWebAppData`.
- Précision visible : **aucune récompense de parrainage** n'est actuellement attribuée.

## Phase 5 — Missions et harmonisation
- Section MRXP resserrée, montants confirmés maintenus, barème dans un panneau dépliable.
- Défis du jour présentés sur trois lignes compactes, montants à droite.
- Bonus hebdomadaire rendu par un libellé court et une barre alimentée exclusivement par `wallet.weekly` signé côté serveur, sans inventer de crédits.
- Missions permanentes lisibles : une seule coche d'achèvement par ligne ; barre de progression uniquement pour les missions de tapotage.
- Boutons de missions et d'actualisation accessibles au toucher.
- MRXP Legends : icône existante, titre sur une ligne, bouton sous le contenu et annonce « collection à venir, non émise ».
- Conservation des règles métier : taux XP, crédits, portefeuilles, collections, boosts, antihacks, signatures et horaires de synchronisation inchangés.

## Contrôles avant publication
- Tests Node : cartes, confidentialité, usages des API, mission/solde, 50 niveaux et 11 rangs.
- Tests Chromium : **7 sections × 5 largeurs**, puis contrôle de la page Amis/Missions/partage à 320, 360, 375, 390 et 430 px.
- Génération effective par Canvas de deux PNG 1080 × 1080 et 1080 × 1920 avec données de test longues ; dimensions, contenus, textes et marges de sécurité contrôlés. Échantillons PNG stockés comme artefacts GitHub Actions.
- Contrôles du Worker, des 25 ressources V2 et des sept nouvelles icônes.
- Canari Cloudflare à 10 %, contrôle du bot et de D1, puis bascule à 100 % uniquement en cas de réussite.
- **À terminer manuellement :** contrôle tactile sur appareils réels Telegram Android et iOS et publication d'une carte depuis chaque terminal.

## Publication — terminée le 20 novembre 2026

- **GitHub :** [PR #510](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/510) fusionnée dans `main`, commit `e5e19e2f45b110d4c981a3fdfd0bbe16d4397510`.
- **Cloudflare :** Worker `mrxpronos-play` — **version 51**, identifiant `a2a89f83-3edf-41d2-aa13-cbd3b5d42427`, **100 % du trafic**.
- **Tests métier :** 84/84 réussis, dont deux nouveaux contrôles spécifiques aux cartes officielles et au partage/bonus des missions.
- **Ressources :** les 25 assets V2 existants vérifiés avec leurs empreintes SHA-256. Avatar servi par l'endpoint public vérifié comme fichier WebP.
- **Tests de rendu :** les sept sections contrôlées à 320/360/375/390/430 px ; la phase 5 sur Amis/Missions/Partage testée également aux mêmes cinq tailles, sans débordement. Export Canvas effectivement exécuté des cartes **1080 × 1080** et **1080 × 1920** avec statistiques fictives, titres longs, dates et badge, toutes les vérifications réussies.
- **Canari 10 % :** 4/70 réponses reçues en V51, tous les critères réussis.
- **Après bascule 100 % :** **70/70 réponses publiques V51**, connexion Telegram valide, bot correspondant, base D1 et route publique des avatars opérationnels.
- **Bindings hérités sans changement :** `BOT_TOKEN`, `WEBHOOK_SECRET`, `DB`, `DEV_MODE`.
- **Recette réelle restante :** vérifier directement dans Telegram sur Android/iPhone le rendu, l'enregistrement et le partage d'une carte générée avec un vrai profil. Les tests automatisés ne remplacent pas cette vérification de terrain.

**Attention :** ne partage jamais l'URL de lancement contenant `tgWebAppData`. Le bouton Amis transmet uniquement `https://t.me/MrXpronosPlayBot`, tandis que le bouton de preuve partage séparément la page de vérification signée.

