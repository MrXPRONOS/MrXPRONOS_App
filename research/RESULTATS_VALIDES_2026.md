> **AUDIT SOURCE IMPORTANT — 21 octobre 2026 :** Nous avons constaté que l'endpoint SportsAPI Pro `/v1/football/games/allscores` retourne en réalité PLUSIEURS sports (champ `sportId`: 1=football, 3=tennis, 8=volley). Le vieux collecteur `allmatches.py` n'a pas conservé `sportId`. Par conséquent, les chiffres historiques de 81 154 rencontres documentés ci-dessous ne sont **pas un backtest vérifié 100 % football** et ne doivent pas servir de performance marketing. Ils restent archivés à titre de diagnostic méthodologique. Le test ponctuel du 20 octobre, refait en filtrant `sportId=1`, porte sur 187 matchs de football : [run validé](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39522118027). Les entraînements sur ce jour utilisent une liste conservatrice de 97 compétitions identifiées football, sans garantie d'exhaustivité historique. Un recalcul annuel avec identifiants de sports certifiés reste nécessaire.

# Mr XPRONOS — Résultats audités des scores exacts, 2026

## Provenance
- Historique calculé par GitHub Actions : [run 39511299147](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39511299147).
- Audit statistique indépendant des probabilités sauvegardées : [run 39518710055](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39518710055).
- Date de vérification : 20 octobre 2026.
- Période réellement couverte : 30 janvier au 19 octobre 2026. **240 jours représentés sur 292 depuis le 1er janvier : 52 dates sans rencontres terminées dans l'archive**. La base est donc incomplète.
- 81 154 matchs distincts, 486 924 lignes de prédictions, 3 388 noms de compétitions, dont 178 avec au moins 100 matchs (43 970 matchs).
- 81 journées récupérées sur 133 requêtes, 52 appels échoués. Ne pas annoncer une couverture exhaustive de 2026.

## Six modèles de scores exacts — comparaison sur les mêmes matchs

| Modèle | Bons scores Top 1 | Top 1 % | Top 3 % | Log-loss exact score |
|---|---:|---:|---:|---:|
| Poisson bivariée | 7 088 | 8,7340 | 24,7271 | 3,147006 |
| Poisson | 7 073 | 8,7155 | 24,7172 | 3,147051 |
| Dixon-Coles | 7 029 | 8,6613 | 24,8367 | 3,147009 |
| Machine Learning | 6 994 | 8,6182 | 24,6642 | **3,131897** |
| Monte-Carlo | 6 847 | 8,4370 | 23,2533 | 3,316097 |
| Bayésien Gamma | 6 780 | 8,3545 | 23,0562 | 3,136490 |

Les résultats sont des fréquences historiques, pas des garanties de réussite ou de rentabilité.

### Incertitude et comparaison par journées UTC appariées
1 800 tirages bootstrap de journées entières sur les mêmes matchs :
- Poisson bivariée vs Poisson, avantage Top 1 observé **+0,0185 point** ; intervalle 95 % **[+0,00121 ; +0,03526] point**. Gain minuscule, peu pertinent commercialement.
- Machine Learning vs Poisson : gain de log-loss **0,015154** ; intervalle 95 % **[+0,01221 ; +0,01825]**. Le ML est meilleur pour attribuer la probabilité au score effectivement survenu, pas pour trouver le Top 1 le plus souvent.
- Bayésien Gamma vs Poisson : gain de log-loss **0,010561** ; intervalle 95 % **[+0,00803 ; +0,01307]**.
- Dixon-Coles n'a pas de progrès Top 1 significatif clair par rapport à Poisson : intervalle **[-0,11679 ; +0,01156] point**.
- Attention : l'incertitude d'échantillonnage ne corrige pas les imperfections de l'historique.

## Correction de calibration strictement chronologique (1 avril–19 octobre)
Pour chaque journée, le réétalonnage du **seul événement “le score favori du modèle est exact”** utilise exclusivement les résultats des journées précédentes. Ni le classement des scores ni toute la grille de probabilités ne sont modifiés.

66 438 matchs évalués par modèle :

| Modèle | Confiance brute % | Confiance recalibrée % | Réussite réelle % | Brier avant | Brier après |
|---|---:|---:|---:|---:|---:|
| Poisson | 11,9534 | 9,2705 | 8,7284 | 0,0803868 | **0,0793426** |
| Dixon-Coles | 12,0910 | 9,2366 | 8,6547 | 0,0799214 | **0,0787359** |
| Bivariée | 11,9603 | 9,2838 | 8,7510 | 0,0805501 | **0,0795191** |
| Bayésien | 11,3381 | 8,7090 | 8,4304 | 0,0776843 | **0,0768640** |
| Machine Learning | 11,3093 | 9,0689 | 8,6396 | 0,0793680 | **0,0786465** |
| Monte-Carlo | 11,6743 | 8,9971 | 8,4425 | 0,0779751 | **0,0769483** |

Les intervalles 95 % de l'amélioration de Brier sont entièrement positifs pour les six modèles en bootstrap par journées (1 200 tirages). Ce résultat améliore la calibration du **score favori**, pas toutes les probabilités d'un pari combiné.

## Approches conditionnelles
- xG : test exploratoire sur 143 matchs d'un autre échantillon. Dixon-Coles 20 scores exacts (13,986 %), Poisson+xG provisoires 16 (11,189 %). Données de fin de match non certifiées complètes ; ce sous-échantillon **n'est pas comparable** à l'ensemble des 81 154 rencontres. L'archive de backtest étendue ne comporte pas de xG.
- Cotes : aucun jeu de cotes **du score exact**, horodatées avant le coup d'envoi, dans l'historique validé. Impossible de calculer sérieusement une rentabilité (ROI) ou l'intérêt d'un modèle ajusté au marché.
- Monte-Carlo : méthode de simulation, pas nécessairement modèle indépendant ; sa granularité de simulation et ses très faibles probabilités nécessitent de la régularisation avant une éventuelle utilisation publique.

## Décisions techniques
- Conserver Poisson bivariée, Poisson, Dixon-Coles et ML comme candidats, sans désigner un modèle “gagnant garanti”.
- Utiliser la calibration walk-forward pour la **probabilité du score favori**, avec affichage explicite de ses limites.
- Mesurer les performances par championnat et période, auditer les 52 jours absents.
- Ne pas fusionner les changements dans `main` sans revue des résultats sur données plus complètes et contrôle qualité.
- Aucun modèle ne justifie à lui seul une recommandation de mise automatique sur score exact.

Détails et export CSV disponibles dans les artefacts des deux workflows ci-dessus (rétention GitHub limitée).
