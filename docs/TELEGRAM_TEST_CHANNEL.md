# Canal Telegram de test — Mr XPRONOS

Objectif : tous les **tests manuels qui produisent un rendu Telegram** doivent aller vers un canal dédié, jamais vers le canal principal.

## Secret unique à ajouter
Dans **GitHub > Settings > Secrets and variables > Actions > New repository secret** :

- Nom : \`TELEGRAM_TEST_CHAT_ID\`
- Valeur :
  - pour un canal public : \`@nom_du_canal\`
  - ou l'identifiant numérique Telegram \`-100...\`

Le projet réutilise les bots existants :
- Actu Foot / visuels : \`FOOTBALL_NEWS_BOT_TOKEN\`
- Coupons BSD V2 : \`TELEGRAM_BOT_TOKEN\`
- Éditorial : \`EDITORIAL_TELEGRAM_BOT_TOKEN\`

Si ces secrets correspondent à des bots différents, **chaque bot concerné doit être ajouté administrateur du canal de test avec le droit de publier**.

## Règles de routage

| Déclenchement | Destination |
|---|---|
| cron-job.org Actu Foot | production |
| cron-job.org cycle match | production |
| cron-job.org BSD coupons | production |
| workflow Actu Foot lancé manuellement | test par défaut |
| BSD coupons lancé manuellement | test par défaut |
| Test réel des 6 rubriques lancé manuellement | test |
| Test visuel Telegram lancé manuellement | test |
| Validation premium lancée manuellement | test |
| Éditorial Telegram lancé manuellement | test par défaut |
| push / pull request / CI classique | aucun envoi Telegram de test |

## Séparation des historiques
- Actu Foot production : \`.state/mrxpronos-football.json\`
- Actu Foot test : \`.state/mrxpronos-football-test.json\`
- Le test éditorial utilise une copie temporaire de la file et ne marque pas les articles comme envoyés en production.
- BSD V2 utilise déjà le \`chat_id\` dans sa clé Supabase anti-doublon : le canal de test et le canal de production ont donc des historiques distincts.

## Premier test recommandé
Lancer manuellement :
**Actions > Telegram - Test canal visuel > Run workflow**

Le workflow envoie une carte carrée 1080×1080 avec le texte « CANAL DE TEST TELEGRAM ».
S'il manque \`TELEGRAM_TEST_CHAT_ID\`, il échoue. Il ne retombe jamais sur le canal principal.
