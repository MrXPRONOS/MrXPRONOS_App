# Ciné Radar — annuaire Telegram simple

L'objectif de Ciné Radar est volontairement minimal : **choisir Films, Séries ou Animés → sélectionner un canal public → l'ouvrir**. Aucune inscription, aucun profil, aucun favori, aucune copie/partage du lien du canal, aucune notification personnalisée.

## Pour l'utilisateur
- Bot Telegram : trois catégories avec les liens directs, huit canaux par page si nécessaire.
- Mini App : trois catégories, recherche par nom, cartes avec les vraies images publiques des canaux lorsque Telegram en fournit, et deux actions **Aperçu** / **Ouvrir**.
- Aperçu : nom, photo du canal, photo d'une publication publique si disponible, courte description et un unique bouton d'ouverture.
- Sans photo publique, une icône neutre apparaît : aucune image n'est inventée.

## Infrastructure légère
- `radar-lean.mjs` : messages Telegram, catalogue public et vérification automatique des liens cassés.
- `app-page.mjs` : interface responsive sans authentification ni fonction personnalisée.
- `channel-preview.mjs` : récupération des seules métadonnées et images publiques via des liens Telegram ; **aucune photo ni vidéo n'est téléchargée dans D1**.
- `worker.mjs` : accès web, webhook et lecture de l'état de découverte GitHub.
- `schema.sql` : données de découverte, canaux, cache limité (une ligne par canal), état du webhook et des contrôles de liens.

Le script GitHub de découverte quotidienne conserve les trois motifs techniques : photo avec légende → vidéo, photo → texte → vidéo et fichier MKV. La synchronisation Cloudflare a lieu toutes les quatre heures. Les liens confirmés définitivement morts lors de deux contrôles indépendants sont retirés. Les erreurs HTTP 429, les indisponibilités temporaires et l'absence d'aperçu public ne suffisent pas à supprimer un canal.

Les aperçus publics sont mis en cache au maximum sept jours lorsqu'ils sont disponibles, avec une seule ligne D1 par canal. Le code ne crée aucune ligne par visiteur ni clic. Un entretien automatique supprime les cache obsolètes et les anciennes découvertes rejetées.

## Tests
- `cinecanaux/tests/radar-lean.test.mjs` et `cinecanaux/tests/channel-preview.test.mjs`.
- `cinecanaux/tests/live-smoke.mjs` teste le vrai catalogue Cloudflare.
- GitHub Actions : `.github/workflows/cine-radar-v2-ci.yml` et `.github/workflows/cine-radar-live-smoke.yml`.

La suppression des anciennes tables de favoris, de parrainage et de données personnelles a été effectuée sur la base D1 utilisée par le Worker. Le compte administrateur existant reste conservé séparément, sans interface administrative publique.

Mini App : https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app

Bot : https://t.me/CineRadarFr_Bot


## Radar des tendances et canaux principaux (novembre 2026)

Trois canaux publics administrés par le bot :
- Films : https://t.me/CineXFilms_vf
- Séries : https://t.me/seriesvf_cinex
- Animés : https://t.me/CineXAnimeFR

Migration D1 : migrations/008_trending_radar.sql. Module : trend-radar.mjs. Les fichiers vidéo ne sont jamais téléchargés, copiés, stockés ni retransmis par ce module.

### Sources et fréquence

- TMDB pour les films et séries de la semaine : configurer TMDB_API_KEY (v3) ou TMDB_READ_ACCESS_TOKEN comme secret du Worker Cloudflare cinecanaux-bot. Un secret GitHub Actions de même nom ne configure pas automatiquement Cloudflare.
- AniList pour les animés tendance via l'API GraphQL publique.
- Le Cron existant 0 */6 * * * (UTC) exécute à 06:00 UTC une vérification quotidienne. Le rafraîchissement réussi par catégorie doit dater d'au moins 72 heures pour se reproduire. Les sources en échec sont réessayées au passage suivant.

### Référencement des titres

Le webhook accepte message, callback_query, channel_post et edited_channel_post. Le bot reçoit seulement les **nouvelles** publications de ses canaux (il ne peut pas relire rétroactivement leur historique via la Bot API). Il conserve uniquement la légende, le type de média, l'identifiant du message et son lien Telegram. Ajouter le **titre exact dans la légende de la vidéo** ou le nom de son fichier ; une affiche isolée ne prouve pas qu'un titre complet est disponible.

L'affiche cliquable du nouveau panneau n'apparaît que lorsqu'une correspondance vidéo assez sûre et une autorisation explicite de diffusion ont été enregistrées. Elle ouvre la publication Telegram exacte, pas simplement la page du canal.

Le score de classement combine récence, tendances et clics agrégés sans enregistrer l'identité des spectateurs. Un titre souvent consulté peut rester visible plus longtemps.

### Commandes privées réservées au propriétaire

- /start : ouvrir la conversation privée avec Cine Radar.
- /actualiser : démarrer manuellement une collecte de tendances.
- /tendances : afficher les recommandations indexées et leurs identifiants.
- /autoriser ID_DU_TITRE : confirmer uniquement les titres pour lesquels on possède les droits nécessaires pour diffuser la vidéo.

Les suggestions sont envoyées au propriétaire par message privé, pas dans ses Messages enregistrés : l'API Telegram des bots ne peut pas écrire directement dans cet espace personnel. Aucun téléchargement ou recherche de copies non autorisées n'est effectué.

API publique : GET /api/radar?kind=films|series|animes&limit=24. Le nouveau catalogue s'ajoute à l'annuaire des canaux existant.


## À l'affiche = épingles des trois canaux officiels

Migration : migrations/009_pinned_showcase.sql. Module : pinned-showcase.mjs.

- La bannière animée « Le cinéma, à découvrir » conserve ses images décoratives.
- La rangée « À l'affiche » n'affiche **que des publications image/vidéo enregistrées depuis les trois canaux officiels** ; aucune affiche décorative n'est présentée à la place d'un vrai lien. Chaque vignette ouvre directement le message public d'origine.
- L'accueil suit l'ordre : bannière cinéma → À l'affiche → recherche → Explore par univers (boutons horizontaux compacts) → À découvrir.
- Le panneau précédent « Nouveautés disponibles dans nos canaux » est supprimé de l'accueil pour limiter le défilement.
- Les vues du canal figurent dans « À découvrir », comme auparavant.
- Le nombre de clics reste agrégé, sans identité utilisateur ; il contribue au classement des images avec leur ancienneté.

### Récupération des épingles Telegram

L'API Telegram getChat fournit **uniquement le message épinglé le plus récent** du canal. Le Worker demande cette information lors du premier chargement (au maximum une fois par heure et par canal), puis toutes les six heures à travers une tâche Cron existante. Les épinglages transmis comme événements Telegram sont ajoutés automatiquement.

Pour afficher **les autres messages déjà épinglés** :
1. Ouvrir le canal officiel Films, Séries ou Animés et sélectionner un ancien message épinglé avec son image ou la miniature de sa vidéo.
2. Utiliser « Transférer » vers **@CineRadarFr_Bot**, en conversation privée depuis le compte propriétaire enregistré dans Ciné Radar.
3. Le bot vérifie l'origine et l'identifiant stable du canal, enregistre l'affiche et confirme sa prise en compte.
4. L'image apparaît ensuite dans « À l'affiche » et ouvre **la publication d'origine** du canal, non le message privé du bot.

Si le transfert est interdit ou qu'un message ne contient ni photo ni miniature vidéo exploitable, il ne peut pas être ajouté par cette méthode. Le bot ne télécharge, ne conserve ni ne republie les fichiers vidéo : seuls les petits visuels et métadonnées de publication sont utilisés. Respecter les autorisations de diffusion des visuels et contenus.

Routes : GET /api/pinned-showcase ; GET /assets/pin-cover/{films|series|animes}/{message_id}.jpg ; POST /api/pinned-click.


## Promotions croisées discrètes dans « À découvrir » (novembre 2026)

Les trois canaux choisis explicitement pour la bande « À découvrir aussi » sont :
- Actualité du football : https://t.me/actufoot_mrxp
- Actualité des cryptomonnaies : https://t.me/ActuCrypto24H
- Pronostics : https://t.me/mrxpronosfr

Le bloc apparaît dans la liste « À découvrir », après quatre canaux sur mobile et six en affichage large. Il ne se place pas entre « À l'affiche » et la recherche. Sur mobile, les cartes se parcourent horizontalement pour éviter une section publicitaire trop haute. Les promotions sont signalées et les pronostics portent une mention de responsabilité (18+).

Module : partner-promotions.mjs. Routes publiques :
- GET /api/partner-promos : trois descriptions et titres issus de l'aperçu public Telegram lorsqu'il est joignable ; textes explicatifs de secours sinon.
- GET /assets/promo-avatar/{actufoot_mrxp|ActuCrypto24H|mrxpronosfr}.jpg : photo Telegram réelle, relayée sur le domaine de Ciné Radar, avec validation stricte des formats et limite de taille.

Les liens sont figés sur la liste blanche de ces trois canaux. Aucun annonceur externe, cookie, script publicitaire tiers ou suivi individuel n'est installé. Si la photo n'est pas accessible, un pictogramme de catégorie reste visible sans être présenté comme une photo réelle.
