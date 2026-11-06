# BSD V3 — moteur football expérimental indépendant

## État

**Développement implémenté sur la branche `feat/bsd-v3-shadow-engine` / PR #303.**
BSD V2 reste le seul moteur publié. BSD V3 n'écrit jamais dans `data.json`,
`bsd/publication_ledger.json`, GitHub Pages ni Telegram.

**Utilisation gratuite uniquement :** historique BSD chiffré existant, clé BSD
existante, modules internes, et éventuellement tableau OddsLink public.
La souscription à une API de bookmaker BSD n'est pas utilisée.
La disponibilité des bookmakers publics et des quotas n'est pas garantie.

## Architecture en service (code)

| Module | Fonction |
|---|---|
| `legacy.py` | Accès en lecture seule au moteur temporel BSD V2 |
| `quality.py` | Validation des données/identifiants, suppression des doublons incohérents, données futures interdites |
| `policy.py` | Seuil public 79 % et historique Pro/VIP, protections de confiance et exclusions |
| `goal_strength.py` | Nouveau modèle Elo → buts attendus, entraînement Jan–Août 2025, garde Sep–Déc 2025 |
| `ensemble.py` | Modèles spécialisés 1X2/Over/BTTS entraînés en 2024, combinaison cohérente validée en 2025 |
| `calibration.py` | Calibration des probabilités par projection de la distribution jointe et validation 2025 |
| `probabilities.py` | Matrice des scores et probabilités compatibles 1X2/BTTS/Over/Under/DC |
| `guardrails.py` | Préservation explicite des protections BTTS/H2H et désaccords de modèles |
| `free_odds.py` | Cotes multi-marchés avec BSD consensus gratuit + tableau public optionnel |
| `quotes.py` | Validation du marché exact, du bookmaker, des horaires et de la provenance |
| `selection.py` | Circuit Pro/VIP shadow, Value Shadow, deux familles distinctes et corrélation |
| `registry.py` | Prévisions figées, empreintes SHA256, journal prospectif chaîné |
| `settlement.py` | Enregistrement des résultats sans remplacer la prévision |
| `monitor.py` | Brier/log-loss, calibration par marché, coupe-circuit sur résultats prospectifs |
| `comparison.py` | Comparaison appariée des modèles V2/V3 sur mêmes matchs avant cotes |
| `evaluation.py` | Évaluation rétrospective V3 et baseline sans ROI artificiel |
| `engine.py` | Orchestration de V3, contrôle qualité, diagnostics et choix expérimentaux |
| `cli.py` | Exécution `shadow`, `evaluate`, `compare`, `settle` ; écriture V3 exclusivement |
| `test_*.py` | Tests hors réseau des règles et des invariants |

## Exécution

Depuis la racine du dépôt, après installation de `requests` et `cryptography` :

1. Sur un environnement privé disposant de `BSD_HISTORY_KEY`, exécuter
   `python bsd/bsd_archive.py restore` pour obtenir l'historique chiffré.
2. Pour tester la syntaxe et le fonctionnement hors réseau :
   `python -m unittest discover -s bsd_v3 -p 'test_*.py' -v`.
3. Prévision expérimentale gratuite :
   `python -m bsd_v3.cli --mode shadow --days 1 --max-odds-events 15 --output bsd_v3/artifacts/shadow.json`.
4. Pour activer le tableau public **gratuit** de cotes, ajouter
   `--free-public-board`. L'indisponibilité de ce tableau est tolérée.
5. Pour entraîner et valider les modèles spécialisés, ajouter `--challengers`.
   Les modèles sans gain validé restent inactifs.
6. Backtest rétrospectif :
   `python -m bsd_v3.cli --mode evaluate --output bsd_v3/artifacts/evaluation.json`.
7. Comparaison V2 contre V3 :
   `python -m bsd_v3.cli --mode compare --max-test-matches 700 --output bsd_v3/artifacts/comparison.json`.
8. Règlement prospectif des prévisions précédemment enregistrées :
   `python -m bsd_v3.cli --mode settle --output bsd_v3/artifacts/settlement.json`.
9. Effacer les fichiers temporaires historiques en clair :
   `rm -f bsd/all_matches_bsd.json bsd/backfill_state.json`.

Le workflow manuel `.github/workflows/bsd-v3-shadow.yml` fournit les quatre modes
**une fois le fichier présent sur la branche par défaut GitHub**. Il possède
uniquement `contents: read` et `actions: read`, et ne peut ni pousser dans Git
ni publier des messages Telegram.

Les artéfacts GitHub Actions peuvent reprendre le dernier registre. GitHub
retient ici les fichiers **90 jours** ; le suivi peut se perdre après une
interruption plus longue, sauf archivage externe. Les fichiers historiques
décryptés ne sont jamais inclus dans les artéfacts.

## Risque et fiabilité

- L'éligibilité à 79 % de probabilité estimée **n'est pas un taux de réussite garanti**.
- Le consensus BSD est une cote observée indicative et non une mise exécutable.
- Le tableau public peut contenir des offres de bookmakers nommés, mais la
  disponibilité au Togo, la limite de mise et l'acceptation ne sont pas vérifiées.
- Le ROI du moniteur est un **rendement théorique sur cotes historiques observées**,
  pas de véritables paris enregistrés, ni un rendement net.
- L'observation historique 2026 a déjà influencé les conceptions précédentes ;
  elle n'est pas un échantillon totalement inédit.
- Les règles V2 pour BTTS sont enregistrées par marché et empêchent une
  recommandation expérimentale publique en cas d'échec, tout en permettant
  de mesurer les marchés ignorés dans Value Shadow.
- Le choix de nouveaux modèles et la qualification des cotes sont falsifiables ;
  un modèle qui échoue au test chronologique reste désactivé.
- **Aucun mécanisme ne publie V3**. Fusionner le code n'est pas équivalent à
  activer V3 sur le site ou Telegram.

## Statut de réception

La présence du code et les tests unitaires ne prouvent pas une meilleure
prédiction, la validité de la couverture de données réelles ni le retour sur
investissement. Voir `IMPLEMENTATION_STATUS.md` pour les items achevés en code
et les éléments encore bloqués par la validation sur matchs prospectifs.
