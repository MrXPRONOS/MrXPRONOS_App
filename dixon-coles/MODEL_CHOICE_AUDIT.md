# Pourquoi le score 1–1 dominait et quelle correction a été apportée

## Diagnostic objectif, sans modifier le résultat d'octobre

Le modèle original a été entraîné sur **1 950 vrais résultats** antérieurs au 1er octobre 2026. La correction de dépendance était `rho=-0.08844`. Sur les 38 matchs du mois, Dixon-Coles plaçait 1–1 au premier rang 27 fois ; avec les **mêmes intensités** mais `rho=0`, 1–1 arrivait encore en tête 25 fois. Le facteur `1-rho` majorait le score 1–1 d'environ 8,84 %, mais **ne créait que deux premières places supplémentaires**.

Les 1–1 réellement constatés étaient au nombre de 5, contre 4,46 prédits en espérance par la somme de leurs probabilités. Choisir 1–1 comme *mode* de distribution n'équivaut pas à annoncer une probabilité élevée de 1–1.

## Résultats indépendants (développement et octobre)

Avant octobre, sur 374 rencontres entre août 2025 et mai 2026, la log loss était **2,89555 pour Dixon-Coles** et **2,89688 pour le Poisson réentraîné**. Dixon-Coles était donc meilleur d'environ 0,00134 en log loss. En octobre, le Poisson avait un avantage très faible, 3,04236 contre 3,04796. Sur 38 matchs, la moyenne de la différence était de 0,00560, avec une estimation de l'intervalle à 95 % de **[-0,0150 ; +0,0262]**, ce qui ne constitue pas une preuve robuste de supériorité du Poisson.

## Corrections du logiciel

1. Le champ `poisson_same_intensities_log_loss` réutilisait à tort la probabilité du Poisson entraîné séparément. Il utilise maintenant **les intensités Dixon-Coles avec rho fixé à zéro**, ce qui isole bien la contribution du correctif rho.
2. Les prédictions fournissent `score_top1_gap_percentage_points`, `top_scores_nearly_tied`, `score_1_1_probability`, `score_1_1_without_rho` et `rho_effect_on_p_1_1_percent`. Les petits écarts entre scores sont explicitement signalés dans l'interface.
3. Une comparaison chronologique sur des matchs **antérieurs** permet de choisir entre deux **modèles séparément entraînés**. Les deux reçoivent les mêmes matchs, les mêmes coupures, le même xi et la même régularisation.
4. Un bootstrap déterministe rééchantillonne les blocs mensuels. La sélection automatique n'accepte Dixon-Coles que lorsque sa borne inférieure de gain est positive et que son gain moyen dépasse **0,005 point de log loss**. Sinon, elle sélectionne le Poisson, modèle plus simple, comme repli prudent. Le moteur original Dixon-Coles reste disponible en mode explicite.
5. Une calibration validée est enregistrable en SQLite, utilisable automatiquement dans les prédictions de la compétition correspondante et **refusée si sa période se termine après l'instant prédit**.

Le changement **ne garantit pas** que Poisson ou Dixon-Coles soit systématiquement meilleur dans une prochaine période. Le gain de log loss constaté en octobre n'est **pas un objectif d'optimisation rétrospective**. La procédure de sélection est conçue pour réduire les risques de surapprentissage et éviter de présenter la correction rho comme une amélioration universelle.

Les sources sont celles déjà citées dans `dixon-coles/results/backtest_october_2026.md` et dans le rapport de calibration OpenFootball, avec données antérieures au 1er octobre 2026. Les mois d'octobre ne sont pas utilisés dans le choix du modèle.
