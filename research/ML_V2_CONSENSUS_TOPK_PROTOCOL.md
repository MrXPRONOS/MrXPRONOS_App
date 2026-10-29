# Protocole gelé avant exécution : Top 5/10/20, consensus HistGB + hybride

Branche dédiée : `research/single-ml-v2-20261024`. Les deux moteurs historiques restent inchangés. Il s'agit d'un **sixième système** de recherche, non d'un réentraînement d'un nouveau modèle.

## Définition exacte de « là où ça colle »

Pour chaque rencontre historique de chaque journée UTC, HistGradientBoosting et `machine_learning_hybrid` produisent chacun un score exact (ex. `2:1`) et une probabilité de ce score. Un match devient candidat au **consensus** si et seulement si les deux scores exacts sont **strictement identiques**. Les matchs en désaccord sont exclus. Les matchs en accord sont triés par la **plus petite** des deux probabilités, du plus fort au plus faible. Une identité stable de rencontre sert à départager les ex æquo. Le Top 5 contient les cinq premiers accords, le Top 10 les dix premiers, le Top 20 les vingt premiers. **Si seulement 3 accords sont trouvés, les trois listes ont 3 matchs ; aucun désaccord n'est injecté pour remplir le quota.**

Les cinq modèles historiques (HistGB, hybride, LightGBM, CatBoost, directe) continuent indépendamment de produire **exactement** 5, 10 et 20 choix par journée, par probabilité modale décroissante, sur le **même univers complet de rencontres**. Les choix entre modèles ne portent pas nécessairement sur les mêmes rencontres ; leurs comparaisons doivent être vues comme des **stratégies de sélection quotidiennes**, pas un test purement apparié sur les mêmes pronostics.

## Mois indépendants gelés AVANT lecture des résultats

- **Novembre 2025** : 2025-11-01..2025-11-30 (30 jours).
- **Février 2026** : 2026-02-01..2026-02-28 (28 jours).
- **Juin 2026** : 2026-06-01..2026-06-30 (30 jours).

**88 journées**, trois mois complets non recouverts par l'étude quotidienne Top-K précédente (octobre 2025, janvier 2026, avril 2026 et septembre 2026). Tous les matchs historiques certifiés sur ces journées sont analysés puis triés. Les mêmes règles, données antérieures aux résultats, versions de modèles et cadence 30 jours de l'étude antérieure restent utilisées, sans optimisation sur les mois ciblés.

## Mesures et critères de comparaison

Pour chacun des 6 systèmes, chaque K et chaque mois :
1. Nombre total de prédictions retenues et nombre de **journées ayant réellement K pronostics** (critique pour le consensus).
2. Nombre total de scores exacts réussis et taux de succès **sur les matchs réellement retenus** ; celui-ci est conditionnel à la disponibilité des accords, donc n'est pas directement comparable à une sélection pleine si le consensus manque de candidats.
3. Nombre de journées avec **au moins 1 / 2 / 3** scores exacts ; les journées avec zéro accord comptent **comme zéro réussite**. Ce sont les critères d'intérêt principal pour un service publiant tous les jours.
4. Histogramme des 0, 1, 2, 3… scores exacts par jour, moyenne de succès par jour, part du score 1–1 dans les choix.
5. **3 000 bootstraps par journée**, stratifiés par mois, et sensibilité par blocs de sept jours (mêmes journées rééchantillonnées pour chaque système), pour les différences de **proportion de journées avec ≥1 score exact** entre le consensus et chacun de ses deux parents. Un IC recouvrant zéro ne permet pas de conclure à une amélioration.
6. Comparaison de référence des cinq modèles et du sixième système ; possibilité qu'une stratégie de consensus ait un taux conditionnel élevé mais peu de sélections quotidiennes : **ne pas confondre**.

Aucune lecture des résultats des matchs ne sert au calcul de l'accord, du rang, ou du poids. Les probabilités des parents sont utilisées sans les multiplier : ce ne sont pas deux preuves indépendantes. Il ne s'agit pas d'une combinaison de grilles de probabilité 121 cellules ; seulement d'une **sélection filtrée par accords**.

## Limites et confinement

Rejeu historique rétrospectif avec liste de matchs complétés ; la visibilité de toutes les rencontres **avant** les coups d'envoi n'a pas été attestée. Cotes historiques exact score non disponibles, pas de calcul de rendement, pas de garantie de gains. Les scripts ne déplacent ni ne publient les pronostics en production. Seuls les agrégats par jour et modèle sont archivés ; les prédictions individuelles et archives déchiffrées restent sur les runners GitHub isolés. PR #227 en brouillon, pas de fusion `main`.
