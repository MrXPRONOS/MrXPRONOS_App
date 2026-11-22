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
La production 52 conserve la clé privée ECDSA P-256 en secret `CINE_DELIVERY44_PRIVATE_KEY` (DER PKCS#8 en base64). Le compte 44 détient uniquement la clé publique de vérification et n'a pas besoin de secret partagé. Les requêtes sont signées sur `timestamp + '.' + corps JSON exact`, avec un timestamp de 60 secondes maximum et un reçu D1 anti-répétition.

Le `bot_token` est transmis exclusivement dans une requête HTTPS signée et ne doit jamais être stocké ou journalisé. Le client 52 utilise le quota D1 partagé avant l'appel, et revient au circuit 52 uniquement lorsque 44 renvoie un échec garanti avant tout appel à Telegram.

## Migration
1. Déployer le Worker et sa D1 isolée sur 44.
2. Vérifier que le secret privé `CINE_DELIVERY44_PRIVATE_KEY` existe uniquement sur 52 et que la clé publique compilée sur 44 correspond.
3. Vérifier `GET /health` et que `POST /internal/v1/copy` non signé renvoie 403.
4. Activer `CINE_DELIVERY44_ENABLED=1` dans `wrangler.jsonc` sur 52 après validation de la CI.
5. Tester avec une vidéo autorisée et vérifier les reçus dans D1 sur les deux comptes.
6. Activer progressivement ; conserver le traitement 52 comme retour arrière **uniquement avant l'acceptation d'un envoi**.
7. Ne jamais rejouer automatiquement un `copyMessage` dont le résultat est inconnu.

## Attention
Ce service ne doit pas être présenté comme «instantané» sans mesures réelles entre le clic, l'update, la DB, le Worker 44 et la réception Telegram. Toute bascule production nécessite les tests et la revue des quatre familles de livraison.
