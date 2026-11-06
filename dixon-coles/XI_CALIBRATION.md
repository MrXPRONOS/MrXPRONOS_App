# Optimisation de ξ sur des résultats réels — protocole reproductible

## Périmètre

- **Source réelle publique indépendante** : [OpenFootball / football.json](https://github.com/openfootball/football.json), données de matchs sous [CC0 1.0](https://github.com/openfootball/football.json/blob/master/LICENSE.md). Aucune donnée ni aucun moteur de l'ancien projet Mr XPRONOS n'est utilisé.
- **Championnat pilote** : Premier League anglaise, identifiant `of:ENG-PL`.
- **Données d'apprentissage et contexte historique** : saisons 2021-22, 2022-23, 2023-24, 2024-25 ; les saisons 2025-26 et 2026-27 sont aussi importées pour le test ultérieur et les prédictions récentes, mais jamais utilisées pour sélectionner ξ lors du protocole pilote.
- **Validation qui choisit ξ** : du 01/08/2024 inclus au 01/06/2025 exclu (saison 2024-25). Blocs successifs de **deux mois**. Pour chaque bloc, le modèle est réentraîné exclusivement sur les matchs terminés **avant le premier jour du bloc**, jamais sur les résultats du bloc. Les équipes comptant moins de cinq matchs d'entraînement sont exclues des prévisions de ce bloc.
- **Jeu de test final indépendant** : du 01/08/2025 inclus au 01/06/2026 exclu. Ce jeu n'intervient **jamais** dans le choix de ξ. Il vérifie seulement la performance du ξ déjà choisi.
- **Critère de sélection** : plus faible `mean_exact_score_log_loss` (= moyenne des `-ln(P_DC(score observé))` sur des rencontres hors entraînement), et non le taux de bons pronostics Top 1. C'est une mesure strictement propre de la qualité de la distribution prédictive de scores.
- **Candidats préfixés** : `0`, `0.0015`, `0.003`, `0.0065`, `0.010`, `0.016`, `0.025`, `0.040` **par demi-semaine de 3,5 jours**. `0.0065` est la référence historique et doit obligatoirement être présente. En cas d'égalité numérique, proximité de cette référence puis valeur la plus petite.
- **Garde-fous** : au moins 500 matchs d'entraînement avant chaque bloc retenu, au moins 4 blocs, au moins 160 scores évalués. Les candidats sont comparés sur le **même ensemble exact** de rencontres ; aucune prédiction n'est inventée en cas d'échec d'optimisation. Les données fictives ou manuelles sont refusées pour l'optimisation réelle. Les données complètes sont filtrées à l'heure réelle du lancement.

## Exécuter entièrement depuis le dépôt

Depuis `dixon-coles/` :

```bash
python -m pip install -e '.[test]'
python -m dcscore.cli sync-openfootball --seasons 2021-22 2022-23 2023-24 2024-25 2025-26 2026-27
python -m dcscore.cli calibrate-xi \
  --competition of:ENG-PL \
  --start 2024-08-01 --end 2025-06-01 \
  --block-months 2 --min-games 500 --min-team 5 \
  --min-folds 4 --min-scored 160 \
  --candidates 0 0.0015 0.003 0.0065 0.01 0.016 0.025 0.04 \
  --holdout-start 2025-08-01 --holdout-end 2026-06-01 \
  --output dcscore/calibrations/eng-premier-league.json
```

Le workflow [`.github/workflows/dixon-coles-real-xi-calibration.yml`](../.github/workflows/dixon-coles-real-xi-calibration.yml) exécute ces commandes sur GitHub Actions, conserve les empreintes SHA-256 des fichiers sources dans ses logs et publie le rapport JSON validé dans le sous-module `dcscore/calibrations/`. Les tests automatisés ne nécessitent pas Internet et utilisent exclusivement des fixtures synthétiques clairement identifiées comme telles.

## Utilisation du coefficient optimisé

- **Lors d'une nouvelle prédiction** (`predict`, API `/api/predict`, interface), le moteur cherche d'abord une calibration locale dans SQLite ; s'il n'en existe pas, il utilise le rapport réel validé qui accompagne le programme. Le résultat précise `xi_source=optimized_real_data`, l'identifiant et la taille de validation, ainsi qu'un marqueur `stale_data` si l'historique a changé depuis la calibration.
- Sans calibration disponible, il utilise `0.0065` en affichant explicitement `xi_source=historical_default_not_optimized` : ce n'est **pas** présenté comme calibré.
- Un `--xi` explicite / `xi` fourni par API est une modification manuelle `xi_source=manual_override` et **n'est pas** présenté comme le ξ optimisé.
- La calibration reste **propre à la compétition**. Les résultats de Premier League ne fournissent pas automatiquement des paramètres fiables pour Ligue 1, Bundesliga, etc. Ces ligues exigent leurs propres données et validations.
- Le rapport daté identifie la source, la fenêtre temporelle, les seuils, l'empreinte SHA-256 des matchs réellement entrés, les résultats pour chaque candidat, les fenêtres d'évaluation et le test ultérieur.

## Limites honnêtes

- Une optimisation réussie signifie uniquement que le meilleur candidat de la **grille donnée** a minimisé la log loss sur la période de calibration choisie. Ce n'est pas une démonstration d'optimalité universelle ni une garantie de score exact gagnant.
- **Le score final de test** est plus informatif pour juger la généralisation ; il n'est pas utilisé pour réajuster ξ dans le présent protocole. Un coefficient optimal d'une saison peut se détériorer une autre saison.
- L'archive OpenFootball peut être incomplète ou en retard sur le championnat en cours ; les matchs sans score final sont exclus, jamais complétés automatiquement. L'affichage « données en retard » ne doit pas être confondu avec un échec mathématique.
- L'interface de calibration et l'import sont destinés à l'application **locale**. Les nouveaux endpoints d'administration refusent les clients non locaux sans `DCSCORE_ADMIN_TOKEN`. Cela ne sécurise pas automatiquement tous les endpoints hérités de la V1 : ne pas exposer l'application sur Internet sans contrôle d'accès global.
- Les cotes et la rentabilité des paris ne sont pas évaluées par cette optimisation : elle mesure des **probabilités de scores exacts**.
