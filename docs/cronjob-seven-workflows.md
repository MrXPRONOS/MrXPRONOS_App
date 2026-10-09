# Sept déclencheurs cron-job.org — Mr XPRONOS

Créer **sept tâches indépendantes**, fuseau **UTC (Togo)**, fréquence **chaque jour**. Plusieurs tâches ont la même heure mais déclenchent des workflows distincts.

## Paramètres HTTP communs

- Méthode : `POST`
- `Accept: application/vnd.github+json`
- `Authorization: Bearer <VOTRE_TOKEN_PRIVÉ>`
- `X-GitHub-Api-Version: 2022-11-28`
- `Content-Type: application/json`
- Corps JSON : `{"ref":"main","inputs":{"trigger_source":"cron-job.org"}}`

Le jeton GitHub doit être limité à ce dépôt avec **Actions: Read and write**. Les arguments optionnels des trois workflows paramétrables conservent leurs valeurs par défaut quand seuls `trigger_source` et `ref` sont envoyés.

## Les sept tâches

| Heure | Nom cron-job.org | URL POST |
|---|---|---|
| 00:05 | Génération quotidienne BSD V2 | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/bsd-v2-production.yml/dispatches` |
| 01:35 | Archive historique BSD | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/bsd-backfill.yml/dispatches` |
| 07:50 | Settlement BSD V2 | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/bsd-v2-settlement.yml/dispatches` |
| 05:00 | Promo XPVIP commune | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/telegram-daily-xpvip-promo.yml/dispatches` |
| 05:00 | Promotions bookmakers selon le jour | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/telegram-day-based-bookmaker-promos.yml/dispatches` |
| 09:00 | Bonus bookmaker quotidien | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/telegram-daily-bookmaker-bonus-ads.yml/dispatches` |
| 09:00 | Guide bookmaker quotidien | `https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/telegram-daily-bookmaker-guide.yml/dispatches` |

## Mise en service

1. Créer et tester chaque tâche dans cron-job.org : HTTP `204` = demande acceptée (pas nécessairement exécution réussie).
2. Vérifier que le nouveau workflow GitHub apparaît avec l'indication `(cron-job.org)` et s'achève avec succès.
3. **Seulement ensuite**, supprimer les blocs `schedule` des sept workflows GitHub afin d'éviter les doublons. Les workflows déclenchés par `push`, `workflow_dispatch` ou d'autres événements continueront de fonctionner.
4. Vérifier que les campagnes publicitaires ciblent bien les deux canaux Telegram configurés.

Attention : les tâches BSD d'archive et de génération peuvent modifier des fichiers du dépôt ; les exécutions GitHub programmées et externes ne doivent pas se chevaucher. Le déclenchement externe est plus régulier, mais GitHub peut différer le démarrage du job.
