# Anti-doublon Telegram promotions — octobre 2026

## Portée
- Promotions XPVIP communes, bonus bookmakers, guides bookmakers et promotions par jour.
- Deux canaux de promotions définis par `TELEGRAM_CHAT_ID` et `TELEGRAM_CHAT_ID_SECONDARY`.
- Le canal ActuFoot `FOOTBALL_NEWS_CHAT_ID` n'est pas visé.
- Les coupons BSD V2 utilisent leur propre système de déduplication.

## Base de données (déployée)
Supabase : table `public.telegram_promo_deliveries`, migration `telegram_promo_delivery_dedup`.
Clé unique : (`campaign`, `delivery_day`, `chat_id`).
RLS activée ; accès accordé au seul rôle `service_role`.

Le script réserve un envoi avant l'appel Telegram. Si la réservation existe déjà,
le message n'est pas renvoyé. En cas d'erreur Telegram, la réservation reste
présente, car on ne peut pas savoir si Telegram a accepté l'envoi.
Une correction manuelle dans la base ne doit intervenir **qu'après vérification**
de l'historique réel du canal.

## GitHub : vérifications indispensables
Dans Settings > Secrets and variables > Actions :
- Secrets existants requis : `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_CHAT_ID_SECONDARY`.
- `SUPABASE_URL` doit pointer vers le projet Supabase utilisé par les workflows
  (`nhwafcpndlufzzxexikh`). Ne jamais publier la clé service_role.
- Variables `TELEGRAM_APPROVED_DAY_PROMOS` : noms d'images séparés par des virgules,
  par exemple `melbet-royal-monday.jpg`. Vide = aucune campagne par jour.
- Variables `TELEGRAM_APPROVED_BONUS_BOOKMAKERS` : noms approuvés séparés par des
  virgules, par exemple `melbet,1xbet`. Vide = aucun bonus publié.
  N'ajouter une campagne **qu'après confirmation des conditions de l'offre**.

Les workflows publicitaires n'ont plus de déclencheur push/schedule GitHub.
Seul `workflow_dispatch` est conservé. Les paramètres manuels `weekday` et
`bookmaker` ne peuvent plus forcer une campagne hors rotation normale.

## cron-job.org : accès et vérifications restantes
Ces réglages ne sont **pas modifiés automatiquement** via l'accès GitHub/Supabase.
Il faut ouvrir cron-job.org et confirmer l'unicité des tâches :
- XPVIP commune : une exécution par jour, idéalement 05:00 UTC.
- Promotions par jour : une exécution par jour, après l'envoi XPVIP (ex. 06:00 UTC).
- Bonus quotidien : une exécution par jour, idéalement 09:00 UTC,
  seulement si une offre est approuvée.
- Guide quotidien : une exécution par jour, après le bonus, si souhaité.
- BSD V2 coupons et victoires : vérifier les cadences exactes de cron-job.org.
Ne pas créer de doublons de tâches pour le même workflow.

Attention : le dimanche, le guide commun est ignoré, car XPVIP commune
possède déjà son propre envoi.

## Tests
- L'unicité SQL a été vérifiée dans une transaction annulée :
  une deuxième insertion du même triplet n'a créé aucune ligne.
- Les fichiers GitHub ont été vérifiés après modification.
- Aucune promotion réelle n'a été déclenchée pendant la migration.
- Un test complet du service REST Supabase et une vérification du prochain cron
  restent recommandés avant de qualifier l'exploitation de validée.
