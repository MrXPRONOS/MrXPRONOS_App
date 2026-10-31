# 2026 HOLDOUT : coefficients figés après 2025 — protocole préenregistré

**Date de gel : 31 octobre 2026, AVANT démarrage.** Recherche isolée sur la branche `research/single-ml-v2-20261024`, sans modification `main`, Telegram, du site ou des bases.

## Réalité des sources et intervalle

L'archive authentifiée contient **91 331 matchs en 2024**, **87 451 en 2025**, **76 934 matchs de 2026 au 24 octobre** (max vérifié `CUTOFF=2026-10-24`). L'année civile 2026 n'est pas achevée et l'archive n'a pas été étendue. On étudie **2026-01-01..2026-10-24**, 297 jours calendaires, via 10 segments mensuels (le dernier est partiel, 1–24 oct.). Les jours sans minimum 20 matchs exploitables sont signalés et rejetés, non omis silencieusement. Les matches 2026 réellement admis par le loader et les huit modèles peuvent être moins nombreux que les 76 934 archives.

## Séparation formation/validation

Les **huit modèles existants inchangés** sont entraînés **une fois** à la première date du segment de validation sur des features pré-match, labels et paramètres calculés à partir de **2024-01-01..2025-12-31, inclusivement**. Le moteur doit garantir, pour chaque tâche de 2026 et TOUS les algorithmes :
- Les dates de tous les exemples passés à `train_ml`, `fit_hist_v3`, `train_direct_score`, `fit_direct_v3`, `fit_pair`, `estimate_dc_rho` et `estimate_shared` sont **strictement antérieures au 1er janvier 2026**.
- **Aucune actualisation des coefficients / réentraînement / sélection d'hyperparamètres / calibration des probabilités** n'utilise des étiquettes de 2026. Pour les calibrateurs V2/V3 reposant sur des prédictions historiques OOS indisponibles avant 2026, utiliser les paramètres par défaut fixés AVANT l'étude : poids hybride de 35 %, poids prior direct V3 de 20 %, multiplicateur P(1–1) de 1. Le modèle peut produire des historiques de diagnostic 2026 mais **ne peut jamais les employer pour entraîner ou calibrer**.
- **Seule la forme d'équipe pré-match (moyennes dernières rencontres, forces adversaires) peut utiliser des matchs déjà terminés en 2026**, dans l'ordre chronologique et exclusivement les **jours précédents**. C'est une caractéristique disponible au moment de prévoir le match et **non** un réentraînement des coefficients. La politique doit être transparente.
- L'indicateur d'antériorité du modèle (`model_fit_latest_day`) doit être **2025-12-31 ou avant** pour toute prévision des huit modèles ; `history_latest_day` peut être le jour 2026 précédent pour les stats de forme. Distinguer clairement les deux.

Les mêmes hyperparamètres et architectures V2/V3 restent figés comme dans les précédentes études. Pas de recherche de seuils, d'optimisation du Top-K ni d'entraînement sur les résultats du holdout.

## Protocole et métriques

Pour chaque journée du 1er janvier au 24 octobre 2026 (date UTC), classement indépendant des **huit** modèles en Top 5, 10, 20, par probabilité de score modal décroissante, sans utiliser le score réalisé ; même univers d'au moins 20 rencontres par modèle et par jour, même score réel par match. Publier : nombre de scores exacts, taux individuel, jours ≥1, ≥2, ≥3 corrects, pourcentage 1–1, log-loss, taux et score moyen par mois et au total. Calculer les différences par paires HistGB V3-V2, Hybride V3-V2, Direct V3-V2, IC bootstrap groupés par journée dans chaque mois, sensibilité par blocs de 7 jours, **4 000 itérations**. Évaluer aussi la stabilité mensuelle.

Les segments : janvier, février, mars, avril, mai, juin, juillet, août, septembre (mois complets), **octobre (1–24)**. Toutes les journées éligibles doivent apparaître ; si l'un des 10 segments est incomplet, aucun résultat global ne peut être appelé « validé ».

Aucune cote de score exact pré-match certifiée disponible → **pas de rendement (ROI)**. Ces résultats restent un rejeu historique avec sélection des rencontres connaissant leur existence a posteriori ; ils ne sont pas un archivage de pronostics réellement publiés avant coup d'envoi.

## Preuve technique requise

Tests synthétiques montrant que des labels de 2026 peuvent être modifiés sans affecter les coefficients entraînés, leur date d'antériorité, ni les grilles prévues pour les matchs antérieurs ; vérification des 10 fenêtres et des univers quotidiens identiques, refus des dates de 2026 dans l'apprentissage. Exécution isolée sur GitHub Actions, secrets seulement côté runner, données sources jamais publiées, uniquement agrégats quotidiens.
