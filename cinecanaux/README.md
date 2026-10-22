# CinéCanaux — Telegram Bot sur Cloudflare

Service: `cinecanaux-bot` · D1: `cinecanaux-directory`

## Fonctionnalités
Menu Films/Séries/Animés par genres, recherche sur canaux approuvés, propositions modérées, vérification d'abonnement aux canaux officiels via `getChatMember`. Aucun lien de diffusion ne doit être publié sans autorisation.

## Mise en service Telegram
1. Créer le bot avec [@BotFather](https://t.me/BotFather), conserver le jeton privé.
2. Dans Cloudflare Workers > `cinecanaux-bot` > Settings > Variables and Secrets, ajouter deux secrets: `TELEGRAM_TOKEN` (jeton BotFather) et `TELEGRAM_WEBHOOK_SECRET` (chaîne aléatoire d'au moins 32 caractères, lettres/chiffres/_/-).
3. Configurer le webhook Telegram vers `https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram` avec `secret_token` égal à `TELEGRAM_WEBHOOK_SECRET`. Ne jamais mettre les secrets sur GitHub.
4. Ajouter le bot comme administrateur de chacun de tes canaux obligatoires. Insérer les canaux dans D1:
```sql
INSERT INTO owned_channels(chat_id,title,link) VALUES ('@nomducanal','Nom du canal','https://t.me/nomducanal');
```
5. Insérer des canaux validés uniquement après vérification des droits:
```sql
INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed)
VALUES ('Canal autorisé','https://t.me/exemple','Films du domaine public','films','action','approved',1);
```
6. Tester `/health` et `/start` depuis Telegram.

## Déploiement
`npx wrangler deploy` depuis le dossier `cinecanaux/`. Schéma initial dans `schema.sql` ; exécuter les migrations uniquement si nécessaire.

## Limitations
Recherche dans la base D1 uniquement; découverte externe automatisée et inspection historique des vidéos non intégrées. Le bot n'est pas utilisable dans Telegram tant que les secrets et le webhook ne sont pas configurés. Éviter les doublons et les canaux sans droits de diffusion.
