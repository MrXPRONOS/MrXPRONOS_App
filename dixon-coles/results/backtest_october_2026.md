# Backtest Dixon-Coles — Premier League — octobre 2026

**Période :** 1er au 31 octobre 2026 (inclus).
**Date d’entraînement :** 1er octobre 2026, 00:00 UTC. Aucun score d’octobre n’est inclus dans l’entraînement.

## Méthode

- Moteur : Dixon-Coles V1.2 du dépôt MrXPRONOS/MrXPRONOS_App.
- Historique : 1 950 rencontres de Premier League entre août 2021 et septembre 2026, OpenFootball CC0.
- Vérité terrain : 38 scores d’octobre 2026, StatsNext, recoupés sur une source de résultats BBC miroir.
- Calcul des paramètres : deux ajustements indépendants (Dixon-Coles, Poisson avec rho=0) à la coupure mensuelle du 1er octobre.
- Coefficient de décroissance temporelle : xi=0,0065 par demi-semaine.
- Dates de match dans le CSV sans heure précise : elles sont consignées à 00:00 UTC, sans impact sur la coupure mensuelle.

## Résultats

- Matchs évalués : **38/38**, exclus : 0.
- Score exact Top 1 : **7/38 = 18.42 %**.
- Score exact Top 3 : **11/38 = 28.95 %**.
- Log loss Dixon-Coles : **3.04796**.
- Log loss Poisson réentraîné séparément : **3.04236**.
- Brier 1N2 : **0.63637**.
- Probabilité moyenne du Top 1 : **13.70 %**.
- Concentration : **27/38** prédictions Top 1 de 1–1 ; ce comportement mérite une vérification supplémentaire.

## Scores exacts trouvés

| Date | Match | Score réel | Prédiction |
|---|---|---|---|
| 2026-10-10 | Manchester United FC - Tottenham Hotspur FC | 1-1 | 1-1 |
| 2026-10-18 | Nottingham Forest FC - Arsenal FC | 0-1 | 0-1 |
| 2026-10-18 | Leeds United FC - Manchester United FC | 1-1 | 1-1 |
| 2026-10-23 | Ipswich Town FC - Nottingham Forest FC | 1-1 | 1-1 |
| 2026-10-24 | Coventry City FC - Fulham FC | 0-1 | 0-1 |
| 2026-10-25 | Hull City AFC - Brentford FC | 1-1 | 1-1 |
| 2026-10-31 | Aston Villa FC - Fulham FC | 1-1 | 1-1 |

## Détail des rencontres

| Date | Rencontre | Réel | Top 1 | Top 3 | Top 1 correct |
|---|---|---|---|---|---|
| 2026-10-10 | Manchester United FC - Tottenham Hotspur FC | 1-1 | 1-1 | 1-1, 2-1, 2-0 | Oui |
| 2026-10-10 | Chelsea FC - AFC Bournemouth | 5-1 | 1-1 | 1-1, 2-1, 1-2 | Non |
| 2026-10-10 | Ipswich Town FC - Fulham FC | 2-1 | 1-1 | 1-1, 1-2, 0-1 | Non |
| 2026-10-10 | Aston Villa FC - Brentford FC | 2-2 | 1-1 | 1-1, 2-1, 1-2 | Non |
| 2026-10-10 | Sunderland AFC - Brighton & Hove Albion FC | 0-2 | 1-1 | 1-1, 0-1, 1-2 | Non |
| 2026-10-10 | Arsenal FC - Leeds United FC | 2-1 | 2-0 | 2-0, 1-0, 1-1 | Non |
| 2026-10-11 | Hull City AFC - Everton FC | 2-2 | 0-0 | 0-0, 1-0, 1-1 | Non |
| 2026-10-11 | Liverpool FC - Manchester City FC | 0-3 | 1-1 | 1-1, 1-2, 2-1 | Non |
| 2026-10-11 | Crystal Palace FC - Nottingham Forest FC | 3-1 | 1-1 | 1-1, 0-0, 1-0 | Non |
| 2026-10-12 | Coventry City FC - Newcastle United FC | 4-1 | 0-1 | 0-1, 0-2, 0-0 | Non |
| 2026-10-17 | Brentford FC - Liverpool FC | 1-2 | 1-1 | 1-1, 1-2, 2-1 | Non |
| 2026-10-17 | Fulham FC - Hull City AFC | 1-0 | 0-0 | 0-0, 1-1, 0-1 | Non |
| 2026-10-17 | Manchester City FC - Ipswich Town FC | 3-2 | 3-0 | 3-0, 4-0, 2-0 | Non |
| 2026-10-17 | Everton FC - Chelsea FC | 0-2 | 1-1 | 1-1, 0-1, 0-0 | Non |
| 2026-10-17 | Newcastle United FC - Aston Villa FC | 0-1 | 1-1 | 1-1, 2-1, 1-2 | Non |
| 2026-10-18 | Nottingham Forest FC - Arsenal FC | 0-1 | 0-1 | 0-1, 1-1, 0-2 | Oui |
| 2026-10-18 | Brighton & Hove Albion FC - Crystal Palace FC | 5-0 | 1-1 | 1-1, 2-1, 2-0 | Non |
| 2026-10-18 | AFC Bournemouth - Sunderland AFC | 2-0 | 1-1 | 1-1, 1-0, 2-1 | Non |
| 2026-10-18 | Leeds United FC - Manchester United FC | 1-1 | 1-1 | 1-1, 1-2, 2-1 | Oui |
| 2026-10-19 | Tottenham Hotspur FC - Coventry City FC | 3-1 | 1-0 | 1-0, 2-0, 0-0 | Non |
| 2026-10-23 | Ipswich Town FC - Nottingham Forest FC | 1-1 | 1-1 | 1-1, 1-2, 0-1 | Oui |
| 2026-10-24 | Arsenal FC - Everton FC | 2-0 | 1-0 | 1-0, 2-0, 1-1 | Non |
| 2026-10-24 | Chelsea FC - Tottenham Hotspur FC | 0-2 | 1-1 | 1-1, 2-1, 2-0 | Non |
| 2026-10-24 | Aston Villa FC - Manchester City FC | 2-1 | 1-1 | 1-1, 1-2, 0-2 | Non |
| 2026-10-24 | Coventry City FC - Fulham FC | 0-1 | 0-1 | 0-1, 0-0, 0-2 | Oui |
| 2026-10-25 | Crystal Palace FC - Newcastle United FC | 0-2 | 1-1 | 1-1, 1-2, 2-1 | Non |
| 2026-10-25 | Hull City AFC - Brentford FC | 1-1 | 1-1 | 1-1, 1-0, 0-0 | Oui |
| 2026-10-25 | Manchester United FC - AFC Bournemouth | 0-3 | 1-1 | 1-1, 2-1, 1-0 | Non |
| 2026-10-25 | Sunderland AFC - Leeds United FC | 0-0 | 1-1 | 1-1, 0-0, 1-0 | Non |
| 2026-10-25 | Liverpool FC - Brighton & Hove Albion FC | 2-0 | 1-1 | 1-1, 2-1, 2-0 | Non |
| 2026-10-31 | Manchester City FC - Brighton & Hove Albion FC | 0-1 | 1-1 | 1-1, 2-1, 2-0 | Non |
| 2026-10-31 | Aston Villa FC - Fulham FC | 1-1 | 1-1 | 1-1, 1-0, 2-1 | Oui |
| 2026-10-31 | Brentford FC - Nottingham Forest FC | 2-0 | 1-1 | 1-1, 2-1, 1-0 | Non |
| 2026-10-31 | Chelsea FC - Manchester United FC | 2-0 | 1-1 | 1-1, 2-1, 1-2 | Non |
| 2026-10-31 | Hull City AFC - Ipswich Town FC | 2-2 | 2-0 | 2-0, 1-0, 1-1 | Non |
| 2026-10-31 | Tottenham Hotspur FC - Crystal Palace FC | 2-0 | 1-1 | 1-1, 2-1, 1-0 | Non |
| 2026-10-31 | Coventry City FC - Sunderland AFC | 3-1 | 0-1 | 0-1, 0-0, 0-2 | Non |
| 2026-10-31 | AFC Bournemouth - Leeds United FC | 2-0 | 1-1 | 1-1, 2-1, 1-0 | Non |

## Limites et sources

Ce test rétrospectif ne constitue pas une preuve de rentabilité : il ne tient pas compte des cotes, marges des opérateurs ou frais. La réussite des scores exacts ne peut être garantie.
Une seule période et 38 matchs représentent un échantillon restreint ; les estimations sont sensibles au championnat et à l’année.
Les résultats sont publiés par des sources tierces et n’ont pas été certifiés indépendamment.
- [StatsNext, octobre 2026](https://statsnext.com/premier-league/matches/2026-10)
- [Résultats BBC miroir](https://bbcinsight.pages.dev/sport/football/premier-league/scores-fixtures/2026-10?filter=results)
- [OpenFootball, CC0](https://github.com/openfootball/football.json)
- [Workflow GitHub](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/42289240465)
