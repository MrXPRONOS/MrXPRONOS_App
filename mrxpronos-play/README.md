# Mr XPRONOS Play — Cloudflare V1

## V2 Phase 2 — Profils évolutifs et collection (19 novembre 2026)

La page Profil possède une collection complète de **11 avatars africains**, un badge de rang et des étoiles temporaires, des animations légères, ainsi que le détail du prochain rang (XP confirmés et défis de maîtrise). Un joueur peut conserver et afficher un ancien avatar débloqué, sans changer son véritable niveau. Le choix est sauvegardé dans D1 et vérifié par le Worker grâce à l'identité Telegram signée. Le mode automatique sélectionne le meilleur avatar débloqué.

**Migration D1 additive nécessaire avant déploiement :** `migrations/003_avatar_profiles.sql` ; nouveaux endpoints privés `GET /api/profile` et `POST /api/profile/avatar`. Les icônes définitives, les cartes partageables, les crédits MRXP et les boosts ne font pas encore partie de cette phase.

Documentation : [PROFILES_V2_PHASE2.md](PROFILES_V2_PHASE2.md).

## V2 Phase 1 — Progression hybride et hub Jeux (19 novembre 2026)

**État courant :** la Mini App adopte les niveaux officiels basés sur les XP confirmés et les défis de maîtrise, avec préservation du niveau acquis sous la V1. L'ancien onglet **ROUE** devient **JEUX** : Lucky Wheel reste jouable, Snake est annoncé comme prochain jeu mais **n'est pas encore intégré**. Les 30 défis de maîtrise et leurs sept passages de rang sont calculés par le Worker ; le profil les affiche. **Migration D1 additive requise avant déploiement** : voir `migrations/002_hybrid_progression.sql`.

Documentation fonctionnelle complète : [PROGRESSION_V2_PHASE1.md](PROGRESSION_V2_PHASE1.md).

**Note historique :** les sections antérieures évoquant les niveaux calculés seulement par les tapotages, l'affichage de la photo Telegram et les missions sans récompense décrivent d'anciennes versions et ne reflètent plus le code actuel.


## État de connexion Telegram — vérifié le 18 novembre 2026

- **Worker déployé** : `mrxpronos-play` (Cloudflare Workers, sans Telegram Serverless)
- **Bot Telegram configuré** : [@MrXpronosPlayBot](https://t.me/MrXpronosPlayBot).
- **Webhook vérifié** : `https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook`.
- **Bouton de lancement** : `🎮 Ouvrir l’application` sous le message `/start` → la Mini App Cloudflare.
- **Commandes visibles** : `/start` pour le public ; `/start` et `/admin` uniquement pour l’administrateur. `/play` reste un alias compatible.
- **Adresse prévue** : https://mrxpronos-play.cinecanaux-xpronos.workers.dev
- **D1 créé** : `mrxpronos-play-v1` (`59d4ecbf-21bc-4221-8909-0213737ab029`).
- **Maquettes Figma** : https://www.figma.com/design/RlWwR9KutRVBRGhuELDH1N
- **Backend + UI** : `worker.js`. Interface embarquée dans le Worker pour cette première version.
- **Icônes** : 58 PNG / 58 WebP présents dans GitHub, visuels WebP déjà intégrés dans la Mini App.
- **État des paiements et tokens** : désactivés / aucun MRXP émis.

**Vérification :** Cloudflare confirme que les deux secrets `BOT_TOKEN` et `WEBHOOK_SECRET` sont présents sans exposer leurs valeurs. Le bot `MrXpronosPlayBot` possède le webhook attendu et un bouton de type `web_app`. La Mini App a déjà été ouverte dans un navigateur de test ; l'ouverture depuis le compte personnel Telegram reste à contrôler par l'utilisateur. La V1 ne doit pas être considérée prête pour des récompenses financières.

## Accueil Telegram public et administration privée

- **Public** : le menu des commandes expose seulement `/start`. Le message de bienvenue comporte un unique bouton **🎮 Ouvrir l’application** qui ouvre la Mini App. Les jeux, missions, roue, XP et profil restent dans la Mini App.
- **Administrateur** : seul le compte Telegram figurant dans la table D1 `bot_admins` peut utiliser `/admin`, voir les statistiques et modifier les textes du bot (accueil, description du profil et bio courte). Les contrôles sont effectués côté Worker à partir de `message.from.id` / `callback_query.from.id` et des droits D1 ; aucun identifiant administrateur n'est codé en clair dans GitHub.
- **Avant Start** : la rubrique Telegram « Que peut faire ce bot ? » utilise `setMyDescription`, et la bio courte `setMyShortDescription`. Ce sont des descriptions Telegram, pas des messages automatiquement envoyés au joueur.
- **Commandes Telegram** : `/start` par défaut et pour tous les chats privés, `/start` + `/admin` exclusivement dans le chat privé du compte administrateur. Les anciennes commandes non adaptées ne sont plus affichées dans le menu public une fois la synchronisation des commandes Telegram effectuée.
- **Menu Telegram** : menu global remis au mode commandes ; l'ouverture du jeu se fait via le bouton affiché après `/start`. Les anciennes touches inline dans l'historique des messages ne peuvent pas être effacées rétrospectivement.
- **Configuration native** : le premier `/start` ou `/admin` de l'administrateur peut déclencher en arrière-plan la synchronisation des commandes et du webhook (y compris les `callback_query`), sans exposer le secret. Le statut du processus est dans D1 `telegram_setup_status`, entrée `onboarding-public-admin-v1`.
- **Réglages administrateur** : les textes personnalisables sont dans `bot_settings`, les changements de texte attendus dans `bot_admin_pending` avec expiration de 10 minutes. Aucun mot de passe Telegram, secret ou token ne doit être publié dans le dépôt.

## Telegram — configuration en place

Les secrets et le webhook sont déjà installés. Ne créez pas un deuxième webhook sur un autre service : Telegram n'en utilise qu'un à la fois. Les instructions suivantes sont à utiliser uniquement pour une réinstallation ou une rotation de jeton.

Dans Cloudflare → Workers & Pages → Worker `mrxpronos-play` → Settings → Variables and Secrets :

1. Vérifier `BOT_TOKEN` (Secret) : jeton du bot fourni par **@BotFather**.
2. Vérifier `WEBHOOK_SECRET` (Secret) : chaîne aléatoire longue, uniquement lettres/chiffres/_/-, à garder privée.
3. Conserver le binding D1 `DB` pointant vers `mrxpronos-play-v1`.

Dans BotFather, associer au bot l'URL de la Mini App. Pour les réponses à `/start`, configurer `setWebhook` avec :

- URL : `https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook`
- `secret_token` : identique à `WEBHOOK_SECRET`
- `allowed_updates` : `["message", "callback_query"]` (pour les boutons de gestion privés).

**Ne jamais publier les secrets dans GitHub ni dans un chat.** La requête setWebhook est à lancer depuis un outil sûr, après avoir défini le jeton.

## Présentation du bot Telegram — texte officiel

**Description (« Que peut faire ce bot ? »)**

> 🎮 Mr XPRONOS Play : tapote pour gagner des XP Points, tourne la roue et accomplis des missions gratuites. Suis ton niveau et tes récompenses dans la Mini App. Les XP n’ont pas de valeur monétaire.

**Description courte du profil**

> 🎮 Tapote, gagne des XP, tourne la roue et accomplis des missions gratuites !

La V1.2 déploie les textes via les méthodes Telegram `setMyDescription` et `setMyShortDescription`. Ne pas stocker le token Telegram dans GitHub. L'exécution est vérifiable dans la table D1 `telegram_setup_status` par l'entrée `bot-profile-description-v1` (état `VERIFIED`).

## Ajustements de l'écran de jeu (V1.2)

- Les six raccourcis de chaque côté de la pièce passent à **28 × 28 px** (26 × 26 px pour les petits écrans), légèrement inférieurs aux icônes de navigation du bas (34 × 34 px).
- Les cartes des raccourcis ont été réduites et remontées ; les boutons restent utilisables.
- Un libellé **« TAPOTER POUR GAGNER »** accompagne la pièce, suivi du rappel **+1 XP / 1 énergie**.

## Fonctionnement du jeu

- Le compteur augmente immédiatement dans le navigateur pour le tap-to-earn.
- Les actions sont sauvegardées dans **IndexedDB** + **Telegram DeviceStorage** lorsque disponible.
- Ce sont deux stockages sur le même appareil : supprimer toutes les données de l'application ou réinitialiser le téléphone peut supprimer les deux.
- Le backend vérifie l'identité via Telegram Mini App `initData`, HMAC-SHA256.
- Les actions locales restent **provisoires** jusqu'à confirmation par D1.
- Les demandes de synchronisation sont autorisées avec un intervalle minimum de **12 heures**.
- **Première synchronisation : immédiate** dès que le joueur est connecté à Telegram et qu'il possède des XP provisoires. Après une synchronisation réussie, le serveur impose un délai minimum de **12 heures** avant la suivante.
- Les gains non synchronisés restent stockés localement. Le bouton de synchronisation reste utilisable lorsqu'il y a des gains en attente : pendant un délai de 12 h, il indique précisément la prochaine date possible sans forcer le serveur.
- Chaque lot a un `batch_id` unique, enregistré dans `sync_receipts` : une nouvelle tentative ne donne pas deux fois les XP.
- La roue est déterminée pour chaque joueur et chaque jour côté serveur et récupérée pour un horizon de 15 jours lors de la connexion.
- Les XP gratuits ne sont ni des tokens on-chain ni une promesse d'argent.

## Limites et tests indispensables avant ouverture publique

- **Anti-triche** : les tapotages hors ligne ne peuvent pas prouver qu'ils viennent d'un humain. La V1 applique des limites d'énergie et de cadence, mais des protections supplémentaires sont nécessaires avant un airdrop ou des récompenses monétaires.
- **Stockage** : panne ou effacement simultané de tous les stockages locaux peut faire perdre des actions non synchronisées.
- **Quotas** : vérifier le volume de requêtes et les écritures D1 en conditions de charge.
- **Tests indispensables** : /start et menu Mini App sur vrai compte Telegram, 2 comptes Telegram, sauvegarde puis reconnexion, fermeture en cours de jeu, 12 h de délai, synchronisation en double, jeu hors ligne, changement de jour UTC, erreurs réseau.
- **Images** : remplacer les boîtes réservées par les PNG nommés du catalogue `mrxpronos-play/assets-manifest.json` lorsqu'ils sont présents sur GitHub.
- **Figma** : six écrans éditables sont créés (Tap, Roue, Missions, Profil, Amis, NFT), mais l'alignement pixel par pixel avec les rendus d'origine n'est pas encore certifié, notamment tant que les vrais éléments graphiques ne sont pas intégrés.

## Arborescence

```text
mrxpronos-play/
  worker.js                 # Worker Cloudflare et frontend
  schema.sql                # D1 à restaurer
  README.md                 # Ce guide
  assets-manifest.json      # Inventaire de 50 images
  README_ASSETS.md          # Noms des ressources
  tools/import_assets.py    # Import des ressources
```


## Lancement utilisateur

1. Ouvrir https://t.me/MrXpronosPlayBot dans Telegram.
2. Appuyer sur **Démarrer**, ou envoyer `/start` (l'alias `/play` reste accepté mais n'est pas visible dans le menu public).
3. Dans le message de bienvenue, toucher **🎮 Ouvrir l’application**.
4. La page se charge depuis Cloudflare. Les XP sont locaux avant validation, avec intervalle minimum de 12 h entre synchronisations.

**Vérification automatique réalisée :** la réponse de `getWebhookInfo` concorde avec l'URL Cloudflare et celle de `getChatMenuButton` confirme `type=web_app`. Aucun webhook préexistant différent n'a été écrasé. Le Cron temporaire de configuration a été désactivé.

## Vérification de la reprise du 19 novembre 2026

- Accueil : texte du jeu avec XP, roue, missions, progression et avertissement sur la valeur virtuelle des XP.
- Navigation : un unique bouton public « 🎮 Ouvrir l’application » ; seuls les administrateurs D1 voient les outils privés.
- Commandes : `/start` public, `/admin` réservé au compte autorisé, alias `/play` accepté sans publicité dans le menu.
- Sécurité : secret du webhook, contrôle de `from.id` et du chat privé, vérification D1 de l’administrateur pour les commandes et callbacks.
- Édition : accueil, description et bio courte, délai de 10 minutes, annulation `/cancel`.
- Tests automatiques : démarrage public, autorisations, changements de texte, statistiques, annulation et configuration Telegram.
- Les anciennes touches de messages déjà envoyés restent éventuellement visibles dans l’historique Telegram ; seules les commandes/menu et nouveaux messages sont configurables.

## Gestion du jeu et identité Telegram — 19 novembre 2026

- **Nom** : le prénom et le nom viennent des `initData` signées par Telegram (champ `user`), validées par HMAC côté Worker. La Mini App affiche `players.display_name` après chaque connexion plutôt qu'un nom de marque. Un changement de nom Telegram est pris en compte à la prochaine ouverture authentifiée.
- **Photo de profil** : endpoint privé `GET /api/avatar`, réservé à l'identité Telegram authentifiée. Le Worker demande `getUserProfilePhotos` puis `getFile` à Telegram, sans exposer le token du bot. Le frontend privilégie la photo personnelle Telegram ; en cas d'absence de photo, de restriction de confidentialité ou de défaillance, il tente `initDataUnsafe.user.photo_url` sur des domaines Telegram autorisés, puis affiche les initiales de l'utilisateur.
- **Panneau privé** : `/admin` → statistiques, textes du bot, état du webhook Telegram, réglages du jeu. Aucun autre identifiant que celui inscrit dans `bot_admins` ne peut modifier ces réglages.
- **Réglages du jeu** : l'administrateur peut activer/suspendre le tapotage, la Lucky Wheel, le bonus quotidien et l'affichage des missions. Les flags sont stockés dans D1 `bot_settings`. Le bootstrap les charge et le client les rafraîchit toutes les minutes. Le serveur refuse les nouvelles tentatives de synchronisation utilisant un module désactivé : le client garde les XP provisoires jusqu'à réactivation. Les réglages n'effacent aucune donnée.
- **Attention** : les missions de tapotage montrent leur progression mais leurs bonus indicatifs ne sont pas encore distribués séparément côté serveur. Seul le bonus quotidien (+100 XP), les tapotages (+1 XP) et les gains XP de la roue sont actuellement comptabilisés par le backend.
- **Vérifications automatisées** : tests de la signature HMAC, du nom complet, de l'avatar associé uniquement au compte signé, de l'isolation administrateur, des réglages et des suspensions côté serveur. Un essai manuel sur Telegram avec deux vrais comptes reste requis pour certifier l'expérience mobile native.

## V1.4 — Missions récompensées et photo personnelle Telegram (19 novembre 2026)

- Missions **simultanées et indépendantes** : premier lancement de la Mini App (+25 XP, une seule fois), paliers de 50/200/500 tapotages confirmés (+40/+75/+150 XP, chacun une seule fois), abonnement au canal principal `@mrxpronosfr` (+100 XP) et à Actu Foot `@actufoot_mrxp` (+100 XP). Les paliers de tapotages sont cumulés sur la vie du compte et dépendent des tapotages **confirmés sur le serveur** ; les XP provisoires nécessitent la synchronisation avant réclamation.
- Les **missions d'adhésion** restent visibles tous les jours jusqu'à leur validation. La vérification appelle l'API Telegram `getChatMember` pour le compte connecté et **exige que @MrXpronosPlayBot soit administrateur de chacun des canaux**. Une réponse API négative, un compte qui n'a pas rejoint ou un bot sans droits ne créditent aucun XP. Après validation, chaque mission rapporte ses XP une seule fois.
- Le bouton privé `/admin` → `📢 Canaux des missions` vérifie si les canaux sont accessibles et si le bot est administrateur. Les URLs initiales sont `https://t.me/mrxpronosfr` et `https://t.me/actufoot_mrxp`; en cas de modification de leur identifiant, adapter les constantes et vérifier les droits avant ouverture générale.
- Les récompenses sont stockées dans la nouvelle table D1 `mission_claims` (clé unique `user_id,mission_key`). Les deux étapes d'attribution (inscription et crédit des XP) sont exécutées en un batch transactionnel D1 avec la condition `changes()=1` : réessayer la même mission ne crédite pas deux fois.
- Les missions sont visibles dans l'écran Missions, avec leur progression, leurs boutons `Rejoindre` puis `Vérifier mon adhésion`, et l'état terminé. Le bonus quotidien préexistant (+100 XP) reste géré par `daily_claims` et la synchronisation habituelle, sans double crédit.
- Le profil privilégie la photo Telegram signée dans `initData.user.photo_url` lorsqu'elle est disponible, puis le serveur `/api/avatar` via `getUserProfilePhotos`. Le joueur peut toucher `Actualiser ma photo`. **Telegram peut masquer la photo selon les réglages de confidentialité** : dans ce cas, les initiales personnelles restent visibles, sans logo générique.
- **Avant déploiement** : appliquer la migration D1 `CREATE TABLE IF NOT EXISTS mission_claims(...)` et son index. Vérifier `getChatMember` sur les deux canaux en tant qu'administrateur du bot. Tester deux utilisateurs réels : non-abonné, abonné, double tentative, progression des tapotages et affichage photo.

## Lot 6 (51–58) — intégration graphique

Les nouveaux visuels sont présents dans `mrxpronos-play/assets/06-game-states/`. Le Splash Screen 53 est volontairement opaque ; les autres visuels sont transparents. Le jeu affiche les icônes de missions et de canal Telegram, utilise le symbole d'énergie vide, et peut afficher l'écran de lancement avec son spinner CSS. Le catalogue global est dans `assets-manifest.json`.


## Avatars africains officiels — dix rangs approuvés (19 novembre 2026)

Dix avatars **individuels** de héros africains ont été vérifiés puis ajoutés en **PNG RGBA source transparent 1254 × 1254** et en **WebP transparent optimisé 768 × 768**. Ils évoluent avec les niveaux selon la table suivante :

| Rang | Niveaux actuels | Portrait WebP |
|---|---|---|
| Recrue | 1 | `assets/07-rank-avatars/rank-01-recrue.webp` |
| Éclaireur | 2 | `assets/07-rank-avatars/rank-02-eclaireur.webp` |
| Combattant | 3–4 | `assets/07-rank-avatars/rank-03-combattant.webp` |
| Sentinelle | 5 | `assets/07-rank-avatars/rank-04-sentinelle.webp` |
| Chevalier | 6–9 | `assets/07-rank-avatars/rank-05-chevalier.webp` |
| Élite | 10–14 | `assets/07-rank-avatars/rank-06-elite.webp` |
| Maître | 15–19 | `assets/07-rank-avatars/rank-07-maitre.webp` |
| Champion | 20–29 | `assets/07-rank-avatars/rank-08-champion.webp` |
| Légende | 30–39 | `assets/07-rank-avatars/rank-09-legende.webp` |
| Mythique | 40–49 | `assets/07-rank-avatars/rank-10-mythique.webp` |
| **Souverain MX** | **50 et au-delà** | **En attente de génération** |

Le nom public du joueur reste authentifié par Telegram, mais **sa photo Telegram n'est plus utilisée comme avatar** : le portrait de son rang est affiché sur sa fiche Profil et dans l'en-tête du jeu.

**Important :** cette intégration est strictement graphique. La progression hybride XP + défis, les crédits MRXP, les boosts et la carte de partage seront développés séparément. La correspondance des images suit pour l'instant les niveaux calculés à partir des tapotages dans `level()`.

Les **58 ressources graphiques historiques** restent conservées dans `assets-manifest.json` et les dix avatars disposent d'un manifeste indépendant `avatars-manifest.json`, avec leurs dimensions, poids et empreintes SHA-256. Les tests de non-régression couvrent les vingt fichiers PNG/WebP, les dix correspondances de niveaux et le rang restant avec son emblème MX provisoire.
