# Backtest : consensus strict HistGradientBoosting + Dixon-Coles (Top 5 / 10 / 20)

**GitHub Actions #40945874686 : SUCCESS**, 3 mois historiques et rapport final validés le 29/10/2026. Règle et dates préenregistrées avant les calculs dans `ML_V2_CONSENSUS_TOPK_PROTOCOL.md`.

## Univers et méthode
20 825 matchs, 88 journées complètes (nov. 2025 : 30 journées, 7 591 matchs ; fév. 2026 : 28, 7 583 ; juin 2026 : 30, 5 651). Les cinq modèles d'origine prédisent sur le même univers quotidien ; le **sixième système** retient UNIQUEMENT les rencontres où HistGB et l'hybride prédisent le même score exact ; classement par minimum de leurs deux probabilités modales, avant d'observer les résultats. Aucune multiplication de probabilités, aucun choix à l'aide du score final. Il y a eu en moyenne 210,4, 225,8 et 156,9 accords par jour dans les trois mois, soit suffisamment pour **remplir les Top 5, Top 10 et Top 20 pendant les 88 jours**.

## Résultats cumulés

| Modèle | Top 5 : hits/440 (%), jours ≥1, jours ≥2 | Top 10 : hits/880 (%), jours ≥1, jours ≥2 | Top 20 : hits/1760 (%), jours ≥1, jours ≥2 |
|---|---|---|---|
| HistGradientBoosting | 78 (17,73 %), 53, 21 | 147 (16,70 %), 69, 47 | 282 (16,02 %), 85, 73 |
| Hybride Dixon-Coles | **88 (20,00 %), 56, 28** | 151 (17,16 %), 70, 48 | **289 (16,42 %)**, 84, 73 |
| LightGBM | 83 (18,86 %), 52, 21 | 148 (16,82 %), 71, 42 | 277 (15,74 %), 85, 76 |
| CatBoost | 77 (17,50 %), 50, 18 | 134 (15,23 %), 67, 43 | 272 (15,45 %), 83, 71 |
| Direct | 79 (17,95 %), 53, 19 | 155 (17,61 %), **77**, 50 | 278 (15,80 %), **87**, **79** |
| **Consensus strict** | **79 (17,95 %), 54, 21** | **157 (17,84 %), 71, 50** | **284 (16,14 %), 84, 73** |

Tous les dénominateurs de « jours » sont 88, **pas le nombre de scores exacts**. Top 5 = 440 choix, Top 10 = 880, Top 20 = 1760 par système.

### Résultats du consensus par mois (Top 5/10/20)

| Mois | Top 5 | Top 10 | Top 20 |
|---|---|---|---|
| Novembre 2025 (30 jours) | 19/150, ≥1:14 j, ≥2:5 j | 42/300, ≥1:22 j, ≥2:12 j | 77/600, ≥1:27 j, ≥2:19 j |
| Février 2026 (28 jours) | 38/140, ≥1:25 j, ≥2:10 j | 70/280, ≥1:27 j, ≥2:23 j | 118/560, ≥1:28 j, ≥2:27 j |
| Juin 2026 (30 jours) | 22/150, ≥1:15 j, ≥2:6 j | 45/300, ≥1:22 j, ≥2:15 j | 89/600, ≥1:29 j, ≥2:27 j |

### Incertitude du critère principal (au moins un bon score/jour)

IC descriptifs 95 %, différence **consensus – parent** en points de pourcentage, bootstrap 3 000 jours rééchantillonnés au sein des mois :

| Taille | Consensus – HistGB | Consensus – Hybride |
|---|---|---|
| Top 5 | [−4,55 ; +6,82] | [−10,23 ; +5,68] |
| Top 10 | [−2,27 ; +7,95] | [−4,55 ; +5,68] |
| Top 20 | [−4,55 ; +2,27] | [0 ; 0] |

Tous les intervalles contiennent zéro. **Aucune supériorité établie sur les deux parents pour la fréquence des journées ≥1 succès**. Pour le critère ≥2 réussites, au Top 5 le consensus (21 jours) est derrière l'hybride (28 jours) ; une analyse bootstrap supplémentaire par jour donne IC 95 % de l'écart de fréquence **[−14,77 ; −2,27] points**. Les tests sont exploratoires et nombreux, et ne sont pas ajustés pour comparaisons multiples.

### Interprétation opérationnelle

- **Top 5** : l'hybride est supérieur au consensus en scores exacts (88 contre 79), journées avec ≥1 (56 contre 54) et ≥2 (28 contre 21).
- **Top 10** : le consensus trouve un peu plus de scores exacts (157 contre 151 pour hybride et 147 pour HistGB), mais pour **au moins un score exact par jour**, la directe fait mieux (77/88 journées contre 71/88 pour consensus).
- **Top 20** : le consensus ne dépasse ni les 289 bons scores de l'hybride ni les **87/88 journées avec ≥1** de la classification directe. Pour ≥2, la directe est également première avec 79/88 contre 73/88 pour le consensus.
- La corrélation entre HistGB et hybride explique probablement que leurs accords ne produisent pas une garantie d'amélioration. Un accord n'est pas une preuve indépendante supplémentaire.

**Limites essentielles :** rejeu historique chronologique, pas de publication horodatée avant le coup d'envoi ; couverture de la journée visible rétrospectivement mais pas certifiée disponible en temps réel ; absence de cotes score exact pré-match pour évaluer des gains financiers. Aucun modèle n'a été déployé sur `main`, le site, Telegram ou les bases de production.

## Preuves
- [Workflow réussi](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40945874686)
- Artifacts de l'exécution : `mlv2-consensus-nov2025`, `mlv2-consensus-feb2026`, `mlv2-consensus-jun2026`, `mlv2-consensus-3months-final`, avec agrégats journaliers anonymisés et intervalles bootstrap (dont sensibilité blocs 7j).
