# Ciné X — Tendances Ciné Radar et canaux privés dédiés

## Fonctionnement
- Ciné Radar collecte déjà des tendances officielles **TMDB, AniList et Simkl** dans Cloudflare D1.
- Nouveau flux de métadonnées: `GET /api/radar/trends?limit=12` (titres, catégories, classements et indicateur d'autorisation ; **aucun média ni session Telegram**).
- L'automate interroge ce flux. Il conserve seulement des tendances **autorisées par le propriétaire dans Ciné Radar**, classées dans les 25 premières positions et reconnues **sans ambiguïté** dans les fiches/vidéos déjà présentes chez Ciné X.
- Films : contrôle la fiche du canal `@CineXFilms_vf` et le film déjà copié dans `TG_PRIVATE_CHANNEL`.
- Séries : réutilise `state/series_catalog.json`, la bibliothèque existante et `@seriesvf_cinex`.
- Animés : réutilise `state/anime_catalog.json`, `ANIME_PRIVATE_CHANNEL` et `@CineXAnimeFR`.
- Pour un titre éligible : le **compte propriétaire** crée un canal privé dédié (ou retrouve celui déjà créé), récupère son lien d'invitation, retransmet l'affiche, organise les saisons et les épisodes disponibles, et enregistre chaque étape.
- **Le bot** modifie la fiche principale (bouton `VOIR LE CONTENU / LES SAISONS` + dossier partagé) et l'épingle **seulement après vérification du transfert**. Si le bot ne peut pas épingler par manque de droits, la session propriétaire prend la main, sans essayer de contourner un ralentissement Telegram.
- Une seule nouvelle vidéothèque par passage, 12 épisodes transférés au maximum par passage, **30 secondes de pause entre opérations**, 60 secondes après création d'un canal. Les saisons incomplètes ne sont pas présentées comme complètes.
- Les anciennes vidéos publiques peuvent être supprimées par le bot ou, en cas de limitation explicitement confirmée, par le propriétaire ; l'archive est vérifiée en premier, comme avant.

## Activation et garde-fous
`.github/workflows/cinex-trending-private.yml` s'exécute à **02 h 35 UTC / heure du Togo** et accepte un lancement manuel. La **simulation est le réglage par défaut**.

Après validation des résultats, ajouter la variable GitHub Actions `CINEX_TRENDS_ENABLED=true`. Les secrets Telegram existants sont réutilisés. Pas de token dans le code, pas de stockage des fichiers films sur GitHub ou Cloudflare.

Les tendances ne sont **pas** des autorisations de distribution. Le champ `authorized` de Ciné Radar désigne une approbation éditoriale du propriétaire ; les droits de diffusion doivent aussi exister. L'automatisation conserve les films ou séries introuvables, ambigus, protégés ou incomplets pour vérification humaine.

## Architecture et limites
- Un titre n'est candidat à un canal privé dédié que s'il apparaît **dans les tendances et dans une bibliothèque Ciné X déjà administrée**. Pas de collecte opaque de nouveaux films, pas de découverte de sources inconnues.
- Une fiche qui n'a pas été publiée par le bot configuré peut être impossible à éditer. Dans ce cas, le canal dédié demeure privé et l'annonce est différée.
- Le lien d'invitation donne accès au canal privé ; contrairement à un lien `t.me/c`, il est utilisable par une personne qui n'est pas encore membre.
- Les transferts utilisent les permissions Telegram existantes et ne contournent pas les restrictions de contenu protégé.
- Les comptes peuvent être limités par Telegram même avec des pauses de 30 à 60 secondes ; aucun intervalle ne garantit zéro restriction.
- L'état `state/trending_private.json` est sauvegardé via GitHub Actions et fusionné avec précaution en cas de commits concurrents. Les médias déjà transmis sont récupérés par leur identifiant pour éviter les doublons après une panne.

## Vérifications locales
```bash
cd telegram-film-relay
python -m unittest discover -s tests -p 'test_trending_private.py' -v
python -m film_relay.trending_private            # simulation, aucun canal créé
python -m film_relay.trending_private --apply    # nécessite CINEX_TRENDS_ENABLED=true
```
