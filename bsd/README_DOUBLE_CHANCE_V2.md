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
