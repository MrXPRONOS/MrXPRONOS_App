# CinéX — vérification finale des Lots 1 et 2

Ce dossier définit **les preuves nécessaires**, distinctes des tests hors ligne.
Les fichiers de sauvegarde ne contiennent **aucune invitation Telegram en clair**.

## Lot 1 — Secours et rétention

- Les sept couples publics/secours doivent apparaître dans `state/rescue_channels.json`. Ce fichier atteste seulement les identités et leurs empreintes SHA-256, **pas** l'accessibilité.
- L'audit en lecture seule `python -m film_relay.rescue_links_runtime --output <fichier-temporaire-0600>` doit confirmer **7 liens actifs** et **0 manquant**. Les liens expirés, épuisés, révoqués ou non vérifiables sont bloqués. Ne jamais publier les invitations ni le fichier temporaire.
- Pour le secours Animés déjà connu mais inaccessible à la session, rétablir l'accès au **canal portant exactement son identifiant sauvegardé**, via le propriétaire/administrateur Telegram ; **ne pas créer de doublon** ni remplacer son ID supposément.
- Le nettoyage public (workflow `cinex-public-video-retention-24h.yml`) doit être observé sur un horaire ou `workflow_dispatch apply=true`, jamais une exécution `push` (tests uniquement). Vérifier le résumé : nombre de vidéos expirées, effectivement supprimées, non supprimées, erreurs **0**, pour six catégories. Seules les nouvelles vidéos avec `#CINEX_VIDEO_24H_V1` âgées de 24 h sont éligibles. Les anciennes vidéos, affiches, stock privé et secours restent intacts.
- Les droits déclarés `CINEX_ARCHIVE_ENABLED`, `CINEX_ARCHIVE_DELETE_APPROVED`, `CINEX_RIGHTS_VERIFIED` restent obligatoires pour l'application réelle. Ne pas désactiver ces garde-fous.

## Lot 2 — Boutons, vidéothèques et téléchargement

- `cinex-unified-preflight.yml` exécute le prévol **sans publication ni suppression** lors des changements de code sur `main`. Il doit vérifier **les six** catégories actives, droits de publication des bots, invitations Secours, dossier Telegram, stock central approuvé, bot D1 et `cine_delivery_enabled=1`.
- Sur chaque nouveau post public (photo **et** vidéo), contrôler en Telegram l'existence de quatre boutons avec les liens exacts : voir, télécharger via CineRadar, secours, dossier.
- Sur chaque nouvelle affiche de vidéothèque, contrôler exactement trois boutons : canal principal, dossier, téléchargement réel.
- Pour un film / épisode représentatif **de chaque catégorie**, confirmer le reçu D1 réel, l'identité du fichier stocké, le fonctionnement du deep link du bot CineRadar et l'absence de duplication à la reprise. Les tests hors ligne ne prouvent pas ces étapes.
- La préparation Anime V2 dédiée est vérifiée par `cinex-anime-v2-readiness.yml`. Le résultat JSON doit contenir `ready_to_publish=true`, `blockers=[]`, et `live_bot_checks=permissions_validated` avant d'affirmer son exploitation réelle. Les sources et droits ne sont jamais déduits ni contournés.

## Terminologie des résultats

- **Terminé (code)** : fusion dans `main` + CI verte.
- **Validé (live)** : reçu GitHub Actions/Telegram avec opération réelle correspondante.
- **Partiel** : tests réussis mais opération live non démontrée.
- **Bloqué** : droits, compte, secret, session ou destination non autorisés.

Le succès d'une exécution `push` ne vaut **jamais** preuve de nettoyage après 24 h, de lien Telegram fonctionnel, ni de téléchargement effectif.
