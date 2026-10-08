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


## Modification des règles des combinés — 8 octobre 2026

**Important : cette section remplace les anciennes descriptions des limites de cotes.**

- Un combiné contient exactement **deux matchs différents**.
- **Chaque sélection du combiné doit avoir une cote BSD authentifiée 1,01 <= cote < 1,50**.
- Les cotes **1,50 ou davantage** ne peuvent jamais constituer une jambe de combiné, même avec un match à faible cote.
- La restriction de 1,20 ne s'applique plus aux combinés. Les cotes **1,01 à 1,19** sont conservées uniquement si la probabilité prudente du modèle est d'au moins 90 % ; ce seuil reste un filtre prudent, non une garantie.
- Les pronostics simples demeurent soumis à leur filtre individuel **>= 1,20** et à leur marge de sélection ; les choix à moins de 1,20 ne sont **pas envoyés seuls sur Telegram**.
- Pour chaque match, le générateur peut enregistrer un marché séparé `combo_prediction` strictement sous 1,50, même si sa sélection individuelle principale est à 1,50 ou plus.
- Le moteur de combinés examine `combo_prediction`, `prediction` et `predictions`, retient au maximum une sélection pour un même match et associe uniquement deux événements distincts.
- Sur le site, **chaque sélection individuelle est présentée dans sa propre fiche** (y compris dans l'historique) ; aucune section « Pronostic 2 » n'est intégrée à la fiche du premier.
- Les matchs `combo_only` (sélection principale < 1,20) sont conservés dans `data.json` pour Telegram combiné, mais ne sont pas affichés comme pronostics individuels sur le site.
- Sur Telegram, les deux sélections individuelles sont suivies et envoyées séparément lorsque la cote de chacune est >= 1,20. Les combinés ont leur propre envoi et leur propre identifiant de dédoublonnage.
- **Under 4,5 reste entièrement interdit.**

### Tests de cette modification

`bsd/test_bsd_v2_combos.py` vérifie les limites (1,01 inclus, 1,50 exclu), la non-association d'un même match et la possibilité d'un `combo_prediction` à faible cote lorsque la sélection principale est à plus de 1,50.

`bsd/test_bsd_v2_market_capacity.py` vérifie le choix des marchés à 1,01–1,19 seulement pour l'usage combiné, à condition d'avoir une probabilité prudente élevée.

**Validation à terminer :** nouvelle génération de `data.json`, exécution des tests GitHub Actions et envoi réel du premier combiné correspondant aux règles actualisées.
