# BSD V3 – Clone expérimental 40 marchés (22 octobre 2026)

## Garantie d'isolation
- Branche séparée; aucun changement du workflow de production BSD V2, de `data.json`, des communications Telegram ou des sélections publiées.
- Pas de secrets GitHub requis pour exécuter les tests.
- Aucun accès Supabase. Neon et Cloudflare sont la **cible de migration**, PAS des intégrations déployées par cette PR.
- Base de calcul: `bsd_v2_core.V2History` (données disponibles historiquement), `estimate_goals`, `score_matrix` (Poisson / Dixon-Coles); Elo point-in-time de `bsd_v2_double_chance`.
- La version active utilisait déjà Poisson, Dixon-Coles, Elo, calibration, moteurs spécialisés BTTS / Over-Under / double chance. Il serait incorrect de les déclarer «créés de zéro».
- Par sécurité, l'ancien `generate_data.py` / `daily-update.yml` n'est pas remplacé: son workflow est désactivé, le système actif est BSD V2.

## Inventaire des 18 améliorations (état de la branche, sans revendication de mise en production)
| # | Amélioration | État | Preuve / reste |
|---|---|---|---|
| 1 | Cloner sans toucher la production | COMPLET pour isolation Git | Branche dédiée + modules `bsd_v3_40_*` |
| 2 | Historique enrichi | PARTIEL | `form_features` 5/10 matchs, domicile/extérieur via V2History; pas de rénovation persistante du schéma historique |
| 3 | Filtrage non limité par H2H/12 | COMPLET dans le clone | Le clone utilise `estimate_goals`, n'impose pas le minimum H2H ni le choix 12 |
| 4 | Elo | COMPLET par réutilisation | `bsd_v2_double_chance._rating` et `form_features`; déjà existant en BSD V2 |
| 5 | Probabilités 1X2 | COMPLET dans le clone de base | Distribution cohérente issue de la matrice de scores; calibration indépendante à tester |
| 6 | Poisson | COMPLET par réutilisation | `bsd_v2_core.score_matrix`; déjà présent en production |
| 7 | Dixon-Coles | COMPLET par réutilisation | paramètre `rho` accepté; calage de rho depuis l'historique reste externe au runner |
| 8 | Matrice cohérente | COMPLET par réutilisation | Normalisation somme=1 + 40 transformations |
| 9 | 40 marchés sur 6 groupes | COMPLET en calcul + règlement | `bsd_v3_40_markets.py`, chaque clé unique; pas encore tous publiables ni tous dotés de cotes |
| 10 | Modernisation ML/calibration | PARTIEL | Réemploi calibrations V2, seuil de validation chronologique dans le sélecteur; pas de réentraînement V3 par famille |
| 11 | Sélection EV / cotes vérifiées | PARTIEL | `rank_markets` refuse cotes estimées, vieillies, sans validation; aucune connexion bookmaker vers ces 40 clés |
| 12 | Règlement automatique | PARTIEL | `settle_market` résultats pending/win/lose/push/void, sans rattachement au workflow de settlement réel |
| 13 | Métriques / ROI | PARTIEL | `bsd_v3_40_evaluate.py` métriques par marché, uniquement cotes vérifiées; pas de validation prospective exécutée |
| 14 | Neon | PARTIEL | Schéma SQL de préparation `bsd/v3_neon_schema.sql`; migration non exécutée, pas de connecteur de production |
| 15 | Cloudflare | NON APPLIQUÉ | Aucun déploiement de Worker ou adaptation du frontend |
| 16 | GitHub Actions | PARTIEL | Workflow PR/manual de test lecture seule; pas de génération quotidienne V3 |
| 17 | Site web | NON APPLIQUÉ | Pas de modification de `pronos.html` ou `assets/js/main.js` |
| 18 | Tests / audit | PARTIEL | Tests V3 et régressions BSD V2 passés en CI du 22/10/2026 (run 39724148348); manque validation historique réelle / Neon / Cloudflare / end-to-end |

## Organisation des 40 marchés
- **G1 Résultat / double chance (5)** : 1,2,18,19,20.
- **G2 DNB avec remboursement (2)** : 12,13.
- **G3 Total des buts (13)** : 3,4,5,6,7,8,9,33,34,35,38,39,40.
- **G4 Total des buts par équipe (10)** : 14,15,16,17,25,26,27,28,36,37.
- **G5 BTTS / clean sheet / win-to-nil (6)** : 10,11,29,30,31,32.
- **G6 Handicaps positifs (4)** : 21,22,23,24.

## Usage hors production
```bash
python -m unittest discover -s bsd -p 'test_bsd_v3_40_markets.py' -v
python bsd/bsd_v3_40_runner.py --events /path/to/upcoming.json --history /path/to/private-history.json --output tmp/bsd_v3_40_shadow.json
```
Les fichiers d'événements/historique doivent respecter le schéma BSD, dates en ISO UTC, identifiants d'équipes. Ne jamais committer de données historiques sous licence en clair.

## Critères avant activation de tout marché sur le site
1. Validation au fil du temps et sans fuite des données futures.
2. Calibration et comparaison à un modèle de référence, résultats suffisants par groupe/ligue.
3. Cotes bookmaker réelles, vérifiées, identifiant du marché vérifié (ne jamais extrapoler un bookmaker code).
4. Suivi financier net, remboursement, annulation et retraits.
5. Pipeline Neon/Cloudflare validé dans la migration; aucun write en production jusqu'à accord.
6. Protections contre le déclenchement double, l'injection de pronostics après coup et la modification d'un pari publié.

Aucun pari ni score de confiance n'offre de garantie de réussite ou de profit.


## Update: experimental page and Neon test branch (22 October 2026)
- Cloned `pronos.html` to `pronos-v3-test.html`; production `pronos.html` remains unchanged.
- Dedicated JS `assets/js/pronos-v3-test.js` renders `bsd/v3_preview_feed.json` only, never `data.json` or the live V2 publication feed.
- Initial preview feed contains **zero genuine forecasts**; no synthetic or invented match. To populate, manually run `BSD V3 - Apercu de test (sans publication)` on experimental GitHub branch. This workflow restores the licensed BSD history, fetches real future BSD fixtures, computes up to 40 probabilities/match, archives an artifact and updates *only the experimental branch* preview JSON.
- Neon project `MrXPRONOS-Migration`: dedicated database branch `bsd-v3-40-markets-preview`; schema `bsd_v3_shadow` was successfully applied on this branch only. No database write integration or synchronization from the preview workflow yet.
- No Cloudflare deployment configured yet; a GitHub branch file is not a live web URL, and must not be described as deployed.
- V3 ML chronological evaluation and priced, fully verified ticket publication are **not completed**; the page labels probabilities as observations only.
- CI must be reconfirmed after the latest commits. Under no circumstances merge the draft PR automatically.
