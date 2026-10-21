# Consensus des 6 systèmes — résultats vérifiés (2026)

**Source immuable :** [GitHub Actions — exécution 39511299147](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39511299147) (scores favoris prévus par chaque modèle avant les matchs).  
**Backtest consensus :** [GitHub Actions — exécution 39519713361](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39519713361).  
**Échantillon :** 81 154 rencontres, du 30 janvier au 19 octobre 2026, historique incomplet ; données de 2026 manquantes certains jours.

## Méthode

Chaque rencontre reçoit les 6 scores favoris des 6 moteurs indépendants dans leur exécution (Poisson, Dixon-Coles, Poisson bivariée, Bayésien Gamma, ML, Monte-Carlo).

- Unanimité : six votes identiques → accepter au seuil 6/6.
- Majorités moins strictes : au moins 5, 4 ou 3 voix pour le même score → accepter au seuil respectif.
- Ex aequo entre plusieurs scores au nombre maximal de voix → **s'abstenir**. Aucun tirage au sort, aucun recours au résultat du match.
- Le nombre de voix (p. ex. 5/6) **n'est pas** une probabilité de réussite de 83,3 %.
- À chaque seuil, le consensus est comparé à chaque modèle **sur exactement les matchs qu'il retient** (pas sur toute la base).

## Backtest intégral des scores exacts

| Majorité requise | Matchs proposés | Couverture | Pronostics exacts | Taux exact |
|---|---:|---:|---:|---:|
| ≥3/6 | 79 371 | 97,80294 % | 6 890 | 8,68075 % |
| ≥4/6 | 76 442 | 94,19376 % | 6 658 | 8,70987 % |
| ≥5/6 | 54 118 | 66,68556 % | 4 872 | 9,00255 % |
| **6/6** | **26 415** | **32,54923 %** | **2 707** | **10,24797 %** |

Répartition **exacte** des votes :
- Exactement 3 : 2 929 matchs.
- Exactement 4 : 22 324 matchs.
- Exactement 5 : 27 703 matchs.
- Exactement 6 : 26 415 matchs.
- Ex-aequo de tête : 1 783 matchs ; aucun score retenu.

## Évaluation de contrôle — du 1er août au 19 octobre 2026

Ces seuils ont été définis avant l'exécution de ce nouveau test. Comparaison ultérieure à conserver dans toute validation supplémentaire :

| Majorité requise | Matchs proposés | Couverture | Scores exacts | Taux exact |
|---|---:|---:|---:|---:|
| ≥3/6 | 33 525 | 98,27344 % | 2 619 | 7,81208 % |
| ≥4/6 | 32 452 | 95,12810 % | 2 538 | 7,82078 % |
| ≥5/6 | 23 118 | 67,76690 % | 1 876 | 8,11489 % |
| **6/6** | **10 880** | **31,89306 %** | **1 085** | **9,97243 %** |

**ATTENTION :** à 6/6, les six modèles donnent le même score : leur réussite est **également 9,97243 %** sur ce sous-ensemble. Ce filtre sélectionne des matchs plus faciles à prédire ; il ne prouve pas que combiner les modèles améliore la qualité d'une prédiction unique.

### Filtre qualité championnat (connu avant les matchs)

Quand on exige **au moins 100 matchs passés dans le même championnat** (dans les prédictions 2026 archivées, jamais les résultats futurs), sur la période août–octobre :

| Majorité requise | Matchs retenus | Couverture de toute la période | Scores exacts | Taux exact |
|---|---:|---:|---:|---:|
| ≥4/6 | 12 905 | 37,82904 % | 1 407 | 10,90275 % |
| ≥5/6 | 10 000 | 29,31348 % | 1 090 | 10,90000 % |
| 6/6 | 6 499 | 19,05083 % | 715 | 11,00169 % |

Le critère de championnat sélectionne encore un sous-ensemble plus restreint et sans garantie : **aucune preuve d'un avantage sur un modèle seul sur ces mêmes matchs**.

## Recommandations de recherche
- **5/6** : bon compromis descriptif entre couverture et précision ; ce n'est pas la preuve d'un gain dû aux votes.
- **6/6** : mode strict, fréquence de diffusion plus faible, taux observé historiquement plus élevé.
- **4/6** : plus de volume ; sur août–octobre, le taux reste 7,82 %. Pas convaincant seul pour annoncer des “coups sûrs”.
- **Pas de score** : égalité des voix, ou moins de voix que le seuil choisi.
- **ROI indisponible** : aucune cote *score exact* pré-match horodatée dans l'historique. N'annoncer aucun profit fictif.
- Ne pas confondre votes de modèles corrélés et indépendance statistique. Ne pas compter 6 accords comme une probabilité de 100 %.

Détails du workflow : `summary.json`, `all_consensus_decisions.csv`, `monthly.csv`, `leagues_100plus.csv`.
