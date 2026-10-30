# ML V2 contre V3 — deuxième validation indépendante Top 5/10/20

**Protocole gelé avant exécution** le 30 octobre 2026, branche de recherche `research/single-ml-v2-20261024`. Aucune modification d'hyperparamètres des 8 modèles, des grilles, des poids ou des règles de sélection par rapport au backtest précédent.

## Mois complets non utilisés dans les précédentes évaluations quotidiennes

- **Avril 2025** : 2025-04-01 au 2025-04-30, 30 jours.
- **Juillet 2025** : 2025-07-01 au 2025-07-31, 31 jours.
- **Décembre 2025** : 2025-12-01 au 2025-12-31, 31 jours.
- **Juillet 2026** : 2026-07-01 au 2026-07-31, 31 jours.

**123 jours** au total. En particulier, ces dates ne chevauchent ni les quatre mois mai/août 2025 + mai/août 2026 du premier V2/V3, ni les périodes Top 5/10/20 antérieures (octobre 2025, janvier 2026, avril 2026, septembre 2026 ; novembre 2025, février 2026, juin 2026).

## Exécution et analyses fixées avant connaissance des résultats

1. Rejeu chronologique des rencontres réelles issues des mêmes archives historiques certifiées (source chiffrée et clé de déchiffrement sur le runner GitHub). Les modèles ne sont entraînés qu'à partir de matches finalisés des jours précédents. Aucun modèle n'est entraîné sur les résultats de la journée sélectionnée.
2. Huit modèles inchangés : les cinq V2 (HistGB, HistGB+DC hybride, LightGBM, CatBoost, Direct) et trois V3 (HistGB V3, Hybride V3, Direct V3), avec les versions et paramètres figés dans la branche.
3. Pour chaque jour UTC et chaque modèle, les mêmes rencontres candidates sont classées par probabilité de son score exact modal décroissante, avec départage stable par ID. Retenir exactement les **5, 10, 20** premiers. Chaque Top 5 est inclus dans son Top 10, lui-même inclus dans son Top 20.
4. Si une journée ne dispose pas d'au moins 20 rencontres évaluables pour un seul modèle, ou si les univers de rencontres/résultats diffèrent entre modèles, le mois échoue plutôt que d'exclure silencieusement des journées.
5. Comparer le nombre de scores exacts, taux individuel, Top 3, log-loss des choix, proportion de pronostics 1–1, journées avec **au moins 1, 2, 3** bons scores, par modèle et par K, mensuellement et au cumul.
6. Comparaison de trois paires *V3 − V2* à taille de liste identique, **4 000** bootstraps stratifiés par mois et groupés par jour (et analyse de sensibilité par blocs de 7 jours) pour les taux de réussite et les journées ≥1, ≥2, ≥3. Préciser la multiplicité des tests. Répéter exactement le comparateur déjà vérifié sans optimisation sur ces nouveaux résultats.
7. Les rapports d'agrégats par jour et par modèle sont archivés anonymement ; toutes les prédictions individuelles et la source déchiffrée restent temporairement sur le runner. Aucune modification de `main`, du site, de Telegram, des bases ou de l'API.

## Limites

Il s'agit d'un **rejeu historique**, pas de pronostics authentiquement archivés avant le coup d'envoi. La disponibilité des listes de rencontres à l'avance reste à confirmer ; aucune cote pré-match score exact certifiée n'est disponible pour calculer le ROI. Le résultat des nouveaux mois ne sera pas utilisé pour modifier les paramètres V3 dans cette étude.

## Liens de suivi

La branche conserve le premier protocole dans `research/ml_v3_topk_compare.py`; ce deuxième protocole utilise `research/ml_v3_topk_round2.py`, qui réutilise l'algorithme d'évaluation identique tout en fixant de nouvelles dates et une nouvelle graine statistique.
