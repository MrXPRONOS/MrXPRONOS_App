# Mr XPRONOS Play — Cloudflare V1

## Statut au 18 novembre 2026

- **Worker déployé** : `mrxpronos-play`
- **Adresse prévue** : https://mrxpronos-play.cinecanaux-xpronos.workers.dev
- **D1 créé** : `mrxpronos-play-v1` (`59d4ecbf-21bc-4221-8909-0213737ab029`).
- **Maquettes Figma** : https://www.figma.com/design/RlWwR9KutRVBRGhuELDH1N
- **Backend + UI** : `worker.js`. Interface embarquée dans le Worker pour cette première version.
- **Icônes** : emplacements visuels réservés, en attente de l'import des PNG officiels.
- **État des paiements et tokens** : désactivés / aucun MRXP émis.

**Limitation :** le déploiement a été accepté par Cloudflare, mais l'URL publique n'a pas pu être testée de bout en bout depuis cet environnement. La connexion Telegram n'est pas activée tant que les secrets et BotFather ne sont pas configurés. Ne pas considérer la V1 comme production prête pour des récompenses financières.

## Configurer Telegram

Dans Cloudflare → Workers & Pages → Worker `mrxpronos-play` → Settings → Variables and Secrets :

1. Créer `BOT_TOKEN` (Secret) : jeton du bot fourni par **@BotFather**.
2. Créer `WEBHOOK_SECRET` (Secret) : chaîne aléatoire longue, uniquement lettres/chiffres/_/-, à garder privée.
3. Conserver le binding D1 `DB` pointant vers `mrxpronos-play-v1`.

Dans BotFather, associer au bot l'URL de la Mini App. Pour les réponses à `/start`, configurer `setWebhook` avec :

- URL : `https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook`
- `secret_token` : identique à `WEBHOOK_SECRET`
- `allowed_updates` : `["message"]`.

**Ne jamais publier les secrets dans GitHub ni dans un chat.** La requête setWebhook est à lancer depuis un outil sûr, après avoir défini le jeton.

## Fonctionnement du jeu

- Le compteur augmente immédiatement dans le navigateur pour le tap-to-earn.
- Les actions sont sauvegardées dans **IndexedDB** + **Telegram DeviceStorage** lorsque disponible.
- Ce sont deux stockages sur le même appareil : supprimer toutes les données de l'application ou réinitialiser le téléphone peut supprimer les deux.
- Le backend vérifie l'identité via Telegram Mini App `initData`, HMAC-SHA256.
- Les actions locales restent **provisoires** jusqu'à confirmation par D1.
- Les demandes de synchronisation sont autorisées avec un intervalle minimum de **12 heures**.
- Première synchronisation admissible : prochain créneau **00 h / 12 h UTC** après la création du compte.
- Si un créneau est manqué, les actions restent locales et sont proposées à la prochaine ouverture/connexion, toujours sous réserve du délai minimum.
- Chaque lot a un `batch_id` unique, enregistré dans `sync_receipts` : une nouvelle tentative ne donne pas deux fois les XP.
- La roue est déterminée pour chaque joueur et chaque jour côté serveur et récupérée pour un horizon de 15 jours lors de la connexion.
- Les XP gratuits ne sont ni des tokens on-chain ni une promesse d'argent.

## Limites et tests indispensables avant ouverture publique

- **Anti-triche** : les tapotages hors ligne ne peuvent pas prouver qu'ils viennent d'un humain. La V1 applique des limites d'énergie et de cadence, mais des protections supplémentaires sont nécessaires avant un airdrop ou des récompenses monétaires.
- **Stockage** : panne ou effacement simultané de tous les stockages locaux peut faire perdre des actions non synchronisées.
- **Quotas** : vérifier le volume de requêtes et les écritures D1 en conditions de charge.
- **Tests indispensables** : installation via BotFather, /start et menu Mini App, 2 comptes Telegram, sauvegarde puis reconnexion, fermeture en cours de jeu, 12 h de délai, synchronisation en double, jeu hors ligne, changement de jour UTC, erreurs réseau.
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

