# Audit de la V2 BSD — 8 octobre 2026

Cette V2 est **isolée** de la V1, des publications et du site. Le résultat du nouveau workflow doit être évalué avant toute bascule.

| # | Amélioration proposée | État du code | Limite de validation |
|---|---|---|---|
| 1 | Classement : fiabilité vs cote | **Implémentée dans V2** | Mode fiabilité sans filtrage par cote; mode valeur requiert des cotes réelles fournies |
| 2 | Calibration des probabilités | **Partielle** | Calibration par marché+tranche sur 2025, bornée ; calibration V2 à évaluer en 2026 et en prospectif |
| 3 | Force attaque/défense adversaire et récence | **Implémentée dans V2** | Modèle heuristique à comparer à V1, pas d'optimisation automatique prouvée |
| 4 | Baselines par championnat | **Implémentée dans V2** | Shrinkage vers moyenne globale si peu de matchs ; championnats sans ID isolés moins précisément |
| 5 | Dixon-Coles / Poisson | **Implémentée pour comparaison** | Rho ajusté sur 2024, accepté uniquement si améliore validation 2024 ; pas de garantie sur 2026 |
| 6 | Backtest walk-forward temporel | **Partielle** | Index temporal, entraînement 2024, calibration 2025, test 2026. Les snapshots de cotes/effectifs avant match sont indisponibles |
| 7 | Contrôle de qualité par match/marché | **Partielle** | Nombre de matchs, fraîcheur, échantillon de championnat, seuil, sélection vide. Pas encore de taux d'erreur prospectif par ligue/marché |
| 8 | Valeur avec cotes réelles | **Partielle** | Mode EV calculé si cotes fournies par un autre composant; **pas de récupération ni association de cotes BSD/1xBet** |

## Règles
- 16 marchés : 1X2, DC, BTTS, Over/Under 1.5, 2.5, 3.5, 4.5 ; aucune statistique corners/tirs/fautes.
- Aucun code de coupon bookmaker inventé. Chaque sélection a un identifiant **interne** et le champ `bookmaker_selection_code=null`.
- Une seule sélection par match ou aucune. Ce classement **optimise la probabilité estimée**, pas les gains, tant qu'aucune cote réelle n'est présente.
- La valeur attendue (EV) est `probabilité × cote - 1` et exige de vraies cotes d'avant-match pour avoir un sens.
- Seuls les matchs achevés il y a 4 heures au minimum alimentent un pronostic : approximation conservatrice de disponibilité des résultats.
- Entraînement Dixon-Coles janvier–août 2024, validation septembre–décembre 2024; calibration 2025, comparaison 2026.
- Aucune publication automatique, aucune modification de `data.json` et aucune écriture Supabase/Telegram.

## Validation
Actions → **BSD V2 - Validation experimentale** → Run workflow.

Le workflow lance les tests unitaires et génère un rapport `bsd/v2_backtest_report.json` comme artefact, sans afficher l'historique BSD brut ni le publier. Un ancien succès V1 ne valide **pas** V2. Comparer le taux de réussite, Brier, la couverture, et les stratégies fixes sur les **mêmes rencontres**. Aucun modèle n'est déclaré supérieur avant cette analyse.

## Travaux complémentaires pour une implémentation de bout en bout
1. Vérifier le workflow et réparer toute régression.
2. Ajouter un véritable collecteur d'odds historiques avant match par bookmaker si les droits et endpoints BSD l'autorisent.
3. Faire un suivi prospectif quotidien des pronostics horodatés.
4. Entraîner des politiques de sélection avec validation temporelle multi-années et comparer à V1 sur échantillons strictement identiques.
5. Envisager un workflow shadow quotidien avant toute activation de publication.
