# MR XPRONOS — protocole gelé pour choisir un seul modèle, 2026

Créé le 2 novembre 2026, AVANT le nouveau rejeu annuel. Étude de recherche seulement ; aucune activation du site / Telegram.

## Données certifiées et disponibilité
Source : archives chiffrées déjà contrôlées par `single_ml_v2_multisource.py`, `CUTOFF=2026-10-24`, 2026 : 76 934 observations de source (toutes ne sont pas admissibles au modèle). **Octobre 25–31, novembre et décembre ne sont pas disponibles.** Ne jamais les inventer.

- **Période principale : neuf mois complets janvier–septembre 2026 (273 jours)** : janvier 31, février 28, mars 31, avril 30, mai 31, juin 30, juillet 31, août 31, septembre 30.
- **Période séparée : octobre 1–24, 2026 (24 jours)**, période explicitement **partielle**. October ne compte pas dans la note principale mais doit faire l'objet d'une analyse de sensibilité.
- Au total 297 jours possibles et 10 périodes. 2026 ne peut PAS être décrit comme une année complète.

## Huit modèles inchangés
HistGB V2, Hybride V2, LightGBM V2, CatBoost V2, Direct V2 ; HistGB V3, Hybride V3 et Direct V3. Identifiants et paramètres conservés ; *aucun recalibrage sur les résultats évalués de cette étude*. Historique strict : uniquement résultats de journées UTC plus anciennes ; ensemble de rencontres identique par modèle et journée.

## Trois tailles de listes quotidiennes
**Top 5, Top 10, Top 20** ; chaque modèle classe chaque jour par la probabilité de son score exact prédit le plus élevé, ex aequo par ID. Le score réellement observé est utilisé pour évaluer, jamais pour choisir. Exactement K matchs/jour; si un modèle manque un match, pas de rapprochement silencieux : faire échouer la période.

## Choix d'un modèle AVANT de voir les résultats
Objectif utilisateur : un modèle fiable pour les pronostics de scores exacts, particulièrement pour **au moins un bon score par jour**.

- **Critère principal** : sur janvier–septembre 2026, **Top 10, nombre de journées avec ≥1 score exact correct**, puis **taux de scores exacts au Top 10** si ex-aequo.
- **Contrôles secondaires** : Top 5 et Top 20, journées ≥2 et ≥3, scores exacts totaux, log-loss, stabilité sur chacun des neuf mois, intervalles bootstrap appariés 95 % par journée et blocs de sept jours. Un modèle ne doit pas être considéré définitivement supérieur sur des différences faibles ou instables. Éviter de modifier le critère après résultats.
- **Déploiement** : aucune activation automatique. La décision finale appartient à l'utilisateur après lecture du rapport et validation prospective.
- Les mois 2026 ont pour certains déjà été évalués dans les comparaisons V2/V3 précédentes. **Ce n'est pas un test indépendant** : l'analyse annuelle est un choix descriptif entre modèles existants et non une démonstration prospective de supériorité.

## Rapports
Pour chaque période : décompte quotidien des huit modèles, courbes Top 5/10/20 et log-loss, aucune donnée source brute publiée. L'agrégateur doit publier **deux totaux distincts** : 273 jours complets (principal) et 297 jours incluant octobre incomplet (diagnostic). Fournir les résultats et les intervalles ; ne jamais attribuer de ROI sans véritables cotes score exact pré-match vérifiées.

La configuration de la comparaison est gelée dans `research/ml_v3_topk_full_2026.py`; le workflow lance les dix périodes uniquement sur la branche de recherche. Pas de `main`, Supabase, Telegram ni production.
