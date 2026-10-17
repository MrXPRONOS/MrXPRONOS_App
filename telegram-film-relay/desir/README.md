# CinéX Désir — relais indépendant

## Automatisation unifiée (17 octobre 2026)

Le programme Désir ne possède plus de workflow indépendant. Il est exécuté à la suite de la découverte et des **deux films classiques + publicité** par le seul workflow `.github/workflows/telegram-film-relay.yml`, toutes les deux heures : **00:17, 02:17, 04:17... UTC / Togo**.

- **Étape 1 :** découverte de canaux publics, envoyés uniquement dans Messages enregistrés (sans ajout automatique comme sources).
- **Étape 2 :** jusqu'à deux films CinéX classiques, puis publicité correspondante dans les destinations classiques, selon le compteur des deux films.
- **Étape 3 :** jusqu'à deux films CinéX Désir au total depuis `@Filmromatique` et `@g_romanticfilm`, affiches publiques `@CineXDesirfr`, vidéos dans le privé et attribution par transfert natif dans `@Torrent9SeriesFilms`. Après **deux films Désir supplémentaires**, la publicité suivante (Actu Foot, Pronos Live VIP, Coupons du Jour) est publiée dans Désir public, transférée à Torrent9 et publiée dans la vidéothèque privée.
- Les deux cycles publicitaires sont **indépendants**, avec reçus `state/state.json` (classique) et `state/desir_state.json` (Désir). Chaque destination conserve aussi son propre compteur.
- Les pubs publiques ont de véritables boutons URL bleus. Pour la vidéothèque Désir, si le bot n'a pas les droits d'administrateur, une affiche et un lien texte cliquable sont envoyés avec le compte utilisateur ; ajouter le bot comme administrateur au privé permet de conserver les vrais boutons bleus.
- Un cycle qui ne trouve pas deux nouveaux films ne poste pas de publicité supplémentaire. Les programmes ne contournent aucune protection anti-copie.
- Les 3 états sont fusionnés et sauvegardés dans une seule mise à jour GitHub, même après un échec partiel, pour éviter les doublons et les notifications répétées.

**Seul workflow de publication programmé :** [CineX - Découverte, Films et Désir](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/telegram-film-relay.yml). Les workflows autonomes de découverte et de Désir ont été supprimés.


## Flux

1. Sources prévues : `@Filmromatique` et `@g_romanticfilm` (affiches et vidéos MKV/MP4, même sans description). Pour les MKV, pas de filtre de durée ni de taille. La source supplémentaire est facultative en cas d'indisponibilité, aucune protection anti-transfert n'est contournée, et les droits de redistribution restent nécessaires.
2. Vidéothèque privée : identifiant numérique de `DESIR_PRIVATE_CHANNEL`. La vidéo et éventuellement l'affiche y sont envoyées comme **nouveaux messages**, sans mention « Transféré de ».
3. Canal public : `@CineXDesirfr`. L'affiche est envoyée avec le lien privé et deux véritables boutons Telegram : **vert** « 🎬 REGARDER LE FILM » et **rouge** « 🔥 PLUS DE FILMS ? REJOINS LA TEAM ! », pointant vers `https://t.me/addlist/ZmW4vfwcrMAwNzJk`. Ce dossier remplace l'ancien deuxième lien d'invitation à la vidéothèque.
4. Miroir : `@Torrent9SeriesFilms`. Le message public (affiche, lien et attribution Telegram) est **transféré nativement** depuis CinéX Désir. Aucune vidéo privée n'est transférée vers ce miroir. Le lien du film **et** celui du dossier sont écrits dans la légende et subsistent si les boutons ne sont pas reproduits par le client Telegram.

## GitHub

Workflow unique : `.github/workflows/telegram-film-relay.yml`. Test manuel : `workflow_dispatch` ; avec `publish=true`, au maximum **deux films classiques et deux films Désir au total** par exécution, suivis des publicités dues après deux films de chaque catégorie. Avec `publish=false`, les publications sont ignorées et seule la découverte s'exécute. Le workflow possède le verrou partagé `mrx-telegram-personal-account`.

Secrets déjà utilisés :
- `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` (ou `TG_STRING_SESSION`).
- `DESIR_BOT_TOKEN` ; sinon le bot existant `FOOTBALL_NEWS_BOT_TOKEN` ou `TELEGRAM_BOT_TOKEN`.
- Le lien `DESIR_PRIVATE_INVITE_LINK` n'est plus nécessaire pour les boutons publics. Le dossier de films commun peut être remplacé via la variable facultative `CINEX_FILM_FOLDER_URL`.

Variables :
- `DESIR_SOURCE_CHANNEL` (première source, défaut `@Filmromatique`).
- `DESIR_EXTRA_SOURCE_CHANNEL` (deuxième source, défaut `@g_romanticfilm` ; **aucune variable supplémentaire obligatoire**).
- `DESIR_PUBLIC_CHANNEL` (défaut `@CineXDesirfr`).
- `DESIR_MIRROR_CHANNEL` (défaut `@Torrent9SeriesFilms` ; **aucune variable supplémentaire nécessaire**).
- `DESIR_PRIVATE_CHANNEL` : identifiant privé obligatoire `-100...`.

La publication exige les permissions de publication du bot dans le canal public et du compte personnel dans Torrent9 ; le programme refuse de copier des fichiers protégés contre le transfert ou des destinations incorrectes. Les reçus des deux sources ainsi que des canaux privé/public/miroir sont indépendants de ceux du relais CinéX classique et persistent dans `state/desir_state.json` ; les transferts manquants sont rattrapés sans nouveau téléchargement vidéo.

## Messages enregistrés — découverte

Le même workflow recherche des canaux et envoie **un seul message HTML récapitulatif par passage** lorsqu'il trouve de nouveaux canaux, et aucun message s'il n'y a pas de nouveauté. Chaque ligne présente le nom du canal **en gras**, un lien cliquable `https://t.me/...` distinct et le nombre de paires affiche/vidéo détectées. Les retours à la ligne sont de vrais caractères de fin de ligne ; pas de séquence littérale `\\n`. La recherche est limitée à 16 canaux analysés par cycle pour rester dans la taille d'un message Telegram. Les accusés des canaux déjà notifiés sont préservés dans `state/discovered_channels.json`.

## Premier test réel — 17 octobre 2026

[GitHub Actions #38995244214](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38995244214) : **succès**.

- Source vidéo #812, affiche source #811.
- Film privé #5.
- Affiche et lien publics [@CineXDesirfr/18](https://t.me/CineXDesirfr/18).
- Transfert Telegram natif [@Torrent9SeriesFilms/2377](https://t.me/Torrent9SeriesFilms/2377).
- Reçus enregistrés dans le dépôt.

La taille et le type du film transféré au privé ne sont pas inscrits dans ce compte rendu ; consulter les messages Telegram pour les détails.
