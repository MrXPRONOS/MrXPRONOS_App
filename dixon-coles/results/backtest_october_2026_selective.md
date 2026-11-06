# Problème des 1–1 répétitifs : audit du filtre de confiance

Période : **38 matchs de Premier League, 1er–31 octobre 2026**. Entraînement strictement antérieur au 1er octobre ; seuils de filtrage issus de **374 matchs en 2025–2026**, jamais du mois d'octobre. L'outil de filtrage a néanmoins été conçu **après avoir vu octobre** : le test reste rétrospectif et ne constitue pas un historique de prévisions réellement publiées avant les rencontres.

## Résultat sur octobre

| Indicateur | Dixon-Coles original | Poisson indépendant (mode automatique) |
|---|---:|---:|
| 1–1 en tête du classement brut | 27 | 25 |
| 1–1 **recommandés comme score unique** après filtrage | **5** | **2** |
| Matchs avec une recommandation unique | 11/38 | 10/38 |
| Abstentions explicites | 27/38 | 28/38 |
| Exactitudes parmi les recommandations | 1/11 (9,09 %) | 2/10 (20,0 %) |
| Top 1 brut correct (avant abstention) | 7/38 | 6/38 |
| Log loss sur tous les matchs (inchangée) | 3,047956 | 3,042360 |

Une abstention n'est **ni une prédiction correcte ni une victoire**. La réduction de 1–1 recommandés n'est **pas** un gain démontré de précision intrinsèque.

## Règle historique publiée

Sur 374 matchs de Premier League observés chronologiquement entre le 1er août 2025 et le 31 mai 2026 :

| Paramètre / métrique | Dixon-Coles | Poisson |
|---|---:|---:|
| Probabilité Top 1 minimum (80e percentile) | 13,0637 % | 12,7474 % |
| Écart minimum entre 1er et 2e scores | 1 point de pourcentage | 1 point de pourcentage |
| Matchs avec signal unique | 55/374 | 47/374 |
| 1–1 classés premiers (brut) | 264/374 | 230/374 |
| 1–1 recommandés après filtrage | 36/374 | 16/374 |
| Réussite Top 1 brute | 11,76 % | 12,03 % |
| Réussite sur les seuls signaux (sélective) | 14,55 % | 12,77 % |

## Fonctionnement

1. Le moteur produit la distribution des scores exacts. Il ne modifie **jamais** les probabilités ni l'ordre des scores pour « fabriquer » de la variété.
2. Si les seuils de validation historique ne sont pas franchis, l'interface affiche **« Aucun score unique recommandé »** et les trois premiers scores possibles.
3. La distinction entre mode mathématique et recommandation est conservée dans l'historique et l'API (`exact_score_signal`).
4. Les compétitions sans calibrage historique n'affichent pas de recommandation unique ; les probabilités restent consultables.

Limites : échantillon d'octobre réduit, forte abstention, absence de preuve prospective ; la performance peut varier sur des périodes futures. L'amélioration des prévisions exactes à l'aide de nouvelles variables nécessite une évaluation indépendante supplémentaire.

Sources : résultats historiques CC0 OpenFootball ; scores d'octobre contenus dans le CSV de résultats documenté avec le backtest précédent.
