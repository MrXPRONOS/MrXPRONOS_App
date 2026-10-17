# CinéX Comédie et CinéX Anime — installation et sources

## Mise en production du 17 octobre 2026

Comédie et Anime sont maintenant ajoutés **au même workflow GitHub programmé toutes les 2 heures** que CinéX Classique, Désir et Découverte :
`.github/workflows/telegram-film-relay.yml`.

Ordre : découverte → 2 films classiques + pub selon compteur → 2 Désir + pub → 2 Comédie + pub → 2 Anime + pub → sauvegarde des cinq historiques.

**Sources déjà configurées en valeurs par défaut :**
- Comédie : `@comexflex`, `@filmcomplets`.
- Anime : `@orak_dessinanime`.

Le compte Telegram ne rejoint pas automatiquement les sources et ne copie pas les publications protégées contre le transfert. Les cinq catégories/états indépendants (classique, Désir, Comédie, Anime, Découverte) restent protégés contre les doublons.

**Ajouter à l'avenir des sources sans modifier GitHub :**

| Catégorie | Variable GitHub Actions pour une liste de @canaux |
|---|---|
| CinéX classique — films | `CINEX_SOURCE_CHANNELS` ou `FILM_SOURCE_CHANNELS` |
| CinéX classique — séries | `SERIES_SOURCE_CHANNELS` (même relais classique, pas de canal public Série autonome) |
| CinéX Désir | `DESIR_SOURCE_CHANNELS` |
| CinéX Comédie | `COMEDIE_SOURCE_CHANNELS` |
| CinéX Anime | `ANIME_SOURCE_CHANNELS` |

Les variables historiques singulières `COMEDIE_SOURCE_CHANNEL`, `ANIME_SOURCE_CHANNEL`, `DESIR_SOURCE_CHANNEL` et `DESIR_EXTRA_SOURCE_CHANNEL` restent prises en charge. On peut utiliser les deux formes ensemble ; les doublons sont supprimés automatiquement.

Format des variables de liste : `@canal_un,@canal_deux,@canal_trois` (virgules, espaces, points-virgules, retours à la ligne ou tableau JSON acceptés). **Maximum 12 sources par groupe**, avec des pauses de sécurité entre les canaux.

Les variables de destination **`COMEDIE_PUBLIC_CHANNEL`, `COMEDIE_PRIVATE_CHANNEL`, `ANIME_PUBLIC_CHANNEL` et `ANIME_PRIVATE_CHANNEL` restent indispensables**. Le programme refuse de publier si un identifiant est manquant ou incorrect. Le même bot existant est réutilisé.

Les workflows séparés de test manuel restent disponibles pour un essai ciblé ou une simulation, avec le même verrou Telegram. Ils ne lancent pas de travail automatiquement.


Les deux projets possèdent également des workflows de test manuel, mais ils sont désormais intégrés au workflow automatique unifié.

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

Les sources indiquées par l'utilisateur sont préconfigurées dans le code ; les identifiants de destinations proviennent des variables GitHub existantes et sont contrôlés avant de contacter Telegram.

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
