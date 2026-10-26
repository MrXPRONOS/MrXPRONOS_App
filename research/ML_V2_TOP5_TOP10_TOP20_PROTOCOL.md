# Mr XPRONOS : sélection quotidienne Top 5 / Top 10 / Top 20

Protocole fixé avant exécution de la nouvelle étude sur la branche de recherche `research/single-ml-v2-20261024`. Sans effet en production.

## Question

Pour **chaque journée UTC**, chaque modèle analyse **tous les matchs certifiés de la journée** (nombre de matchs variable selon les archives). Puis, **indépendamment** des autres modèles, il sélectionne exactement 5, 10 et 20 matchs : les plus fortes probabilités de son score exact le plus probable (`top_probability`). En cas d'égalité : ordre alphabétique déterministe sur l'identifiant du match. Le rang est défini avant d'examiner son résultat final. Le **Top 5 est inclus dans le Top 10, inclus dans le Top 20**, pour chaque modèle et chaque journée.

Les cinq modèles : HistGradientBoosting, ML + Dixon-Coles hybride (pondération en absence de calibration hors échantillon), LightGBM, CatBoost et classification directe.

**Important :** `top_probability` est la confiance estimée du *score exact modal* ; elle n'est pas une probabilité de **rentabilité**, elle peut être imparfaitement calibrée. Nous ne filtrons pas les matchs en utilisant leur score final, leur cote a posteriori ou leur résultat. Tous les modèles évaluent le **même univers de rencontres par journée** ; leurs 5/10/20 rencontres **peuvent être différentes**. Une comparaison de taux n'est donc PAS une comparaison match-par-match appariée des sélections. Les intervalles bootstrap sont appariés **par journée**, avec une analyse de sensibilité par blocs de sept jours.

## Quatre mois distincts, enregistrés à l'avance

| Mois | Début UTC | Fin UTC | Journées |
|---|---|---|---:|
| Octobre 2025 | 2025-10-01 | 2025-10-31 | 31 |
| Janvier 2026 | 2026-01-01 | 2026-01-31 | 31 |
| Avril 2026 | 2026-04-01 | 2026-04-30 | 30 |
| Septembre 2026 | 2026-09-01 | 2026-09-30 | 30 |

**Total : 122 jours et 122 × 5 = 610 sélections Top 5, 1 220 sélections Top 10, 2 440 sélections Top 20 par modèle**, si les 122 journées disposent toutes d'au moins 20 matchs et que l'entraînement/les contrôles aboutissent. Ces sélections sont *comptées en matchs-journées par modèle*, pas en rencontres distinctes entre plusieurs modèles.

## Entraînement et comparabilité

Archives historiques 2024–2026 authentifiées, cohortes d'entraînement chronologiques sans scores du jour courant, modèles et hyperparamètres tels que validés dans le backtest précédent, réentraînement tous les 30 jours calendaires, `auto_tune=False` et `max_eval=0`, sans chercher sur les résultats des quatre nouvelles périodes les meilleurs paramètres ni les meilleures journées. Les quatre mois ne recoupent pas l'essai exploratoire d'octobre 2026 (20–22).

## Indicateurs prévus

Pour chaque modèle et chaque Top-K, chaque mois et l'ensemble des mois :
- **Taux de scores exacts** : scores exacts trouvés / `K × nombre_de_journées`.
- **Nombre de scores exacts**, réussite Top 3, moyenne de confiance et log-loss sur les matchs sélectionnés.
- **Nombre moyen de bons pronostics par jour**, proportion de journées avec au moins un succès.
- Part du score 1–1 parmi les pronostics retenus (utile pour dépister une concentration).
- Intervalles descriptifs Wilson 95 % sur le taux Top 1 ; **4 000** rééchantillonnages stratifiés et appariés des journées pour les écarts entre modèles de même K, et pour la différence de taux Top 10/20 contre Top 5 du même modèle. Sensibilité par blocs de sept jours.

Les chiffres `hits` augmentent mécaniquement lorsque K augmente (Top 5 inclus dans Top 10 inclus dans Top 20). **Ne pas interpréter le simple nombre brut de succès comme une preuve de supériorité du Top 20** ; comparer le taux de réussite, les intervalles et la charge d'envoi.

## Limites

Backtest historique **rejoué** : ce ne sont pas des pronostics réellement archivés avant coup d'envoi. Sélection "tous les matchs de la journée" réalisée rétrospectivement à partir de l'ensemble des rencontres historiques de cette date (la disponibilité prospective avant coup d'envoi n'est pas prouvée). Pas de xG certifiés historiques ni de cotes pré-match pour calculer le ROI. Pas de promesse de rentabilité.

Les fichiers de matchs et les prédictions individuelles restent dans `/tmp` du runner GitHub ; les archives produites partagent seulement des agrégats par modèle/jour/K. Aucun déploiement, aucune modification de `main`, Telegram, site, base client, Supabase ou Neon.
