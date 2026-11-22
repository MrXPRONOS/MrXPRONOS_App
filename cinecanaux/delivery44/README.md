# Ciné Radar — service de livraison Cloudflare 44

Moteur de copies Telegram à déployer sur le compte Cloudflare **ananiolivier44@gmail.com**.

## Périmètre
- Un seul bot public : `@CineRadarFr_Bot`.
- Le webhook Telegram, le catalogue, les droits, les limitations et les files de travaux restent sur le compte 52 pendant la migration.
- Ce Worker ne possède **aucun webhook** et **aucune tâche Cron**.
- Il accepte exclusivement des requêtes signées HMAC-SHA256 du Worker 52 et appelle `copyMessage`.
- Il ne télécharge ni ne stocke les vidéos.
- La base D1 44 stocke uniquement les identifiants de requête et les états de livraison.

## Sécurité
L'appelant fournit `x-cine-time` (timestamp Unix en millisecondes) et `x-cine-signature` (HMAC-SHA256 hexadécimal sur `timestamp + '.' + corps JSON exact`), avec `CINE_BRIDGE_SECRET` partagé dans les secrets Workers. La requête comprend un `request_id` stable de type `classic:123`, `method: 'copyMessage'`, `bot_token` temporaire et `payload` Telegram. Le token transmis par HTTPS ne doit jamais être journalisé, stocké dans D1 ni renvoyé dans une réponse.

## Migration
1. Déployer le Worker et sa D1 isolée sur 44.
2. Configurer le même `CINE_BRIDGE_SECRET` sur les Workers 44 et 52.
3. Vérifier `GET /health` et que `POST /internal/v1/copy` non signé renvoie 403.
4. Ajouter une fonction d'envoi distant avec feature flag dans les quatre processeurs du dépôt `cinecanaux` (un par un).
5. Tester avec une vidéo autorisée et vérifier les reçus dans D1 sur les deux comptes.
6. Activer progressivement ; conserver le traitement 52 comme retour arrière **uniquement avant l'acceptation d'un envoi**.
7. Ne jamais rejouer automatiquement un `copyMessage` dont le résultat est inconnu.

## Attention
Ce service ne doit pas être présenté comme «instantané» sans mesures réelles entre le clic, l'update, la DB, le Worker 44 et la réception Telegram. Toute bascule production nécessite les tests et la revue des quatre familles de livraison.
