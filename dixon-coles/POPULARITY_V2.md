# Popularité éditoriale V2 — sélection des matchs (Mr XPRONOS)

## Périmètre

Cette fonctionnalité donne une priorité **éditoriale**, non une probabilité de victoire ni une mesure réelle d'audience. Les scores exacts restent calculés par Dixon-Coles à partir d'un historique antérieur au coup d'envoi. Aucun résultat, cote, tendance de pari ni classement rétrospectif n'est lu pour calculer l'importance.

## Principes

| Critère | Règle |
|---|---|
| Compétition | Ligue des champions, Europa League, Premier League, Liga, Bundesliga, Serie A, Ligue 1, coupes principales, compétition féminine et autres ligues prises en charge |
| Club | Noms reconnus par alias **complets** : PSG, Paris Saint-Germain, Real Madrid, FC Barcelona, Manchester City, etc. |
| Equipes de jeunes et réserves | U17/U19/U21/U23, Castilla, II, B, academy, reserves : bonus de grand club interdit, pénalité de -60 |
| Equipes féminines | Distinguées des hommes, bonus de marque atténué plutôt qu'effacé |
| Nations | Table dédiée applicable aux compétitions de sélections nationales explicitement identifiées |
| Grandes affiches | +28 lorsque deux clubs reconnus ont un poids suffisant |
| Rivalités | +75 pour des paires **exactes** (Real-Barça, PSG-OM, Inter-Milan, etc.), uniquement entre catégories cohérentes |
| Phases de compétition | Finale +225, demi-finale +105, quart +62, huitième +35, play-offs +38, uniquement si la phase apparaît dans les métadonnées du fournisseur |
| Diversité | 4 matchs maximum par compétition dans le premier passage, puis complément au mérite si moins de 10 rencontres |
| Robustesse | Aucun match créé artificiellement ; limite quotidienne conservée à 10, historique et logos obligatoires |

L'ordre s'effectue par `importance` décroissante, puis coup d'envoi, puis ID stable. Un match moins coté peut sortir de la sélection si les données historiques du club ou les seuils ne permettent pas une prédiction valide.

## Sources

Le mode social `--source espn` découvre désormais 12 compétitions configurées : UEFA Champions League, Europa League, Conference League, Premier League, Liga, Bundesliga, Serie A, Ligue 1, FA Cup, League Cup, Women's Champions League, EFL Trophy.

La disponibilité de chaque compétition **doit être vérifiée dans les exécutions réelles** : les endpoints publics ESPN sont des données tierces, susceptibles de manquer de résultats complets, de modifier leur format et soumises aux conditions d'utilisation du fournisseur. Un championnat dont les données sont absentes, incohérentes ou insuffisantes ne produit aucun pronostic. Aucun score fictif n'est utilisé pour remplacer l'historique.

## Traçabilité

Chaque match sélectionné contient `importance`, `importance_reasons`, `popularity_class`, `home_team_category` et `away_team_category`. Ces champs montrent pourquoi la rencontre a été priorisée, sans prétendre mesurer l'audience ou la rentabilité.

**Attention :** l'ajout de compétitions et la modification des règles invalident la comparaison directe avec le backtest d'octobre 2026 effectué avec l'ancienne configuration. Il faut exécuter un nouveau backtest sans fuite temporelle, avec les mêmes sélections et sources V2, avant toute conclusion de performance statistique.
