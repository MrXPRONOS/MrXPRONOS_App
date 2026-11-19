# Mr XPRONOS Play — Cloudflare V1

## État de connexion Telegram — vérifié le 18 novembre 2026

- **Worker déployé** : `mrxpronos-play` (Cloudflare Workers, sans Telegram Serverless)
- **Bot Telegram configuré** : [@MrXpronosPlayBot](https://t.me/MrXpronosPlayBot).
- **Webhook vérifié** : `https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook`.
- **Bouton Menu configuré** : `🎮 Jouer` → la Mini App Cloudflare.
- **Commandes disponibles** : `/start` et `/play`.
- **Adresse prévue** : https://mrxpronos-play.cinecanaux-xpronos.workers.dev
- **D1 créé** : `mrxpronos-play-v1` (`59d4ecbf-21bc-4221-8909-0213737ab029`).
- **Maquettes Figma** : https://www.figma.com/design/RlWwR9KutRVBRGhuELDH1N
- **Backend + UI** : `worker.js`. Interface embarquée dans le Worker pour cette première version.
- **Icônes** : 50 PNG / 50 WebP présents dans GitHub, visuels WebP déjà intégrés dans la Mini App.
- **État des paiements et tokens** : désactivés / aucun MRXP émis.

**Vérification :** Cloudflare confirme que les deux secrets `BOT_TOKEN` et `WEBHOOK_SECRET` sont présents sans exposer leurs valeurs. Le bot `MrXpronosPlayBot` possède le webhook attendu et un bouton de type `web_app`. La Mini App a déjà été ouverte dans un navigateur de test ; l'ouverture depuis le compte personnel Telegram reste à contrôler par l'utilisateur. La V1 ne doit pas être considérée prête pour des récompenses financières.

## Accueil Telegram public et administration privée

- **Public** : le menu des commandes expose seulement `/start`. Le message de bienvenue comporte un unique bouton **🎮 Démarrer Mr XPRONOS Play** qui ouvre la Mini App. Les jeux, missions, roue, XP et profil restent dans la Mini App.
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
- `allowed_updates` : `["message"]`.

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
2. Appuyer sur **Démarrer**, ou envoyer `/start` (également `/play`).
3. Dans le message de bienvenue, toucher **🎮 Jouer maintenant** ou le bouton menu **🎮 Jouer**.
4. La page se charge depuis Cloudflare. Les XP sont locaux avant validation, avec intervalle minimum de 12 h entre synchronisations.

**Vérification automatique réalisée :** la réponse de `getWebhookInfo` concorde avec l'URL Cloudflare et celle de `getChatMenuButton` confirme `type=web_app`. Aucun webhook préexistant différent n'a été écrasé. Le Cron temporaire de configuration a été désactivé.
