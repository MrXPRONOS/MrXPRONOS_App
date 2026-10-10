# Production Telegram football — Mr XPRONOS

## Objectif
Le canal football fonctionne en production avec un contrôle automatique toutes les 30 minutes, heure du Togo (GMT/UTC).

## Planning éditorial

- 07h00 : Matchs du jour
- 09h00 : Flash Foot principal
- 12h30 : La Stat du jour
- 15h00 : Le Débat du jour
- Avant-match : déclenchement événementiel entre 65 et 170 minutes avant le coup d'envoi
- Résultat final : dès qu'un match terminé et vérifié devient disponible
- 17h00–23h00 : second Flash Foot possible si une nouvelle actualité existe et si l'espacement minimum de 3 heures est respecté

## Fréquence du workflow production
Workflow : `.github/workflows/football-production.yml`

Cron :
`0,30 7-23 * * *`

Le workflow s'exécute à 07h00, 07h30, 08h00, 08h30, etc. jusqu'à 23h30 GMT.

## Anti-doublon
L'historique est stocké dans :
`.state/mrxpronos-football.json`

GitHub Actions restaure le dernier cache `football-production-` avant chaque run puis sauvegarde un nouveau cache après publication réelle.

## Limites par jour
- Matchs du jour : 1
- Avant-match : 2
- Résultats : 2
- Stat : 1
- Débat : 1
- Flash Foot : 2

Maximum par run : 2 publications.

## Sécurité
- Les pushes de code n'envoient jamais de message Telegram.
- Le workflow CI `.github/workflows/football-channel.yml` ne fait que des tests et une simulation.
- Les runs planifiés du workflow production publient réellement.
- Un lancement manuel du workflow production est en dry-run par défaut.
- L'option `force` est réservée aux tests exceptionnels.
- Les six templates premium doivent être présents avant publication.
- Les secrets BSD et Telegram sont contrôlés avant le lancement.

## Secrets nécessaires
- `BSD_API_KEY`
- `FOOTBALL_NEWS_BOT_TOKEN`
- `FOOTBALL_NEWS_CHAT_ID`

## Fuseau horaire
Le Togo est GMT/UTC, donc le cron GitHub correspond directement aux horaires éditoriaux.
