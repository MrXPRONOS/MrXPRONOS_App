# MR XPRONOS — Audit Option B (8 octobre 2026)

## Les six améliorations

| # | Amélioration demandée | Livrables GitHub | Validation restante |
|---|---|---|---|
| 1 | Seuils spécifiques aux doubles chances, BTTS et Over/Under | Profils distincts dans BSD V2, majorations prudentes fondées sur les écarts de calibration du jeu de validation fin 2025 | Rentabilité non mesurable sans véritables cotes BSD historiques ; contrôle CI à confirmer |
| 2 | Couverture des équipes et des championnats | Minimum 4 matchs au calcul, lissage de ligue renforcé, et ligue qualité à 15 | Évaluer le Brier et la couverture sur les données historiques |
| 3 | Diagnostic complet des rejets | Chaque match possède cotes BSD, sélections examinées, probabilités et raisons de rejet. Rapport `bsd/rejections_report.json` disponible en artefact de workflow | Production du premier rapport CI à vérifier |
| 4 | Combinaison de 2 matchs cotés à 1,20+ | `bsd/bsd_v2_combos.py`, carte sombre `bsd/bsd_v2_combo_card.py`, deux matchs distincts, cote multipliée, mise de référence et suivi d'envoi Supabase | Vérifier un envoi réel Telegram ; notification GAIN du combiné non couverte |
| 5 | Minimum 4 matchs au calcul / 5 au contrôle qualité | `MIN_TEAM_GAMES = 4` et `V2QualityPolicy(min_form=5)` | Contrôle CI à confirmer ; modèles spécialisés peuvent encore demander davantage de matchs |
| 6 | Deux pronostics par match | Champ historique `prediction` maintenu et champ optionnel `predictions` (jusqu'à 2), familles de marchés distinctes, site et Telegram adaptés ; suivi de chaque résultat séparément | Vérifier un vrai match avec 2 marchés coté BSD ; pas de deuxième pronostic forcé |

## Couverture des tests

- `bsd/test_bsd_v2_combos.py` : cote de combiné, éligibilité horaire, matchs distincts, rendu PNG et résultats individuels gagnant/perdant.
- `bsd/test_bsd_v2_market_capacity.py` : calcul sur 4 matchs, contrôle qualité sur 5, audit des cotes et sérialisation de deux marchés.
- `.github/workflows/bsd-v2-ci.yml` : compilation Python, régression BSD, vérification syntaxique JavaScript.
- `.github/workflows/bsd-v2-production.yml` : contrôles du flux produit, export du rapport de rejets en artefact, retrait des fichiers privés avant GitHub Pages.
- `.github/workflows/bsd-v2-telegram-hourly.yml` : passage à 05, 20, 35 et 50 minutes après chaque heure ; combiné prévu autour de 45 à 65 minutes avant le premier coup d'envoi.

## Sécurité des données

Les données historiques ne contiennent pas nécessairement de cotes bookmaker vérifiées. Aucun rendement financier historique n'est reconstruit artificiellement. Une mise affichée à 500 000 FCFA est une référence théorique, pas un pari accepté, et le gain potentiel n'est pas un paiement.

Les combinés sont enregistrés dans Supabase avec un type de message distinct pour éviter les doublons ; la notification du résultat d'un combiné n'est pas encore intégrée. Les pronostics individuels, y compris les deux marchés éventuels d'un même match, conservent leur suivi indépendant.

**État : fichiers GitHub committés, mais exécution GitHub Actions et envoi réel Telegram non encore confirmés.**
