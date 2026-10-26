# Mr XPRONOS — ML V2: 1–1 et validation rétrospective multisaison

Prédéclaration : 2026-10-26. Branche `research/single-ml-v2-20261024`, sans déploiement.

## Question (diagnostic, sans sélection post-hoc)
Le modèle annonce fréquemment 1–1 comme score *modal*. Un score modal (argmax) à 10 % de probabilité peut être le score **le plus probable** sans être prévu plus d'une fois sur dix. Il est incorrect d'assimiler **taux de 1–1 modal** et **probabilité 1–1 prédite**. Nous mesurons donc, pour les cinq mêmes modèles et matchs :
- part de 1–1 modaux, part des **véritables** 1–1 ;
- **moyenne des probabilités P(1–1)** des grilles 11×11 avant de lire le résultat, et biais en points par rapport à la fréquence réelle ;
- Brier binaire de la cellule 1–1, tranches de calibration, exact hits sur les prédictions 1–1 ;
- écart de probabilité top-1 / top-2, diagnostic alternatif à seuils FIXES de 0,005 / 0,01 / 0,02, **non optimisé, non déployé**.
Les différents paramètres ne sont pas retouchés pour faire mieux sur le test.

## Quatre périodes gelées (28 jours calendaires chacune)
1. 2025-03-01 → 2025-03-28 ;
2. 2025-09-01 → 2025-09-28 ;
3. 2026-03-01 → 2026-03-28 ;
4. 2026-09-01 → 2026-09-28.

Aucune période ne recoupe l'essai exploratoire 2026-10-20 → 2026-10-22. Les périodes sont indépendantes pour la comparaison de l'amélioration exploratoire mais les résultats ne peuvent pas être qualifiés de prédictions prospectives réellement émises. Les entraînements évoluent chronologiquement avec les matchs antérieurs à chaque journée, sans labels de la journée en cours. Hyperparamètres fixes (pas de tuning guidé par les résultats de l'évaluation), cadence 30 jours, données historiques chiffrées BSD/SportScore/OpenFootball authentifiées. Cohortes identiques pour les cinq modèles. Les xG/odds non documentés restent absents, ROI non calculé.

## Preuves statistiques
- exact-hit Top-1, Top-3, log-loss multinomial et Brier simplifié, P(1–1) et calibration ;
- intervalles de Wilson 95 % descriptifs sur les réussites ;
- 3 000 bootstrap **appariés par journée UTC, stratifiés par période**, comparant chacun des quatre concurrents à HistGradientBoosting sur le même dénominateur ;
- sensibilité par **blocs de sept jours** pour les dépendances dans les séries chronologiques (intervalles possiblement larges avec 16 blocs) ;
- rapports des 28 jours de chaque période et pool des quatre périodes **toutes obligatoires**, sans choix de la meilleure période ni de vainqueur sur le même jeu.

## Contraintes de sécurité et interprétation
Archives chiffrées demeurent dans GitHub. Pendant l'exécution, les matchs déchiffrés et prédictions match-par-match restent sur le runner; les artifacts contiennent **uniquement des agrégats par jour et par modèle**, pas les lignes individuelles. Chiffres historiques de date/match score sont non secrets mais aucun nouvel export du dataset individuel n'est effectué. Ni `main`, ni Telegram, ni Supabase, ni Neon, ni publication commerciale ne sont modifiés. Aucun retour sur investissement, accroissement garanti ou supériorité statistique ne sera annoncé sans preuve. Même un résultat bootstrap positif nécessite ensuite une validation réellement prospective, datée AVANT coup d'envoi.
