# Filtre de confiance pour les scores exacts — problème des 1–1 répétés

## Constat empirique

Sur les 38 rencontres de Premier League d'octobre 2026, Dixon-Coles (ρ≈−0,08844) avait 27 matchs dont **1–1** était le mode. Le Poisson indépendant en avait 25. Les résultats réels avaient 5 scores 1–1. La somme des probabilités de 1–1 calculées par Dixon-Coles correspondait à 4,46 matchs, proche des 5 constatés. La correction ρ est responsable d'environ deux premières places supplémentaires et non des 27. Il n'y a aucune justification statistique pour remplacer arbitrairement 1–1 par 1–0 ou 2–1.

## Ce qui est corrigé

Une **couche de décision distincte du modèle probabiliste** gère la *recommandation d'un score exact unique*.

- Le `top_scores` conserve les classements et probabilités mathématiques exacts : si le score 1–1 est le plus probable, il reste en première position.
- Le champ `exact_score_signal` de l'API affiche `single_score` et `recommended_score`, ou `abstain` et `recommended_score=null`. En cas d'abstention, un Top 3 reste disponible.
- Les seuils (`min_top_probability` et `min_gap_percentage_points`) sont calibrés sur les **seuls matchs historiques** par entraînement chronologique mensuel.
- Valeurs prédéfinies de la politique : 80e percentile des probabilités Top 1, plus un écart d'au moins 1,0 point entre les deux premiers scores. Le percentile a été choisi pour limiter le nombre de *recommandations uniques*, non pour maximiser le taux de réussite rétrospectif.
- L'API ajoute `/api/score-signal/calibrate` (protégé) et `/api/score-signal/calibration` ; la calibration est enregistrée en SQLite et peut être empaquetée pour la Premier League.
- Les anciennes prédictions enregistrées restent des prédictions anciennes et ne deviennent pas des « abstentions » a posteriori.
- L'interface affiche `—` et « Aucun score unique recommandé » dans le bloc central si les seuils ne sont pas atteints ; les probabilités de tous les scores sont toujours visibles.

## Périmètre de validation

- Validation prévue : **374** rencontres de Premier League d'août 2025 à mai 2026, avec ajustements mensuels et aucune utilisation des rencontres du mois testé pour entraîner le modèle.
- Test rétrospectif séparé : 38 rencontres d'octobre 2026 ; aucune utilisation de leurs scores pour régler les seuils de la politique. **Cette règle a été conçue en novembre 2026 après avoir observé octobre ; le test d'octobre n'est PAS une preuve prospective indépendante.**
- En l'absence de calibration historique pour un championnat : pas de recommandation exacte unique ; le top des scores reste disponible.

## Ce qui n'est pas revendiqué

Aucun gain de log loss ou de précision exacte n'est garanti par le filtre : il laisse la distribution intacte. Son effet est de limiter les conseils isolés peu convaincants. Il faut des données plus prédictives (notamment xG, compositions, blessures, effets contextuels) et des périodes prospectives vraiment nouvelles pour envisager un gain intrinsèque de précision.
