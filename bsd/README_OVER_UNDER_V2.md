# Audit des dix améliorations Over/Under — BSD V2

État des fichiers sur la branche `main` au 8 octobre 2026. Les nouvelles versions ne sont **pas encore validées sur un runner GitHub Actions** et aucun gain de précision n'est revendiqué.

| # | Amélioration | Implémentation | Vérification |
|---|---|---|---|
| 1 | Distribution spécialisée de total de buts | CODE — bsd_v2_over_under.py | Partielle : backtest à exécuter |
| 2 | Fréquences Over/Under par seuil 1,5/2,5/3,5/4,5 | CODE — probabilité de chaque seuil depuis distribution | Partielle : calibration réelle à vérifier |
| 3 | Forces attaque/défense selon adversaire | CODE — opponent_adjusted_mean, formule marque × encaisse | Partielle : validation empirique |
| 4 | Forme et domicile/extérieur | CODE — 15 rencontres pondérées, domicile/extérieur et lissage | Partielle : efficacité non vérifiée |
| 5 | Championnat et variance | CODE — moyenne, variabilité et taille d'échantillon | Partielle : efficacité non vérifiée |
| 6 | Poisson vs binomiale négative | CODE — modèle total_distribution + poids sur 2024 | Partielle : résultats hors échantillon |
| 7 | Calibration par ligne | CODE — V2Calibration, 2025, chaque clé OVER/UNDER | Partielle : métriques à vérifier |
| 8 | Cote BSD >=1,20 + seuil implicite | CODE — choisissez seulement marché coté, P >= max(50 %, 1/cote + 2,5 points) pour Over/Under | Partielle : API BSD en réel |
| 9 | Rejet des cas incertains | CODE — dispersion/forme/ligue, bloque seulement famille totals | Partielle : seuils à valider |
| 10 | Backtest autonome | CODE — bsd_v2_totals_backtest.py, workflow de validation, mêmes rencontres 2026 | Partielle : première exécution à lancer |

### Règles inchangées
- Le marché **UNDER_45** demeure exclu en production ; il peut rester dans l'audit statistique de référence, mais ne sortira pas sur le site.
- Une cote BSD réelle, issue du flux de marché correspondant, d'au moins **1,20** est impérative.
- Le moteur peut refuser tout le match ; BTTS et 1X2 restent des alternatives, non privilégiées artificiellement.
- L'archive de scores n'a pas de cotes passées vérifiées : pas de ROI historique inféré.
- Le nouveau modèle est ajusté et calibré avant les rencontres de test de 2026.

### Fichiers
- `bsd/bsd_v2_over_under.py` : modèle total de buts, contraintes historiques, forme, contexte, volatilité.
- `bsd/bsd_v2_core.py` : choix entre marchés, filtre de cote/valeur et rejets.
- `bsd/bsd_v2_policies.py` : calibration 2025, qualité 2025.
- `bsd/bsd_v2_publish.py`, `bsd/bsd_v2_shadow.py`, `bsd/bsd_v2_evaluate.py` : intégration.
- `bsd/bsd_v2_totals_backtest.py`, `bsd/test_bsd_v2_over_under.py` : contrôle.
- `.github/workflows/bsd-v2-validation.yml` : crée `bsd/v2_totals_backtest.json` comme artefact.

### Conditions de validation finale
1. Démarrer `BSD V2 - Validation experimentale` avec max_test=1000.
2. Vérifier la réussite de tous les tests, puis examiner `v2_totals_backtest.json` : Brier par marché, écart de calibration, nombre d'échantillons et résultats par ligue.
3. Comparer à la baseline sur les **mêmes rencontres**. Si le modèle spécialisé n'améliore pas le score retenu lors de la validation 2024, son poids est nul.
4. Exécuter la génération quotidienne sur un créneau contrôlé, vérifier les cotes BSD, les compteurs de rejet et le JSON final. Ne jamais conclure à une rentabilité sans disposer des cotes historiques réelles.


## Audit complémentaire du 8 octobre 2026 (corrections de complétude)
Les éléments ci-dessous ont été implémentés dans le code et intégrés aux chemins production, shadow et backtest. Ils ne constituent pas la preuve que le dernier workflow GitHub Actions a réussi.

| # | Amélioration | État code | État de la vérification |
|---|---|---|---|
| 1 | Distribution dédiée de total de buts | Complète dans le code | Tests CI réels en attente |
| 2 | Fréquences par ligne 1,5/2,5/3,5/4,5, séries 5/10/15, domicile/extérieur, ligue | Complète dans le code | Tests CI réels en attente |
| 3 | Force offensive et défensive de chaque adversaire | Complète dans le code | Backtest de gain de précision en attente |
| 4 | Moyennes pondérées temporellement et séparation domicile/extérieur | Complète dans le code | Backtest en attente |
| 5 | Moyenne/variance des ligues et lissage | Complète dans le code | Backtest par championnat en attente |
| 6 | Modèle Poisson ou binomiale négative, mélange hors échantillon 2024 | Complète dans le code | Choix effectif du poids à vérifier sur historique BSD |
| 7 | Calibration propre à chaque Over/Under sur début 2025, contrôle qualité fin 2025 | Complète dans le code | Rapport CI et erreurs de calibration en attente |
| 8 | Cotes >= 1,20 et marge de probabilité conservatrice vs seuil d'équilibre | Complète dans le code | Vérification BSD réel en attente |
| 9 | Détection de volatilité, faible historique et désaccord modèles, sans pénaliser l'ancien modèle lorsque le nouveau est désactivé | Complète dans le code | Sensibilité des seuils en attente |
| 10 | Backtest indépendant comparant référence calibrée et spécialisée calibrée sur les mêmes matchs de 2026 | Complète dans le code | Workflow GitHub à exécuter et comparer |

### Tests ajoutés
`bsd/test_bsd_v2_over_under.py` vérifie la monotonie des probabilités des lignes, la cohérence des Over/Under complémentaires, l'absence de fuite future, le seuil de cotes, la sécurité de sélection par probabilité prudente, la variance, le comportement des modèles sans entraînement et la conservation des autres marchés.

### Ce qui reste réellement à valider
- Exécuter et inspecter toutes les assertions GitHub Actions. Les modifications GitHub n'exécutent pas à elles seules des tests.
- Exécuter le rapport `bsd/v2_totals_backtest.json` avec historique BSD restauré, comparer `baseline_calibrated` à `specialized_calibrated`. Si le nouveau modèle ne s'améliore pas, il faut laisser le blend à 0.
- Vérifier la génération quotidienne et l'application du filtre sur les vrais prix BSD. Ne jamais simuler des cotes historiques manquantes.
