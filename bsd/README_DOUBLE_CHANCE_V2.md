# Double Chance V2 : audit des 12 améliorations

Les modifications sont sur GitHub main. La présence du code ne prouve pas une amélioration de précision. L'exécution CI et l'évaluation BSD historique sont nécessaires.

| N° | Amélioration | Statut code | Vérification |
|---|---|---|---|
| 1 | Classifieur 1X2 multinomial indépendant | Implémenté (`bsd_v2_double_chance.py`) | Test CI puis Brier 2026 |
| 2 | Modélisation des nuls (équipe + ligue + petit contexte) | Implémenté | Résultats sur matchs nuls 2026 |
| 3 | Domicile/extérieur (lissage petites séries) | Implémenté | Validation données réelles |
| 4 | Force des adversaires, Elo chronologique | Implémenté | Comparaison Brier/Elo via historique |
| 5 | Forme récente pondérée (5/15 matchs) | Implémenté | Test réel |
| 6 | Équilibre attaques/défenses | Implémenté : taux de buts marqués/encaissés pondérés, opposition attaque/défense | Évaluation ablation requise |
| 7 | Fréquence des nuls par championnat | Implémenté avec lissage | Test par ligue |
| 8 | Calibration multinomiale jointe 1/X/2 | Implémenté, 1X/X2/12 sont des sommes normalisées | Tests CI |
| 9 | Cotes BSD réelles >=1,20 + marge conservatrice | Implémenté dans `choose_market` | Publication réelle BSD |
| 10 | Rejet si forme, domicile/extérieur ou désaccord insuffisant | Implémenté pour modèle actif seulement | Contrôle de couverture |
| 11 | Comparaison spécialisée vs Poisson/Dixon-Coles | Implémenté, poids choisi sur holdout 2024, repli à zéro | Backtest |
| 12 | Backtest indépendant 1X/X2/12 | Implémenté, référence calibrée séparément | Workflow validation à exécuter |

## Flux de calcul

- Année 2024 janvier–août : apprentissage multinomial ; septembre–décembre : choix du poids du modèle sur résultats ultérieurs.
- 2025 janvier–août : correction jointe des probabilités 1/X/2 ; septembre–décembre : contrôle qualité par marché.
- 2026 : évaluation indépendante sur les mêmes rencontres, avec référence Poisson/Dixon-Coles et calibrations séparées.
- `P(1X)=P(1)+P(X)`, `P(X2)=P(X)+P(2)`, `P(12)=1-P(X)`. Le classement ne force pas de double chance si un autre marché gagne.
- Cote BSD de source vérifiée indispensable, minimum 1,20. Seuil de confiance prudente contre `1/cote + 2,5 points`.
- Le marché Under 4,5 reste banni.
- Aucun rendement historique ne peut être calculé lorsque les cotes historiques sont absentes.

## À exécuter avant validation définitive

`BSD V2 - Validation experimentale` / `bsd-v2-validation.yml`, entrée `max_test=1000`. Examiner `v2_double_chance_backtest.json`, notamment `baseline_calibrated`, `specialized_calibrated`, les ligues et les tranches. Une implémentation complète du code n'est pas synonyme de meilleur taux de réussite ni d'exécution CI confirmée.


## Complément de finalisation technique — 8 octobre 2026

La phase de finalisation a corrigé les points demeurés partiels dans l'implémentation d'origine.

1. Le modèle comporte maintenant les éléments de force offensive/défensive et la qualité du résultat face à l'Elo connu à la **date du match historique**, sans examiner les résultats futurs.
2. La calibration jointe des trois classes 1/X/2 utilise désormais des tranches de probabilité de nul avec un lissage global pour les petits effectifs, avant de dériver 1X, X2 et 12.
3. Le classement `choose_market` ne recalibre plus séparément la double chance : il conserve la probabilité cohérente du modèle multiclasses déjà corrigée.
4. Des tests de la cohérence des probabilités, du classement, des tranches de calibration et des signaux d'adversaire ont été ajoutés dans `test_bsd_v2_double_chance.py`.
5. Le workflow `bsd-v2-validation.yml` vérifie que les trois marchés ont le même effectif dans le rapport de référence calibré et le rapport spécialisé calibré.

| # | Axe | Implémentation dans le code | Preuve d'exécution |
|---|---|---|---|
| 1 | Classification 1/X/2 | Présente | CI en attente |
| 2 | Nuls | Présente : fréquence, modèle 1X2, calibration conditionnelle au nul | Validation statistique en attente |
| 3 | Domicile/extérieur | Présente : historique séparé et lissage | CI en attente |
| 4 | Force adverse | Renforcée : Elo historique à l'instant du match passé | Backtest en attente |
| 5 | Forme pondérée | Présente : 5/15 rencontres et décroissance temporelle | CI en attente |
| 6 | Attaque/défense | Présente : buts marqués et encaissés pondérés | CI en attente |
| 7 | Ligue | Présente : prior de taux de nul lissé | Validation par ligue en attente |
| 8 | Probabilités cohérentes | Renforcée : calibration multiclasses, aucun second calibrage indépendant au classement | CI en attente |
| 9 | Cote BSD >=1,20 | Présente : prix réel et marge de sécurité sur probabilité prudente | API réelle en attente |
| 10 | Rejet d'incertitude | Présent : historique insuffisant ou désaccord excessif | Seuils à auditer |
| 11 | Comparaison modèles | Présente : poids 2024 et fallback Poisson | Résultat hors échantillon en attente |
| 12 | Backtest 1X/X2/12 | Présent : référence calibrée, modèle calibré, mêmes matchs 2026 | Run GitHub Actions en attente |

Le statut **présent dans le code** ne signifie pas *performance supérieure prouvée*. Aucun résultat CI n'a été obtenu lors de cette intervention. En cas de qualité insuffisante, le poids du spécialiste reste zéro.
