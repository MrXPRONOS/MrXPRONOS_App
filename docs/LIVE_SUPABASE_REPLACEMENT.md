# Sortie de Neon — production LIVE Mr XPRONOS

Date : 24 novembre 2026

## Architecture choisie
- Base : Supabase PostgreSQL existant, projet `nhwafcpndlufzzxexikh` (actif, pas de nouvelle facture ni nouveau projet).
- Edge Function déjà déployée : `/functions/v1/live` (moteur de refresh, requêtes, historique et validation).
- Frontend `assets/js/live.precompiled.js` : URL publique Supabase, aucune clé privée.
- Workflow `validate_predictions.yml` : garde le dispatch cron-job.org existant ; vérifie en lecture les réponses publiques, déclenche refresh avec `CRON_SECRET`, attend le résultat réel `cron_runs` via rôle service GitHub Actions, puis valide les pronostics.
- Quotas : le verrou `claim_live_refresh` évite les rafraîchissements concurrents ; chaque échec est remonté comme échec réel, pas comme simple accusé de réception 202.
- Les secrets de service ne sont jamais envoyés au navigateur ni enregistrés dans Git.
- Neon n'est plus sollicité par la page LIVE et par le workflow de validation.
- Les autres workflows historiques Neon encore présents doivent être désactivés ou basculés distinctement : pas de double publication Telegram.

## Limite de migration
Le projet Neon `withered-tooth-71931108` est archivé et renvoie HTTP 402 « quota exceeded » à sa base. Les lignes anciennes ne sont pas transférables actuellement. Le remplacement ne détruit aucun historique Neon. Vérifier les données accessibles au 1er décembre ou depuis un export disponible, sans réactiver Neon en production.

## Critères d'acceptation
1. Six routes publiques Supabase répondent avec la structure attendue.
2. Le refresh renvoie 202, le relevé `cron_runs.live_refresh.last_ok` est frais et true.
3. La validation renvoie `success:true` avec le nombre réel de pronostics validés, jamais un succès artificiel.
4. Le site public utilise le bon backend et la publication Telegram n'envoie aucun doublon.
5. Les tables peuvent être vides lorsqu'aucun match n'est live ; cette situation ne prouve pas l'existence de nouvelles prédictions.
