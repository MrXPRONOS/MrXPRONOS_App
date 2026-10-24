# Mr XPRONOS — Protocole indépendant n°10 (scores exacts uniques)

## Deux niveaux de preuve distincts

1. **Backtest chronologique rétrospectif** : `single_ml_v2_validation.py` vérifie les séparations de dates, la cohérence de la probabilité du score réalisé, les paires de matchs et les métriques. Même lorsque les calculs n'utilisent pas le futur, des prédictions calculées après le match ne sont **PAS** des pronostics réellement archivés avant le coup d'envoi.
2. **Test réellement prospectif (« blind forward »)** : `single_ml_v2_forward.py` récupère les futurs matchs vérifiés football sportId=1 et prépare les modèles **uniquement à partir de journées antérieures certifiées et déchiffrées en mémoire temporaire**. Les grilles 11×11 sont chiffrées avec AES-256-GCM et inscrites dans GitHub sous `research/encrypted_football/forward/issued/YYYY/MM/DD/<digest>.enc` avant le match. Un deuxième passage récupère les résultats certifiés, vérifie leur identité et crée un autre fichier chiffré `forward/settled/XX/<digest>.enc`, sans réécrire le pronostic initial.

## Conditions strictes d'un pronostic réellement validé

- La rencontre doit être certifiée **football uniquement**, identifiée par l'API, non commencée, et prévue suffisamment loin.
- Le pronostic doit être créé **au moins 45 minutes avant le coup d'envoi**, puis son premier commit Git doit être antérieur d'au moins 45 minutes.
- Sur GitHub Actions, un autre contrôle interroge l'**API GitHub** et vérifie qu'une exécution authentique du workflow dédié était déjà terminée avec succès au moins 45 minutes avant le coup d'envoi. Un simple horodatage ajouté par un script ou un commit modifiable ne suffit pas.
- Une valeur manquante, un résultat non finalisé, un report, une identité contradictoire, un score suspect, un commit trop récent ou une clé de chiffrement manquante entraînent le rejet ou le statut « en attente ».
- Les prévisions émises localement sans preuve de l'exécution GitHub sont marquées **LOCAL_GIT_ONLY_UNVERIFIED**, même si les calculs numériques fonctionnent.
- Toute récupération xG est strictement « telle que connue à la date du pronostic » : les xG récupérés plusieurs jours plus tard ne sont jamais antidatés.

## Comparaisons

- Référence : Machine Learning historique `machine_learning`.
- Alternatives : `machine_learning_direct`, `machine_learning_lightgbm` et `machine_learning_catboost`.
- Comparaison uniquement sur **les mêmes matchs et dates**, rapportant aussi le **nombre de pronostics impossibles**.
- Scores exacts trouvés, couverture, taux de réussite, Top 3, log-loss, Brier simplifié, calibration et fréquence artificielle de 1–1; Wilson à 95 % et bootstrap par journée. Les tests d'incertitude ne prouvent pas à eux seuls une capacité prédictive future.
- **Aucun ROI n'est estimé en l'absence de vraies cotes du score exact prises avant le match.**
- **Date de début prospective pré-enregistrée : 2026-10-25**. Les archives antérieures peuvent servir à entraîner, jamais comme preuves de pronostics archivés.

## Activation contrôlée — pas de dépenses API en boucle sans consentement

Les workflows isolés sont installés dans `.github/workflows/research-single-ml-v2.yml` (tests hors ligne) et `.github/workflows/research-ml-v2-forward.yml` (recherche uniquement). Le workflow prospectif est enregistré sur `main` pour être visible dans GitHub Actions, mais les déclenchements planifiés restent **désactivés** tant que la variable de dépôt **`ML_V2_FORWARD_ENABLED`** n'est pas réglée sur `true`. Il peut être lancé manuellement via GitHub Actions sans cette variable.

La collecte nécessite les secrets `ML_V2_HISTORY_KEY_B64` (32 octets aléatoires encodés en Base64, gardés privés) et une clé `SPORTDATA_API_KEY` ou `SPORTDATA_API_KEY_1..5`, ainsi qu'une **archive football chiffrée certifiée couvrant la période requise**. L'entraînement refuse de produire une simulation prétendue « prospective » tant que ce prérequis n'est pas satisfait.

Les tâches planifiées exécutent au plus deux passages quotidiens (00:20 et 12:20 UTC) **uniquement après activation explicite**. Les étapes sur le Git historique ne modifient aucune API/route/page/Telegram de production. Les seuls fichiers ajoutés sont les `.enc` chiffrés. Les rapports agrégés, et non les matchs déchiffrés, sont téléchargeables sous forme d'artifacts GitHub temporaires.

## Limites et transparence

Un pipeline implémenté n'est pas un ensemble de résultats acquis : aucune preuve prospective ne peut être produite avant qu'une rencontre réelle ait été prédite en amont puis terminée. Il faut ensuite auditer le nombre d'observations et leur incertitude statistique. Les protections GitHub rendent la fraude rétrospective plus difficile, mais elles ne représentent pas une notarisation externe indépendante absolue. Il faut conserver le contrôle des accès au dépôt et des secrets, et éviter les réécritures forcées de l'historique Git.
