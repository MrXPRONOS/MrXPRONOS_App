# Mr XPRONOS — Audit des APIs football LIVE
Date: 20 octobre 2026 (UTC) | Dépôt: MrXPRONOS/MrXPRONOS_App

## Méthode et limites
- Code audité : fonctions Supabase `live/index.ts`, `_shared/football_sources.ts`, `_shared/espn.ts`, `_shared/live_bookmaker_direct.ts`, `_shared/live_odds_failover.ts`.
- Vérifications HTTP réelles : `scripts/audit_live_sources.py` via `.github/workflows/audit-live-apis.yml`, avec les identifiants GitHub Secrets disponibles, sans les journaliser.
- Rapport détaillé non sensible : `public.cron_runs`, enregistrement `live_api_audit`. Données brutes/provenance : `live_stats_sources`, `live_stats_merged`.
- Couverture dépendante de l'heure, de la ligue et du match : un endpoint HTTP 200 ne garantit pas que tous les marchés sont disponibles.
- Règle : une paire de statistiques pour un marché doit comporter une valeur réellement observée pour chaque équipe. Une absence n'est jamais traitée comme zéro. La minute en jeu doit être confirmée, jamais estimée sur la base du début théorique.

## Fournisseurs — endpoints, test et rôle

| Source | Endpoint testé | Statut HTTP | Échantillon (tests successifs) | Recommandation |
| --- | --- | --- | --- | --- |
| BSD football v2 | `/api/v2/events/live/`, `/api/v2/events/{id}/stats/` | 200/200 avec `BSD_API_TOKEN` | Un match live puis un détail avec corners, tirs et fautes par équipe | Prioritaire pour marchés détaillés et leurs validations finales, quotas à respecter |
| ESPN | `/apis/site/v2/sports/soccer/all/scoreboard?dates=...`, `summary?event=...` | 200 scoreboard | 94 événements, 0 en cours à l'instant du test; gros historique de statistiques | Fournisseur de couverture et fallback. API de site non contractuelle : circuit breaker/cache essentiels |
| SportScore | `/api/v1/fixtures/?sport=football&date=...&status=live&limit=200` et `/api/v1/match/?sport=football&slug=...` | 200/200 | 3 fixtures en cours, détail avec `stats` sous forme de lignes `label,home,away` | Excellent repérage des matchs / minute si présente; détails observés sur tirs cadrés, possession, attaques; corners/fautes non garantis |
| MoviOdds | `/odds?sport=soccer&in_play=1&stats=1` | 200 | 12 matchs avec 12/12 paires corners, tirs, attaques et attaques dangereuses; 0/12 fautes | Compléter corners et tirs; conserver la fraîcheur `polled_at` et `stats.updated_at`, appariement deux équipes + heure exacts |
| TheSportsDB | `/api/v1/json/123/eventsday.php?d=...&s=Soccer` | 200 | 3 événements avec clé publique gratuite 123 | Calendrier, logos, métadonnées; faible couverture gratuite des stats pour les pronos LIVE |
| OpenLigaDB | `/getavailableleagues`, `/getnextmatchbyleagueshortcut/bl1` | 200/200 | 839 ligues cataloguées | Ligue/calendrier et score, pas source de corners/tirs/fautes |
| API-Football | cache `live_provider_probe_cache` et `live_stats_merged` | Non testé en direct | Contrôles de couverture anciens et non concluants | Vérifier la clé/plan/coût autorisé avant des appels complémentaires |
| PinnWire et autres bridges optionnels | URLs configurables par secrets dans les fichiers `live_odds_*.ts` | Non testé en direct | Pas de contrat/clé vérifié | Ne pas inventer d'endpoint ni prétendre qu'une cote est bookmaker sans vérification |

## Historique de présence des marchés en base avant corrections

| Source | Enregistrements | Corners complets | Tirs totaux complets | Fautes complètes |
| --- | ---: | ---: | ---: | ---: |
| ESPN | 4265 | 3211 | 1281 | 3211 |
| BSD (api_original) | 1625 | 1012 | 862 | 936 |
| SportScore | 1631 | 0 | 0 | 0 |
| TheSportsDB | 18 | 0 | 0 | 0 |
| OpenLigaDB | 25 | 0 | 0 | 0 |

Ceci dénombre les enregistrements de provenance, non les matchs distincts, et non le taux de réussite des pronostics.

## Défauts détectés et corrections
1. **Réception cron bloquée par panne Supabase** : erreurs HTTP 503/504 sur `claim_live_refresh` le 17/10, devenues HTTP 500 au planificateur. Corrigé par prise en charge asynchrone et journalisation de la réussite réelle via `cron_runs`, avec GitHub failover.
2. **BSD éventuellement sauté à tort** : le moteur pouvait écarter `/events/live/` lorsque `/coverage/` indiquait zéro, même si une source complémentaire voyait des matchs actifs. Correction : ignorer ce zéro lorsqu'un autre fournisseur annonce du LIVE, sinon sondage périodique contrôlé.
3. **MoviOdds sous-exploité** : paramètre `stats=1` absent. Ajouté : capture de paires complètes réelles et fusion sans écraser BSD/ESPN; enregistrement de provenance `moviodds`.
4. **Contrainte SQL ancienne** : `live_stats_sources_source_name_check` rejetait le nouveau fournisseur. Migration `20261020032000_allow_moviodds_live_stats.sql`. Vérification DB : `moviodds` est accepté, deux enregistrements avec corners et tirs observés.
5. **Horloge minute indisponible** : certains matchs SportScore/MovieOdds portent le statut 2e mi-temps mais minute exacte = 0. Le moteur les exclut, à juste titre, avant d'émettre des pronostics temporels. Cible du prochain correctif : utiliser uniquement une minute **explicitement observée** chez un fournisseur pour un match apparié; ne jamais en déduire une à partir de l'heure du coup d'envoi.

## Vérifications de production
- Fonction `live` Supabase version 271 : code d'enrichissement MoviOdds et contrôle BSD visibles dans déploiement.
- Table `live_stats_sources` : contrainte actualisée pour MoviOdds, 2 lignes avec paires corners/tirs complètes à 03:20 UTC.
- `cron_runs.live_refresh` : runs réguliers `last_ok=true`, 3 matchs traités sur cycle nocturne, **aucun signal généré** pendant ces contrôles, du fait des marchés incomplets et/ou minute inconnue.
- L'absence de signal est une sortie légitime lorsque les critères de qualité/temps ne sont pas réunis; ne pas abaisser artificiellement les seuils.

## Ressources et secrets
- `BSD_API_TOKEN` : présent/valide dans le workflow GitHub du test, valeur non extraite.
- `MOVIODDS_API_KEY` : optionnelle si endpoint public accessible; la requête audit a réussi; aucune valeur secrète révélée.
- `SUPABASE_SERVICE_ROLE_KEY`, `CRON_SECRET` : ne doivent jamais apparaître côté navigateur ou dans les logs.

## Références fournisseurs
- BSD : https://sports.bzzoiro.com/docs/ et https://sports.bzzoiro.com/docs/conventions/
- MoviOdds : https://moviodds.com/doc
- SportScore : https://sportscore.com/
- OpenLigaDB : https://www.openligadb.de/
- TheSportsDB : https://www.thesportsdb.com/api.php

Pour refaire l'audit après un changement d'API : GitHub Actions > `Audit LIVE football APIs` > `Run workflow`, puis lire `cron_runs.live_api_audit.meta`.
