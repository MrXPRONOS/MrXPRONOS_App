# ML Hybride V3 — protocole figé du backtest Top 3 scores groupés (2026)

Date: 2 novembre 2026. Projet de recherche uniquement, branche `research/single-ml-v2-20261024`, aucun changement de production.

## Hypothèse
Une stratégie **Top 3** choisit chaque jour uniquement les trois rencontres que `machine_learning_v3_hybrid` classe au plus haut en probabilité de son **score exact modal** ; mêmes critères d'ordre qu'au Top 5, mêmes matchs sources, mêmes modèles V3 et mêmes scores groupés **fixés** dans `ml_v3_grouped_scores.py`. Aucun réentraînement du modèle avec les résultats évalués de la journée. Aucune sélection du groupe selon le score réel.

## Périmètre
Janvier–septembre 2026 : neuf mois calendaires complets, **273 journées**, **819 places de sélection Top 3**. Pour octobre : historique limité aux **24 premiers jours** (72 sélections), isolé des résultats principaux. Novembre et décembre non disponibles dans l'archive certifiée (cutoff 2026-10-24).

## Groupes fixes (proxy de recherche, pas les marchés réels proposés par 1xBet)
- H_LOW : 1:0 / 2:0 / 2:1.
- H_HIGH : 3:0 / 3:1 / 3:2.
- A_LOW : 0:1 / 0:2 / 1:2.
- A_HIGH : 0:3 / 1:3 / 2:3.
- DRAW_LOW : 0:0 / 1:1 / 2:2.

Chaque pronostic dont le score modal n'est dans aucun groupe sera compté comme **abstention** et demeurera dans le dénominateur original Top 3 ; aucune attribution du type « tout autre ». Aucune cote réelle de bookmakers disponible.

## Mesures préfixées
- Score exact simple vs groupé **sur les mêmes Top 3 et les mêmes 819 pronostics** ; succès Top 3 groupé = score réel appartient au groupe du score exact prédit.
- Nombre de journées avec au moins 1/2/3 bonnes sélections groupées ; nombre de journées avec au moins 1/2 bonnes sélections de score exact.
- Couverture (abstentions), variation par mois, contraste direct Top 3 vs Top 5 sur chaque journée, taux par groupes.
- Cote moyenne théorique d'équilibre sous hypothèse de mises égales et cotes uniformes pour les sélections couvertes. Elle ne doit PAS être confondue avec une cote réellement offerte ou une preuve de rentabilité.
- Aucun changement des paramètres/critères des Top 5/10/20 : leur recalcul dans le même replay sert de contrôle de cohérence.

## Limites
Les groupes de trois résultats augmentent mécaniquement la réussite par rapport à un score exact unique. Il s'agit d'un rejeu de données historiques, non de prévisions contemporaines certifiées prises avant les matchs. Le modèle, les règles de groupes et certains mois ont déjà été examinés dans d'autres recherches : ce n'est pas un test indépendant aveugle. Ni cotes officielles historiques 1xBet, ni ROI vérifiable. Ne pas lier le modèle aux flux live/site/Telegram avant décision explicite.
