# Exploitation Cinéma Telegram — 15 formats

## État actuel

- **Code** des 15 formats présent sur `main`.
- **Canal de test** : `@predict_mrxp`, défini explicitement dans `scripts/cinema_telegram.py`.
- **Production** : désactivée par défaut, exige `vars.CINEMA_PRODUCTION_ENABLED=true` ET `secrets.CINEMA_PRODUCTION_CHAT_ID`.
- **Images** : affiches TMDB téléchargées telles quelles, sans composition, sans image créée. Portrait TMDB pour les acteurs. Sondages/quiz natifs Telegram.
- **Réels essais sur Telegram** : ne sont validés qu'avec les IDs de messages et une exécution GitHub Actions réussie ; ne pas considérer un simple commit comme preuve d'envoi.

## Diagnostic automatisé en lecture seule

Workflow : [Cinema healthcheck](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/cinema-healthcheck.yml).

Lors d'un changement de ses fichiers sur `main` (ou lors d'un déclenchement manuel), il :
1. Lance les tests unitaires des trois séries et les tests du diagnostic.
2. Génère les quinze aperçus hors ligne (aucun envoi).
3. Vérifie via `getMe`, `getChat` et `getChatMember` que le bot est administrateur de `@predict_mrxp` et peut y publier.
4. Vérifie que TMDB répond avec des films et des affiches réelles.
5. Inscrit un bilan dans le résumé du job GitHub.

**Ce diagnostic ne publie rien.** S'il échoue, consulter son résumé de job et corriger la permission/secret manquant avant un test réel.

## Secrets nécessaires (ne pas les mettre dans le dépôt)

- `CINEMA_TELEGRAM_BOT_TOKEN` ou `TELEGRAM_BOT_TOKEN` : bot administrateur du canal de test.
- `TMDB_API_KEY` : clé API TMDB autorisée pour le type d'utilisation envisagée.
- `CINEMA_PRODUCTION_CHAT_ID` : identifiant du **canal cinéma de production** (pas un canal de pronostics).

La variable de dépôt `CINEMA_PRODUCTION_ENABLED` doit rester absente ou différente de `true` jusqu'à validation des essais et accord explicite pour la production.

## Programmation prévue après activation

Toutes les heures sont en UTC et identiques à l'heure du Togo.

| Jour | 09:17 (série 1) | 13:19 (série 2) | 20:27 (série 3) |
|---|---|---|---|
| Lundi | Film du jour | Séries | Duel |
| Mardi | Top 5 | Mieux notés | Anecdote vérifiée |
| Mercredi | Prochaines sorties | Pépites | Box-office cumulatif |
| Jeudi | Film du soir | Acteur | Bande-annonce officielle |
| Vendredi | Quiz | Sondage | Sélection du week-end |
| Samedi | Film du jour | Séries | Sélection du week-end |
| Dimanche | Top 5 | Mieux notés | Duel |

Cela correspond à **3 posts par jour**, soit **21 par semaine**, et couvre les **15 formats différents** sur cinq jours.

GitHub Actions peut déclencher ses tâches planifiées avec un retard occasionnel ; ce n'est pas une garantie d'envoi à la seconde.

## Contrôle des doublons et reprise

Les trois workflows sauvegardent maintenant l'historique même après un échec partiel, dans :
- `cinema/sent_test.json` et `cinema/sent_production.json` ;
- `cinema/sent_test_batch2.json` et `cinema/sent_production_batch2.json` ;
- `cinema/sent_test_batch3.json` et `cinema/sent_production_batch3.json`.

Les fichiers manquants ne bloquent pas l'enregistrement des fichiers présents. Le duel conserve ses étapes (publication et sondage). Une interruption réseau ambiguë peut toutefois empêcher une garantie absolue de publication exactement une fois.

## Lancer un essai réel et contrôlé

Dans Actions, déclencher le workflow de la série souhaitée sur `main`, avec `mode=test`, `format=all`, `demo=false`, `dry_run=false`. Cette opération **publie réellement** dans `@predict_mrxp` si les secrets et droits sont valides. Vérifier visuellement les photos officielles, les mises en forme et la largeur réelle des boutons Rich Messages avant l'activation en production.

**Droits d'usage :** les métadonnées et affiches TMDB peuvent être soumises à des conditions de licence. Une clé gratuite TMDB n'autorise pas nécessairement un usage commercial. Les films complets ne sont pas distribués par ces scripts.
