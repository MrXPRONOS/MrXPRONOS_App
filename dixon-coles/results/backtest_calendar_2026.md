# Backtest annuel 2026 — Premier League (1 janvier – 6 novembre)

**Type :** simulation rétrospective, pas de pronostics publiés à l’époque.
**Périmètre :** 284 résultats terminés, 275 évalués, 9 exclus faute d'historique.
**Méthode :** entraînement mensuel strictement antérieur aux matchs évalués ; aucun score du mois ne rentre dans son apprentissage.
**Coefficient de décroissance :** ξ = 0.0065; modèle automatique fixé avant 2026 : **poisson**.
**Calibration indépendante :** 2024-08-01 à 2025-06-01 sur 374 matchs, sans utiliser 2026.

## Résultats d’ensemble

| Indicateur | Dixon-Coles | Poisson indépendant | Mode automatique |
|---|---:|---:|---:|
| Log loss score exact | 2.9372 | 2.9388 | 2.9388 |
| Scores exacts Top 1 | 13.09% | 12.73% | 12.73% |
| Scores exacts Top 3 | 29.45% | 29.09% | 29.09% |
| Scores 1–1 en première position | 212 | 174 | 174 |
| Recommandations uniques | 94 | 58 | 58 |
| Scores 1–1 recommandés | 76 | 29 | 29 |
| Recommandations correctes | 16 | 8 | 8 |

## Par mois

| Mois | Matchs | Évalués | Top 1 (auto) | Top 3 (auto) | Conseils | Conseils justes | 1–1 conseillés |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 49 | 49 | 12.2% | 24.5% | 11 | 2 | 5 |
| 2026-02 | 42 | 42 | 19.0% | 35.7% | 8 | 2 | 3 |
| 2026-03 | 32 | 32 | 3.1% | 31.2% | 7 | 0 | 4 |
| 2026-04 | 30 | 30 | 3.3% | 26.7% | 6 | 1 | 4 |
| 2026-05 | 41 | 41 | 19.5% | 31.7% | 8 | 1 | 5 |
| 2026-08 | 20 | 17 | 17.6% | 29.4% | 1 | 0 | 0 |
| 2026-09 | 30 | 24 | 8.3% | 29.2% | 4 | 0 | 3 |
| 2026-10 | 38 | 38 | 15.8% | 23.7% | 12 | 2 | 4 |
| 2026-11 | 2 | 2 | 0.0% | 50.0% | 1 | 0 | 1 |

## Sources et limites

* Historique 2021–2026 : OpenFootball (CC0).
* Octobre 2026 : relevé StatsNext, vérifié contre une seconde source de résultats.
* Novembre 2026 : The Guardian et FBref.
* Les scores de juin et juillet sont absents parce que la Premier League était entre deux saisons.
* Les 1–1 en Top 1 restent des modes mathématiques, pas automatiquement des recommandations.
* Ce backtest ne mesure ni les cotes, ni le rendement de paris ni la performance de championnats autres que Premier League.
