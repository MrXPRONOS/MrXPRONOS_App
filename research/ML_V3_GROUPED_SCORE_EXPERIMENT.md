# Scores exacts groupés type bookmaker — module expérimental Hybride V3

**Date du protocole** : 2026-11-02. **Aucun déploiement de paris ou sur le site.**

## 1. Ce que ce code fait exactement

Le moteur historique `research/single_ml_v2.py` produit les pronostics `machine_learning_v3_hybrid` dans `all_predictions.csv`. Le module `research/ml_v3_grouped_scores.py` lit ce CSV, reproduit exactement le choix quotidien **Top 5, Top 10 et Top 20** par probabilité du score modal décroissante, et **ensuite seulement** associe chaque score modal à un **groupe fixé avant de voir les résultats**. Le score final sert exclusivement à vérifier le groupe. Le classement et les matchs choisis restent inchangés.

Les groupes ci-dessous sont **des proxys de recherche à trois scores fixes, pas la vraie liste des groupes commercialisés par 1xBet pour chaque match** :

| Nom | Scores |
|---|---|
| H_LOW | 1:0, 2:0, 2:1 |
| H_HIGH | 3:0, 3:1, 3:2 |
| A_LOW | 0:1, 0:2, 1:2 |
| A_HIGH | 0:3, 1:3, 2:3 |
| DRAW_LOW | 0:0, 1:1, 2:2 |

Toutes les catégories sont disjointes et comportent trois scores. Les autres scores prévus par le modèle (comme 0:4, 3:3, 4:0) sont **des abstentions**, jamais « tout autre » par défaut. Les abstentions restent dans le dénominateur des Top K afin de mesurer les sélections qu'une stratégie de paris groupés ne couvrirait pas.

## 2. Vérifications

- **7 tests unitaires synthétiques validés** pour l'inclusion exact→groupe couvert, l'ordre Top K, l'absence de fuite du résultat, les résultats cohérents avec le marché 1X2, les abstentions, et les 10 périodes de 2026.
- Contrôles sur les vraies archives : statistiques distinctes **Top 5, Top 10 et Top 20**, les groupes et le score exact initial sont évalués sur les **mêmes pronostics et matchs** ; si un jour a moins de 20 pronostics, échec explicite.
- Rapport par mois et cumul principal **janvier–septembre 2026 : 273 jours complets** ; octobre 1–24 (24 jours disponibles) **isolé**.
- Indicateurs : taux de scores exacts simples (sur K), taux des scores groupés (sur K, et séparément sur les matchs couverts), taux de **couverture**, journées avec 1/2/3 résultats groupés, bonus purement mécanique de couverture, groupement par catégorie, issue 1X2 pour contrôle, cote décimale théorique d'équilibre **sans frais** calculée comme 1/p empirique, et affichage d'absence de cotes réelles.

## 3. Ce que le résultat ne montrera PAS

Une hausse du taux de réussite est **mécanique** car un groupe couvre **3 résultats** contre 1 pour le score exact. Cette hausse **n'est pas une amélioration du modèle Hybride V3**, ni une preuve de rentabilité : les marchés groupés paient normalement une cote inférieure. Les groupes proposés diffèrent potentiellement d'un match à l'autre ; aucune cote ni groupe **réel historique** 1xBet n'est présent dans les archives certifiées. Toute extrapolation de ROI ou recommandations de mise est interdite sans ces données.

Cette expérimentation est indépendante de la sélection des huit modèles et ne modifie aucun composant de production.

## 4. Preuves & fichiers

- Code : `research/ml_v3_grouped_scores.py`
- Tests : `research/test_ml_v3_grouped_scores.py`
- CI rapide (7 tests passés) : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/41524206815
- Rejeu 2026 : `.github/workflows/research-ml-v3-grouped-scores-2026.yml`, dernier lancement autorisé : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/41524431995
- Les résultats historiques ne doivent être présentés comme **vérifiés** qu'après que les dix mois et le job d'agrégation aient terminé avec succès.
