# Audit corrigé — Dixon-Coles / Poisson, octobre 2026

**Période :** 1er–31 octobre 2026, Premier League. **Rencontres évaluées :** 38/38.

## Cause des 27 scores 1–1 placés en première position

Le modèle DC original a appris **ρ = −0,08844**. Le facteur `1−ρ` a augmenté la probabilité d'un 1–1 de **8,844 %**. Néanmoins, **25 des 38 rencontres** plaçaient encore 1–1 au premier rang avec les **mêmes intensités mais ρ = 0**. La correction de dépendance n'explique que **deux** premières positions supplémentaires. L'effet principal vient donc des intensités de buts des deux équipes souvent proches de 1 à 2.

La somme des probabilités DC individuelles du 1–1 était **4,456** rencontres attendues ; on a observé **5** scores 1–1. Avoir 27 *modes* 1–1 ne signifie pas prédire 27 égalisations, ni donner une probabilité de 71 % à ces scores.

## Vraie comparaison statistique (score exact)

| Modèle | Log loss octobre ↓ | Top 1 | Top 3 | 1–1 en tête |
|---|---:|---:|---:|---:|
| Dixon-Coles original | 3.04796 | 7/38 (18.42%) | 11/38 (28.95%) | 27/38 |
| Poisson réentraîné séparément | 3.04236 | 6/38 (15.79%) | 9/38 (23.68%) | 25/38 |
| Poisson avec les mêmes intensités que DC (ρ=0) | 3.04676 | — | — | — |

**Écart moyen de log loss (DC − Poisson indépendant) : +0.00560**. Approximation de l'intervalle 95 % sur 38 matchs : [-0.01498, 0.02618], contenant 0. **L'écart n'est pas statistiquement concluant.**

## Sélection automatique sans utiliser octobre pour l'ajustement

Le système a comparé les deux modèles sur **374 matchs de août 2025 à mai 2026**, en dix blocs mensuels :

| Modèle | Log loss sur 374 matchs |
|---|---:|
| DC | 2,89555 |
| Poisson indépendant | 2,89688 |

Gain DC moyen : +0,00134 ; IC 95 % par bootstrap des blocs mensuels : **[−0,00150, +0,00402]**. Étant donné le risque d'instabilité, le nouveau mécanisme choisit le modèle simple **Poisson** automatiquement ; il ne le fait pas passer pour Dixon-Coles. Sur octobre, ce mécanisme obtient **3.04236 de log loss**, contre 3.04796 pour DC, mais avec **un Top 1 moins performant (6 contre 7)**. Il ne prétend donc pas améliorer toutes les métriques.

**Important :** même si les *données* utilisées pour sélectionner le modèle précèdent octobre, **la règle informatique de repli a été conçue après avoir observé octobre**. C'est une vérification rétrospective, **pas** une preuve prospective indépendante. Ne pas déclarer que ces prévisions étaient réellement publiées avant les matchs.

## Corrections techniques réalisées

- Correction du champ `poisson_same_intensities_log_loss` : il utilise enfin les intensités DC sans la correction rho, et non celles du modèle Poisson réentraîné.
- Ajout du rapport de sélection historique enregistré, comparant les modèles sur les mêmes rencontres et les mêmes coupures mensuelles.
- Nouveau mode automatique fondé sur l'incertitude et un seuil de gain pratique, avec possibilité de forcer le mode Dixon-Coles original.
- Affichage des écarts de probabilité Top 1–Top 2 et du vrai rôle de ρ sur le 1–1.
- Tests des prédictions de repli, de la fuite temporelle et de la sélection historique.

## Détails des 38 rencontres

| Date | Rencontre | Réel | Top 1 DC | Top 1 Poisson |
|---|---|---|---|---|
| 2026-10-10 | Manchester United FC - Tottenham Hotspur FC | 1-1 | 1-1 | 1-1 |
| 2026-10-10 | Chelsea FC - AFC Bournemouth | 5-1 | 1-1 | 1-1 |
| 2026-10-10 | Ipswich Town FC - Fulham FC | 2-1 | 1-1 | 1-1 |
| 2026-10-10 | Aston Villa FC - Brentford FC | 2-2 | 1-1 | 1-1 |
| 2026-10-10 | Sunderland AFC - Brighton & Hove Albion FC | 0-2 | 1-1 | 1-1 |
| 2026-10-10 | Arsenal FC - Leeds United FC | 2-1 | 2-0 | 1-0 |
| 2026-10-11 | Hull City AFC - Everton FC | 2-2 | 0-0 | 1-0 |
| 2026-10-11 | Liverpool FC - Manchester City FC | 0-3 | 1-1 | 1-1 |
| 2026-10-11 | Crystal Palace FC - Nottingham Forest FC | 3-1 | 1-1 | 1-1 |
| 2026-10-12 | Coventry City FC - Newcastle United FC | 4-1 | 0-1 | 0-1 |
| 2026-10-17 | Brentford FC - Liverpool FC | 1-2 | 1-1 | 1-1 |
| 2026-10-17 | Fulham FC - Hull City AFC | 1-0 | 0-0 | 0-1 |
| 2026-10-17 | Manchester City FC - Ipswich Town FC | 3-2 | 3-0 | 3-0 |
| 2026-10-17 | Everton FC - Chelsea FC | 0-2 | 1-1 | 1-1 |
| 2026-10-17 | Newcastle United FC - Aston Villa FC | 0-1 | 1-1 | 1-1 |
| 2026-10-18 | Nottingham Forest FC - Arsenal FC | 0-1 | 0-1 | 0-1 |
| 2026-10-18 | Brighton & Hove Albion FC - Crystal Palace FC | 5-0 | 1-1 | 1-1 |
| 2026-10-18 | AFC Bournemouth - Sunderland AFC | 2-0 | 1-1 | 1-1 |
| 2026-10-18 | Leeds United FC - Manchester United FC | 1-1 | 1-1 | 1-1 |
| 2026-10-19 | Tottenham Hotspur FC - Coventry City FC | 3-1 | 1-0 | 1-0 |
| 2026-10-23 | Ipswich Town FC - Nottingham Forest FC | 1-1 | 1-1 | 1-1 |
| 2026-10-24 | Arsenal FC - Everton FC | 2-0 | 1-0 | 1-0 |
| 2026-10-24 | Chelsea FC - Tottenham Hotspur FC | 0-2 | 1-1 | 1-1 |
| 2026-10-24 | Aston Villa FC - Manchester City FC | 2-1 | 1-1 | 1-1 |
| 2026-10-24 | Coventry City FC - Fulham FC | 0-1 | 0-1 | 0-1 |
| 2026-10-25 | Crystal Palace FC - Newcastle United FC | 0-2 | 1-1 | 1-1 |
| 2026-10-25 | Hull City AFC - Brentford FC | 1-1 | 1-1 | 1-0 |
| 2026-10-25 | Manchester United FC - AFC Bournemouth | 0-3 | 1-1 | 1-1 |
| 2026-10-25 | Sunderland AFC - Leeds United FC | 0-0 | 1-1 | 1-1 |
| 2026-10-25 | Liverpool FC - Brighton & Hove Albion FC | 2-0 | 1-1 | 1-1 |
| 2026-10-31 | Manchester City FC - Brighton & Hove Albion FC | 0-1 | 1-1 | 2-1 |
| 2026-10-31 | Aston Villa FC - Fulham FC | 1-1 | 1-1 | 1-1 |
| 2026-10-31 | Brentford FC - Nottingham Forest FC | 2-0 | 1-1 | 1-1 |
| 2026-10-31 | Chelsea FC - Manchester United FC | 2-0 | 1-1 | 1-1 |
| 2026-10-31 | Hull City AFC - Ipswich Town FC | 2-2 | 2-0 | 1-0 |
| 2026-10-31 | Tottenham Hotspur FC - Crystal Palace FC | 2-0 | 1-1 | 1-1 |
| 2026-10-31 | Coventry City FC - Sunderland AFC | 3-1 | 0-1 | 0-1 |
| 2026-10-31 | AFC Bournemouth - Leeds United FC | 2-0 | 1-1 | 1-1 |

Sources et méthode : fichier `backtest_october_2026_v13.json` associé, historiques CC0 OpenFootball 2021–2026, résultats d'octobre recoupés avec StatsNext et Football Web Pages. Les 38 matchs du mois n'ont pas été utilisés pour l'estimation des paramètres à la coupure du 1er octobre.
