# Mr XPRONOS — Élargissement des scores groupés de 0 à 7 buts

**Statut : expérimental / aucune publication ou cote inventée.** Cette extension
n'altère pas les neuf groupes de scores exacts observés chez 1xBet.
Elle modifie seulement les critères permettant de présélectionner davantage
de rencontres. Même lorsqu'un match a une forte probabilité d'Under 7,5,
le pari groupé n'est gagnant que si un des **scores EXACTS du groupe** se produit.

## Six plafonds de buts évalués

| Match (buts FT) | Seuil Under | Nom interne |
|---|---|---|
| 0, 1, 2 | Under 2,5 | `ceiling_under_25` |
| 0 à 3 | Under 3,5 | `ceiling_under_35` |
| 0 à 4 | Under 4,5 | `ceiling_under_45` |
| 0 à 5 | Under 5,5 | `ceiling_under_55` |
| 0 à 6 | Under 6,5 | `ceiling_under_65` |
| 0 à 7 | Under 7,5 | `ceiling_under_75` |

Le système calcule **P(T≤2), P(T≤3), ..., P(T≤7)** depuis la matrice complète
des scores BSD V2, après fusion Under 2,5 V1. Les plafonds sont cumulatifs :
P(T≤2) ≤ P(T≤3) ≤ ... ≤ P(T≤7).
Il calcule aussi les bandes **exclusives** 0–2, 3–4, 5–7 et 8+ buts.
Cette distinction empêche de compter deux fois un résultat dans
une même probabilité, même si un match est admissible à plusieurs plafonds.

## Règles expérimentales (PAS des règles d'un bookmaker)

Les bornes ont été définies à l'avance pour le suivi prospectif :

- Probabilité estimée de respecter le plafond ≥ **62 %**.
- Probabilité propre au groupe des scores exacts ≥ **12 %**.
- Au moins **60 % de la masse de probabilité de ce groupe** sur les scores
  respectant le plafond examiné.
- Signal Double Chance cohérent pour le groupe retenu ; les anciennes
  règles H2H + Under 2,5 restent disponibles séparément comme référence.
- Une seule sélection est évaluée par match et **par plafond**. Le
  même match peut apparaître dans plusieurs analyses ; cela ne signifie
  pas plusieurs paris indépendants.
- Un groupe de pari n'est **jamais tronqué** pour l'adapter au plafond :
  par exemple G7 couvre toujours 2-3, 2-4 et 3-4. La probabilité du pari
  reste la somme de ses trois scores, et non P(Under 7,5).

Les nouveaux paramètres sont hypothétiques, non calibrés ni optimisés.
Le fait que presque tous les matchs puissent atteindre Under 7,5 rend
ce plafond peu sélectif à lui seul. Une cote 1xBet observée pour **le même
groupe et le même match** est indispensable pour calculer une espérance
de valeur ; les backtests historiques n'en disposent pas.

## Fichiers ajoutés / modifiés

- `bsd/grouped_total_goals.py` : CDF 2–7, bandes disjointes, choix d'un
  groupe compatible par plafond, contrôles d'intégrité et abstention.
- `bsd/grouped_correct_score_engine.py` : intègre les six politiques
  aux neuf groupes existants, aux probabilités de score et Double Chance.
- `bsd/grouped_correct_score_backtest.py` : résultats 2025 (échantillon
  chronologique) et 2026 (historique complet), couverture, taux de
  réussite, Brier du groupe et de chaque seuil Under, observé vs estimé,
  détail par mois et par groupe.
- `bsd/grouped_correct_score_prospective.py` : fige les décisions des
  six seuils sur les **nouvelles** prévisions avant match dans l'archive
  chiffrée ; les anciennes restent intactes.
- `bsd/grouped_correct_score_feed.py` et la prévisualisation
  `scores-groupes.html` : affichage filtrable des plafonds, uniquement
  quand les groupes/cotes du match sont documentés.
- `bsd/test_grouped_correct_score.py` : nouveaux tests sur les CDF,
  les cas à 5–7 buts, les groupes inchangés, l'absence de cotes fictives
  et la compatibilité des archives antérieures.

## Ne pas confondre « mieux couvrir » et « mieux prédire »

L'augmentation du nombre de candidats se mesure sur l'historique, mais
ne prouve pas un gain de fiabilité des groupes. Il faut comparer pour
chaque plafond les matchs, les sélections gagnantes, la couverture,
le Brier et les résultats prospectifs après la création de ces règles.

Le code demeure sur la branche de recherche et ne modifie pas le moteur
BSD V2 des pronostics simples en production.
