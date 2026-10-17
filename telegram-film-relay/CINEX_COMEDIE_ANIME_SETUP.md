# CinéX Comédie et CinéX Anime — préparation des tests

Ces deux nouveaux projets ont des workflows séparés et uniquement manuels. Ils ne sont pas encore intégrés au workflow automatique CinéX classique + Désir.

## Canaux à créer

### CinéX Comédie

- Canal public : **CinéX Comédie 😂** ; identifiant suggéré **@CineXComediefr** (disponibilité à vérifier).
- Canal privé : **CinéX Comédie 🍿 | Vidéothèque Privée**.

Description du privé :

> 😂🎬 CINÉX COMÉDIE — VIDÉOTHÈQUE
>
> 🍿 Ton espace 100 % comédies et fous rires !
> 🤣 Films comiques africains, français et internationaux.
> 🎥 De nouvelles découvertes pour des moments de détente.
> 🔥 Prépare le popcorn, le spectacle commence !

### CinéX Anime

- Canal public : **CinéX Anime 🌸** ; identifiant suggéré **@CineXAnimeFR** (disponibilité à vérifier).
- Canal privé : **CinéX Anime 🎌 | Épisodes & Films**.

Description du privé :

> 🌸🎬 CINÉX ANIME — VIDÉOTHÈQUE
>
> 🎌 Ton univers 100 % animés en VF & VOSTFR.
> ⚔️ Action • Aventure • Fantastique • Romance.
> 📺 Épisodes, saisons et films d'animation.
> 🍿 Retrouve tes histoires et découvre de nouvelles séries !

### CinéX Désir — description publique

> 🔞🌹 CINÉX DÉSIR
>
> ❤️ Romance, passion, séduction et films sensuels.
> 🌙 Des histoires intenses et des découvertes réservées aux adultes.
> 🎥 Retrouve les affiches et accède aux films.
> 🔞 Exclusivement pour les 18 ans et plus.

## Variables GitHub requises

Settings → Secrets and variables → Actions → Variables

| Variable | Valeur |
|---|---|
| COMEDIE_SOURCE_CHANNEL | Identifiant Telegram @... de la source autorisée de comédies |
| COMEDIE_PUBLIC_CHANNEL | @identifiant réel du nouveau canal public Comédie |
| COMEDIE_PRIVATE_CHANNEL | ID numérique -100... de la vidéothèque Comédie |
| ANIME_SOURCE_CHANNEL | Identifiant Telegram @... de la source autorisée d'animés |
| ANIME_PUBLIC_CHANNEL | @identifiant réel du nouveau canal public Anime |
| ANIME_PRIVATE_CHANNEL | ID numérique -100... de la vidéothèque Anime |

Ces identifiants ne sont pas encore fournis ; le système les exige avant de contacter Telegram.

Variables facultatives :
- COMEDIE_MIRROR_CHANNEL et ANIME_MIRROR_CHANNEL : non nécessaires, la destination par défaut est @Torrent9SeriesFilms.
- CINEX_FILM_FOLDER_URL : non nécessaire si le lien reste https://t.me/addlist/ZmW4vfwcrMAwNzJk.

**Aucun nouveau secret** si les secrets existants sont en place : TG_API_ID, TG_API_HASH, TG_SESSION_STRING (ou TG_STRING_SESSION), et le bot déjà utilisé par CinéX Désir (DESIR_BOT_TOKEN, sinon FOOTBALL_NEWS_BOT_TOKEN, sinon TELEGRAM_BOT_TOKEN).

N'ajoutez pas de nouvelles variables de type droits attestés ou publication activée : les workflows fonctionnent avec un déclenchement manuel explicite.

## Permissions

Ajouter le bot existant comme administrateur **avec Publier des messages** dans les deux canaux publics et, idéalement, dans les deux vidéothèques privées pour les boutons bleus des publicités. Le compte utilisateur des sessions doit avoir accès aux sources, pouvoir publier dans les vidéothèques privées et transférer vers @Torrent9SeriesFilms.

## Premier test manuel

1. Ouvrir GitHub Actions et le workflow **CinéX Comédie - Test isolé** ou **CinéX Anime - Test isolé**.
2. Choisir publish=false et max_films=1 : diagnostic sans publication.
3. Après vérification, choisir publish=true et max_films=1 : un film réel maximum.
4. Confirmer la vidéo privée, l'affiche publique (bouton vert film + bouton rouge dossier), et son **transfert natif avec attribution** sur @Torrent9SeriesFilms.
5. Le deuxième film, lors d'une exécution ultérieure, déclenchera le compteur publicitaire indépendant de la catégorie.
6. Une fois tous les tests validés, seulement alors, envisager l'intégration au workflow programmé toutes les deux heures.

## Sécurité, état, et indépendance

- Workflows : .github/workflows/cinex-comedie-test.yml et .github/workflows/cinex-anime-test.yml ; **aucune programmation automatique**.
- Script : telegram-film-relay/film_relay/category_runner.py.
- Historiques : telegram-film-relay/state/comedie_state.json et telegram-film-relay/state/anime_state.json (films, miroirs et pubs séparés).
- Supports : photos avec ou sans légende, fichiers MKV sans limite de durée, MP4, vidéo sans affiche.
- Publication privée et publique comme nouveau message ; seul le message public avec son lien est transféré à Torrent9, en conservant « Transféré de ».
- Maximum 2 nouveaux films par exécution ; premier essai limité à 1 film.
- Les pubs Mr XPRONOS suivent une rotation après chaque 2 nouveaux films, séparément pour chaque catégorie.
- Les workflows partagent le verrou de compte Telegram utilisé par CinéX, et s'arrêtent en cas de restriction Telegram.
