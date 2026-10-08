# Audit d'implémentation — spécialisation BTTS Oui / Non

Ce document décrit le code effectivement ajouté. **Les tests GitHub Actions et le nouveau backtest doivent encore être exécutés** avant d'affirmer que la précision est améliorée.

| N° | Amélioration | Statut technique | Vérification nécessaire |
|---|---|---|---|
| 1 | Classifieur BTTS indépendant | Implémenté | Comparer son Brier 2026 à Poisson/Dixon-Coles |
| 2 | Fréquence réelle des équipes marquent/encaissent | Implémentée | Tests sur données historiques réelles |
| 3 | Domicile/extérieur | Implémenté | Contrôle de couverture des rencontres locales |
| 4 | Force de l'adversaire | Implémentée | La concession de buts adverse contribue à la probabilité de marquer |
| 5 | BTTS moyen par championnat | Implémenté | Lissage vers moyenne générale si faible échantillon |
| 6 | Calibration séparée BTTS Oui/Non | Implémentée | Calibration 2025 sur le modèle BTTS et évaluation 2026 |
| 7 | Cote BSD réelle >= 1,20 pour BTTS | Implémenté via filtre commun à tous les marchés | Test en production avec API BSD ; aucun prix fictif |
| 8 | Backtest BTTS indépendant | Implémenté | Premier rapport GitHub Actions pas encore exécuté |

## Fonctionnement

- Historique point-in-time : seul le résultat d'une rencontre terminée au moins 4 heures plus tôt est utilisable.
- Entraînement logistique spécialisé sur janvier–août **2024**; validation du mélange Poisson/classifieur sur septembre–décembre 2024. Si le mélange n'améliore pas le Brier de validation de 0,001, son poids est **0**.
- Calibration propre à BTTS Oui/Non sur janvier–août **2025**. Surveillance des erreurs par marché sur septembre–décembre 2025.
- Backtest de référence sur **2026**, sur toutes les rencontres éligibles, même si un autre marché aurait finalement été choisi.
- La sortie BTTS Oui et la sortie BTTS Non sont complémentaires. Pas de paris corners, tirs, fautes.
- La production refuse les cotes <1,20 et les marchés sans cote BSD; UNDER_45 reste exclu.
- La valeur des cotes BSD historiques n'existe pas dans les fichiers de scores : on ne calcule pas de rentabilité rétroactive.
- La diversification des choix de paris n'est pas forcée.

## Fichiers modifiés/créés

- `bsd/bsd_v2_btts.py` : extraction des fréquences, features, entraînement/réglage, injection probabiliste.
- `bsd/bsd_v2_core.py` : comparaison avec les marchés existants.
- `bsd/bsd_v2_policies.py` : calibration BTTS spécialisée et qualité.
- `bsd/bsd_v2_publish.py` : moteur quotidien réel, cote vérifiée avant publication.
- `bsd/bsd_v2_shadow.py` : génération expérimentale.
- `bsd/bsd_v2_evaluate.py` : comparaison historique V1/V2.
- `bsd/bsd_v2_btts_backtest.py` : backtest Oui et Non par marché/ligue.
- `bsd/test_bsd_v2_btts.py` : six tests de régression.
- `.github/workflows/bsd-v2-validation.yml` : exécute le backtest BTTS et conserve son rapport.

## Étape d'acceptation

Ouvrir **BSD V2 - Validation experimentale** dans Actions, conserver `max_test=1000` et lancer. Vérifier les tests, puis `BSD_BTTS_BACKTEST`, `poisson_dixon_coles_baseline` et `specialized_calibrated`. Un résultat plus faible ou mal calibré invalide la prétention d'amélioration du classifieur, même si les tests unitaires réussissent.

La réussite technique d'une implémentation ne garantit ni plus de paris BTTS ni un gain financier.
