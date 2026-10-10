# Canal d'actualités football — Mr XPRONOS

Ce module est **indépendant des pronostics** et ne modifie ni `data.json`, ni le modèle BSD, ni les workflows de coupons.

## Six automatisations

| Rubrique | Créneau Togo | Source | Limite journalière |
| --- | --- | --- | --- |
| Programme du jour | 07h | API BSD V2, rencontres du jour | 1 |
| Flash actualité | 08h–23h | RSS Foot Mercato, articles récents avec lien et attribution | 2 |
| Avant-match | 08h–23h, environ 65–170 min avant le début | API BSD V2, forme sur l'échantillon disponible | 2 |
| Résultats | 08h–23h, lorsque BSD confirme `finished` | API BSD V2 | 2 |
| Statistique | 12h, match d'hier le plus prolifique dans l'échantillon récupéré | API BSD V2 | 1 |
| Sondage | 15h, vote Telegram sur un match ou une question football | API BSD V2 / banque éditoriale | 1 |

Chaque lancement envoie au maximum deux messages. Les déclenchements sont toutes les 30 minutes de 07h07 à 23h37 UTC (Lomé = UTC). Pas de garantie d'instantanéité avec GitHub Actions.

## Prérequis GitHub

Dans **Settings → Secrets and variables → Actions** :
- `BSD_API_KEY` : secret **déjà utilisé par BSD V2**, aucune nouvelle clé nécessaire.
- `FOOTBALL_NEWS_CHAT_ID` : identifiant **du canal d'actualités football**, et non `TELEGRAM_CHAT_ID` des coupons.
- `FOOTBALL_NEWS_BOT_TOKEN` : jeton du bot administrateur de ce canal, autorisé à publier messages et sondages.

Le workflow ne réutilise PAS automatiquement le bot des coupons : cela empêche de publier involontairement dans le mauvais canal. Aucun token ne doit être codé en dur. Un chat ID absent interdit toute publication réelle.

## Tester

Dans Actions → « Mr XPRONOS - Media football Telegram » → Run workflow : laisser `dry_run=true`. La simulation peut contacter l'API BSD pour lire les matchs, mais ne publie pas de message et ne modifie pas l'historique.

Local : `python -m pip install requests`, puis `python -m unittest discover -s tests_football_channel -v` et `python scripts/football_channel.py --dry-run` (BSD_API_KEY nécessaire à certains créneaux).

Pour la première publication réelle, lancer manuellement avec `dry_run=false`, après ajout des deux secrets Telegram.

## Sécurité et qualité

- Les messages ne promettent pas de pronostics et ne touchent pas aux données de paris.
- Un flux RSS ne garantit pas la libre réutilisation des photos : les flashes restent **texte + résumé + lien source**, sans copier les images de Foot Mercato.
- `statistique` indique seulement les buts d'un match présent dans l'échantillon BSD ; ce n'est pas un classement global.
- `avant_match` annonce clairement la forme selon **les sept jours de données récupérés**, jamais une série de cinq matchs inventée.
- Une réponse Telegram doit être confirmée avant enregistrement d'une publication.
- Anti-doublons : restauration des marqueurs par le cache GitHub Actions et sérialisation des runs par `concurrency`. Le cache peut être évincé ; une base Supabase reste préférable pour une garantie forte.
- Les matchs doivent être marqués terminés par BSD avant qu'un score final soit publié.
- Les autres rubriques continuent même si le RSS échoue.
