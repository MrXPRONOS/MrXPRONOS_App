# Diagnostic du 20 novembre 2026 — réactions Telegram

## Constats vérifiés dans GitHub et Cloudflare D1

- Les 2 bots Cloudflare historiques ont marqué **398 réactions réussies sur 199 publications**.
- Les 8 bots supplémentaires confirmés lors du dernier passage (03–07 et 13–15) ont enregistré **30 réactions réussies**, tandis que **520 tâches étaient encore en attente**, 70 à réessayer et 30 bloquées.
- La séquence des nouvelles publications allait jusqu'à **199 à 19:44 UTC**, mais la file additionnelle ne contenait que des tâches jusqu'à la séquence **148** ; le runner GitHub ne traite donc pas les dernières publications.
- Le workflow additionnel n'avait **aucune exécution GitHub avec l'événement `schedule`** dans les journaux consultés. Seules les modifications GitHub (`push`) l'avaient exécuté. GitHub reconnaît que les workflows planifiés peuvent être retardés ou abandonnés aux heures chargées ; on ne peut donc pas garantir 5 minutes exactes.
- Les bots 03–07 ont reçu des erreurs Telegram **`chat_not_found`** sur plusieurs canaux et n'avaient pas réussi de réactions dans le journal consulté. Cela nécessite de vérifier leur statut d'administrateur et les emojis autorisés.
- Le bot 16 avait un jeton configuré, mais l'identité n'avait pas été validée. Le nouvel affichage de diagnostic distingue jeton refusé, doublon, bot réservé et informations invalides.

## Correctifs dans ce changement

1. **Publication récente prioritaire** : insertion des nouveaux jobs par numéro de publication décroissant. Quand le backlog est important, les dernières publications ne sont plus exclues de la création des tâches.
2. **Traitement équitable** : un passage réserve au plus 80 places aux jobs les plus récents et 20 aux plus anciens encore éligibles. Les jobs envoyés et bloqués sont ignorés ; une même paire message/bot n'est jamais renvoyée parce qu'elle apparaît dans les deux lots.
3. **Horaire GitHub standard** : liste explicite des minutes 03, 08, 13, 18, ... 58 (une fois toutes les cinq minutes). Toujours sujet aux retards et abandons possibles de GitHub.
4. **Déclencheur de secours** : `repository_dispatch` de type `telegram_reactions_tick`. Un éventuel service externe de planification comme cron-job.org peut appeler l'API GitHub sans exécuter les réactions hors de GitHub. **Ce secours doit être configuré séparément** ; ajouter le trigger seul ne le rend pas actif.
5. **Secours réellement automatisé** : le workflow Github de réactions est aussi lancé à la fin du workflow existant **BSD V2 - Coupons Telegram (cron-job.org)**, déclenché toutes les 15 minutes par cron-job.org. Il ne récupère aucun code d'une branche externe ; seuls les événements ayant `head_branch=main`, `event=workflow_dispatch`, `conclusion=success` et le dépôt source attendu sont autorisés. Cela reste un déclencheur GitHub : les réactions s'exécutent dans GitHub Actions avec ses secrets, pas dans cron-job.org. La cadence native de cinq minutes reste la voie privilégiée.
6. **Coût réduit** : le job de tests est exécuté sur `push`, `pull_request` et `workflow_dispatch` manuels, mais pas à chaque réveil planifié ou par secours.
7. **Vérification d'accès en lecture seule** sur chaque `push` ou lancement manuel : les comptes supplémentaires dont l'identité est valide sont vérifiés avec `getChatMember` dans les canaux principaux Films, Séries et Animés. Les logs montrent `admin`, `not_admin`, `not_accessible`, sans jeton.

## Contrôler le succès après déploiement

Dans GitHub → Actions → `Telegram - bots de reactions extensibles (GitHub)` :

- vérifier qu'il existe des exécutions **`schedule`** ou **`repository_dispatch`** ; les passages `push` seuls ne sont pas suffisants ;
- rechercher `reaction_slots_verified` et `bot_slot=16 identity=...` pour confirmer les jetons ;
- rechercher `access_bot=XX channel=films/series/animes status=...` pour les accès des bots ;
- rechercher `reactions_confirmed=...` ; un succès GitHub ne garantit pas à lui seul que Telegram ait accepté des réactions.

Dans D1 :

```sql
SELECT j.bot_slot,j.state,j.last_error,COUNT(*) AS total
FROM channel_reaction_extra_jobs j
GROUP BY j.bot_slot,j.state,j.last_error
ORDER BY j.bot_slot,j.state;

SELECT p.seq,p.chat_id,p.message_id,p.observed_at,
       j.bot_slot,j.state,j.last_error
FROM channel_reaction_posts p
LEFT JOIN channel_reaction_extra_jobs j ON j.post_seq=p.seq
ORDER BY p.seq DESC,j.bot_slot
LIMIT 50;
```

## Si GitHub ne déclenche pas les horaires planifiés

Configurer sur un **canal d'administration privé**, jamais sur GitHub source, un planificateur qui appelle :
`POST https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/dispatches`
avec un jeton GitHub à droits minimaux adapté au dépôt et l'événement `telegram_reactions_tick`. L'API GitHub lance alors le **même** workflow avec les secrets GitHub existants. Il ne faut pas publier le jeton dans les logs ou le code. Ne pas mettre en place des déclenchements plus rapides que nécessaire ; chaque exécution consomme des quotas GitHub et reste soumise aux limites Telegram.

**Les bots supplémentaires doivent être administrateurs des canaux correspondants** : un code correct ne donne pas à lui seul ce droit.
