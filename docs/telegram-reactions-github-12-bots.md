# Réactions Telegram extensibles — Ciné Radar + bots ajoutés progressivement

## Architecture et couverture

Deux bots de réaction historiques continuent à utiliser le webhook Cloudflare Ciné Radar. Leurs réactions ❤️ / 👍 et leur journal D1 sont conservés. Les bots supplémentaires sont servis par GitHub Actions et réagissent environ toutes les cinq minutes, **uniquement** aux nouveaux messages que le webhook reçoit.

Les publications faites manuellement par le propriétaire, par d'autres administrateurs, par les bots de publication ou via une API sont toutes éligibles dès qu'un événement `channel_post` arrive au webhook. Un bot qui figure dans un canal ne reçoit pas nécessairement son historique ; pour recevoir les nouveaux `channel_post`, Ciné Radar doit y disposer de l'accès requis.

Ce système ne crée pas d'abonnés et ne constitue pas une mesure authentique d'engagement.

## Ajouter les bots progressivement, sans changer le code

Les secrets GitHub de la forme `TELEGRAM_REACTION_BOT_NN_TOKEN` sont **déjà déclarés dans le workflow pour les emplacements 03 à 99**. Exemples :

```text
TELEGRAM_REACTION_BOT_03_TOKEN
TELEGRAM_REACTION_BOT_07_TOKEN
TELEGRAM_REACTION_BOT_08_TOKEN
TELEGRAM_REACTION_BOT_12_TOKEN
TELEGRAM_REACTION_BOT_13_TOKEN
TELEGRAM_REACTION_BOT_14_TOKEN
TELEGRAM_REACTION_BOT_15_TOKEN
TELEGRAM_REACTION_BOT_16_TOKEN
...
TELEGRAM_REACTION_BOT_99_TOKEN
```

Dans GitHub, ouvrir `MrXPRONOS/MrXPRONOS_App → Settings → Secrets and variables → Actions → New repository secret` et copier le jeton que `@BotFather` a généré **dans la valeur du secret**.

Chaque bot doit posséder son propre token et son identité vérifiée via `getMe`. Les noms 13, 14, 15, 16, etc. sont détectés lors du **passage GitHub suivant** (généralement cinq minutes, retard possible). Il n'est pas nécessaire de remplir les emplacements intermédiaires.

**Pour dépasser 99 ou préserver les quotas de secrets GitHub :** créer un seul secret `TELEGRAM_REACTION_BOTS_JSON` dont la valeur est un objet JSON contenant les indices (de 3 à 9999) et leurs jetons. Par exemple, remplacer les exemples par des jetons réels directement **dans le secret GitHub** :

```json
{"100":"TOKEN_DU_BOT_100","101":"TOKEN_DU_BOT_101"}
```

Ne jamais copier ce JSON avec de vrais jetons dans GitHub source, les logs, les issues ou une discussion publique. Les secrets individuels prévalent en cas de doublon d'indice ; les jetons identiques attribués à plusieurs indices sont ignorés. GitHub limite le nombre de secrets qu'un dépôt peut stocker : le JSON évite d'avoir besoin d'un secret pour chaque nouveau bot.

## Règles d'activation

Chaque nouveau bot doit aussi être ajouté aux canaux visés, avec le niveau d'accès requis par Telegram. Les réactions ❤️ et 👍 doivent être autorisées dans les réglages du canal.

- Emplacements **03–07** : ils conservent leur position d'activation initiale (63).
- Chaque bot ajouté ultérieurement se voit attribuer la position du dernier post reçu au moment de sa première identification valide ; il ne réagit **pas** à l'historique antérieur.
- Leurs réactions alternent selon la parité du message et du numéro du bot ; les numéros pairs et impairs se répartissent les ❤️ / 👍.
- Le traitement D1 ne crée qu'un job par paire (publication, bot). Les erreurs de droits ou de réaction sont enregistrées comme des diagnostics sans fuite de token.
- Les appels Telegram sont soumis à ses propres limites, même si le workflow est exécuté sur GitHub.

## Canaux principaux Films et Séries

Les identifiants réels vérifiés en D1 :
- Films : `@CineXFilms_vf`, `-1003921647496`.
- Séries : `@seriesvf_cinex`, `-1004406527554`.
- Animés : `@CineXAnimeFR`, `-1004347937458`.

Le 20 novembre, le journal de Ciné Radar montrait des posts Films jusqu'à 00:50 UTC et des posts Séries jusqu'à 13:10 UTC : **tous avant l'activation des réactions**. Le webhook de Ciné Radar n'est donc pas encore prouvé défaillant dans ces canaux.

Le job GitHub `coverage_audit`, lancé lors d'une modification ou d'un déclenchement manuel du workflow, vérifie en lecture seule :
1. si le jeton Ciné Radar est disponible dans les secrets GitHub (sinon audit indisponible) ;
2. si son webhook est configuré pour `channel_post` ;
3. si le bot est actuellement administrateur des trois canaux ;
4. si Telegram annonce que les réactions sont autorisées ;
5. si des publications ont été reçues dans le journal des réactions.

Aucun post Telegram de test n'est envoyé. Les permissions et les paramètres du canal se règlent dans Telegram par son propriétaire.

## Bots 03 à 16 : numéros manquants et reprise d'accès

Les secrets numérotés ne doivent **pas** être consécutifs : si seuls `TELEGRAM_REACTION_BOT_03_TOKEN`, `TELEGRAM_REACTION_BOT_07_TOKEN`, `TELEGRAM_REACTION_BOT_13_TOKEN` et `TELEGRAM_REACTION_BOT_16_TOKEN` sont renseignés, le workflow utilise ces quatre bots et ignore les autres numéros.

Pour chaque nouveau message reçu par le webhook Ciné Radar, les bots dont `getMe` confirme l'identité reçoivent une tâche de réaction, avec leur propre ❤️ ou 👍. Un bot ajouté après la publication d'un message ne rattrape pas les anciens posts antérieurs à sa première activation.

**Telegram reste responsable des autorisations** : chaque bot doit être administrateur des canaux ciblés et les réactions ❤️ / 👍 doivent être permises. L'ajout d'un secret dans GitHub ne fait pas entrer le bot dans un canal. Si Telegram renvoie `chat_not_found` ou `not enough rights`, la réaction est désormais conservée pour un nouvel essai après **15 à 60 minutes**. Les messages supprimés ou les emojis interdits restent bloqués.

Lors de chaque exécution, le journal GitHub indique les numéros configurés de 03 à 16 et les numéros dont l'identité Telegram est validée. Un secret de bot invalide, redondant ou attribué au mauvais bot doit être corrigé dans GitHub. Le programme ne crée ni jeton ni bot.

## Vérification

Workflow GitHub : `.github/workflows/telegram-reactions-github.yml`.
Script : `scripts/telegram_reactions_github.py`.
Audit : `scripts/telegram_reaction_coverage_audit.py`.

Statuts D1 des nouveaux bots :

```sql
SELECT bot_slot,state,last_error,COUNT(*) n
FROM channel_reaction_extra_jobs
GROUP BY bot_slot,state,last_error
ORDER BY bot_slot,state;
```

Attention : `blocked` indique qu'un appel Telegram a été refusé ; l'ajout d'un nouveau bot ne peut pas corriger automatiquement un refus de droits ou un canal dans lequel le bot n'a pas accès au message.

## Ordre de priorité des publications (21 novembre 2026)

Les deux réactions du Worker Ciné Radar et les réactions supplémentaires du workflow GitHub traitent maintenant **les nouvelles publications avant les anciennes** : numéros de publication décroissants (`DESC`). En cas de limite de traitement, toute la capacité du passage va aux tâches les plus récentes admissibles, sans réserver une part aux anciennes. Une fois les tâches récentes traitées, les anciennes restent en attente et sont traitées progressivement. Dans chaque publication, Ciné Radar précède Canal Bots ; l'alternance ❤️/👍 et la protection contre les doublons sont conservées. La limite représente un nombre d'**actions de réaction**, pas un nombre de messages indépendants, car plusieurs bots réagissent à un message.
