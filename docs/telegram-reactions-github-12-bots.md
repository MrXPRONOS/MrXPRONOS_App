# Réactions automatiques Telegram — 12 bots (2 existants + 10 sur GitHub)

## Couverture

L'API Telegram délivre les nouveaux `channel_post` au webhook existant de **Ciné Radar** seulement dans les canaux où ce bot est administrateur et reçoit les événements. Cela comprend les publications faites **manuellement par le propriétaire**, par un autre administrateur ou par un autre bot. Les publications anciennes ne sont pas parcourues.

- **Bots n°1 et n°2** : déjà actifs via le Worker Cloudflare `cinecanaux-bot`, réactions cœur/pouce en alternance.
- **Bots n°03 à n°12** : GitHub Actions lit les identifiants de messages dans Cloudflare D1 et appelle directement l'API officielle `setMessageReaction`.
- Chaque publication peut obtenir 6 cœurs + 6 pouces au total si **tous** les bots disposent des autorisations nécessaires et si les 12 appels sont acceptés par Telegram.
- Les albums sont regroupés en une publication par le détecteur existant.
- Le système ne republie aucun message et ne s'appuie sur aucune session Telegram personnelle.

Les 10 nouveaux bots utilisent 10 secrets dans **GitHub → Settings → Secrets and variables → Actions → Repository secrets** :

```text
TELEGRAM_REACTION_BOT_03_TOKEN
TELEGRAM_REACTION_BOT_04_TOKEN
TELEGRAM_REACTION_BOT_05_TOKEN
TELEGRAM_REACTION_BOT_06_TOKEN
TELEGRAM_REACTION_BOT_07_TOKEN
TELEGRAM_REACTION_BOT_08_TOKEN
TELEGRAM_REACTION_BOT_09_TOKEN
TELEGRAM_REACTION_BOT_10_TOKEN
TELEGRAM_REACTION_BOT_11_TOKEN
TELEGRAM_REACTION_BOT_12_TOKEN
```

Ces secrets doivent être **10 jetons Telegram différents** issus de **10 bots différents**. Ne renseignez jamais le jeton Ciné Radar ou Canal Bots dans ces 10 emplacements. La validation `getMe` exclut les deux bots existants.

## Création et autorisations des bots

1. Dans Telegram, ouvrir `@BotFather`, taper `/newbot` et créer chacun des dix bots.
2. Enregistrer chaque jeton via les secrets GitHub ci-dessus (pas dans un fichier, une issue ou une conversation).
3. Ajouter les dix bots dans **chaque canal de votre propriété** concerné, avec les autorisations nécessaires selon Telegram. S'assurer que **Ciné Radar** fait aussi partie des administrateurs du canal pour que les nouveaux posts soient détectés.
4. Autoriser les réactions ❤️ et 👍 dans les paramètres du canal.
5. Vérifier dans GitHub Actions le workflow `Telegram - 10 bots de reactions supplementaires (GitHub)`.

Le workflow utilise aussi un secret Cloudflare existant `CLOUDFLARE_API_TOKEN` ou `CF_API_TOKEN`, si celui-ci a les droits de lecture/écriture D1 ; dans le cas contraire, configurer un jeton restreint dédié `CLOUDFLARE_D1_TOKEN` (accès D1 à la base `cinecanaux-directory`). Ne pas publier ce jeton.

## Exploitation

La migration `cinecanaux/migrations/023_github_extra_reaction_bots.sql` doit être appliquée **avant** la fusion du workflow. Elle garde la position de départ afin de ne pas ajouter de réactions aux publications antérieures.

**Activation progressive :** les bots 03 à 07 ont leur point de départ conservé à la publication n°63. Les bots 08 à 12 seront enregistrés lors de leur première vérification d'identité réussie, et ne réagiront qu'aux publications suivantes ; ils ne rattraperont pas les messages parus avant leur activation. L'absence d'un secret n'empêche jamais les bots déjà opérationnels de fonctionner.

Le workflow GitHub `.github/workflows/telegram-reactions-github.yml` :
- s'exécute environ toutes les cinq minutes (les déclenchements GitHub peuvent subir des retards) ;
- ne réagit qu'aux publications **postérieures à l'installation** de la migration ;
- n'envoie aucune réaction si aucun jeton supplémentaire n'est défini ;
- empêche les tentatives en double grâce à une clé D1 `(post_seq,bot_slot)` et à la sémantique idempotente de `setMessageReaction` ;
- met de côté les refus permanents de Telegram ; réessaie progressivement les erreurs temporaires et HTTP 429 ;
- conserve un journal de résultat sans exposer les jetons.

La fréquence et les limites sont celles de **GitHub Actions ET de Telegram** : GitHub ne supprime pas les limites Telegram. Pour des réactions quasi instantanées, maintenir le système Cloudflare existant des deux premiers bots ; la dizaine supplémentaire suit le cycle GitHub.

Ces réactions sont automatisées, **pas des réactions spontanées de vrais abonnés**. Signalez ce fonctionnement aux membres pour ne pas confondre les chiffres avec une mesure réelle de popularité.

## Vérification D1

```sql
SELECT state, bot_slot, COUNT(*) AS n
FROM channel_reaction_extra_jobs
GROUP BY state, bot_slot
ORDER BY bot_slot, state;
```

Ce workflow ne peut pas réagir aux publications des canaux où le bot Ciné Radar ne reçoit aucun événement `channel_post`.
