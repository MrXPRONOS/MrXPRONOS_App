# CinéX Désir — relais indépendant

## Flux

1. Source autorisée : `@Filmromatique` (affiches et vidéos MKV/MP4, même sans description). Pour les MKV, pas de filtre de durée ni de taille.
2. Vidéothèque privée : identifiant numérique de `DESIR_PRIVATE_CHANNEL`. La vidéo et éventuellement l'affiche y sont envoyées comme **nouveaux messages**, sans mention « Transféré de ».
3. Canal public : `@CineXDesirfr`. L'affiche est envoyée avec le lien vers la vidéo privée dans sa légende et un véritable bouton Telegram vert « Regarder le film ».
4. Miroir : `@Torrent9SeriesFilms`. Le message public (affiche, lien et attribution Telegram) est **transféré nativement** depuis CinéX Désir. Aucune vidéo privée n'est transférée vers ce miroir. Le lien écrit dans la légende subsiste si les boutons ne sont pas reproduits par le client Telegram.

## GitHub

Workflow : `.github/workflows/telegram-film-desir.yml`. Test manuel : `workflow_dispatch` ; avec `publish=true` la publication réelle est limitée à **1 film par exécution**. Une simulation sans publication reste possible. Le workflow possède le verrou partagé `mrx-telegram-personal-account`.

Secrets déjà utilisés :
- `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` (ou `TG_STRING_SESSION`).
- `DESIR_BOT_TOKEN` ; sinon le bot existant `FOOTBALL_NEWS_BOT_TOKEN` ou `TELEGRAM_BOT_TOKEN`.
- `DESIR_PRIVATE_INVITE_LINK` : lien d'invitation privé.

Variables :
- `DESIR_SOURCE_CHANNEL` (défaut `@Filmromatique`).
- `DESIR_PUBLIC_CHANNEL` (défaut `@CineXDesirfr`).
- `DESIR_MIRROR_CHANNEL` (défaut `@Torrent9SeriesFilms` ; **aucune variable supplémentaire nécessaire**).
- `DESIR_PRIVATE_CHANNEL` : identifiant privé obligatoire `-100...`.

La publication exige les permissions de publication du bot dans le canal public et du compte personnel dans Torrent9 ; le programme refuse de copier des fichiers protégés contre le transfert ou des destinations incorrectes. Les reçus des canaux privé/public/miroir sont indépendants de ceux du relais CinéX classique et persistent dans `state/desir_state.json` ; les transferts manquants sont rattrapés sans nouveau téléchargement vidéo.

## Premier test réel — 17 octobre 2026

[GitHub Actions #38995244214](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38995244214) : **succès**.

- Source vidéo #812, affiche source #811.
- Film privé #5.
- Affiche et lien publics [@CineXDesirfr/18](https://t.me/CineXDesirfr/18).
- Transfert Telegram natif [@Torrent9SeriesFilms/2377](https://t.me/Torrent9SeriesFilms/2377).
- Reçus enregistrés dans le dépôt.

La taille et le type du film transféré au privé ne sont pas inscrits dans ce compte rendu ; consulter les messages Telegram pour les détails.
