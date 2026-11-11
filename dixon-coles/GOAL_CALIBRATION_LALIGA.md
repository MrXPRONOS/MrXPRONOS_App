# Calibration des buts — Liga / Dixon-Coles

## Diagnostic reproductible

La référence est le backtest Popularité V2, octobre 2026, **25 matchs de Liga**, matchs présélectionnés avant l'évaluation. La cohorte est figée dans `dcscore/diagnose_laliga_oct2026.py` pour interdire le changement rétrospectif des matches « faciles ».

**Octobre (25 matchs)**

| Mesure | Modèle initial | Modèle calibré |
|---|---:|---:|
| Scores exacts Top 1 | 0 | 0 |
| Scores dans le Top 5 | 14 | 14 |
| Résultats 1N2 corrects | 17 | 16 |
| Somme des buts attendus (λ+μ) | 71,97 | 75,74 |
| Somme des buts réels | 83 | 83 |
| NLL moyen score exact (moins = mieux) | 3,0433 | 3,0204 |
| NLL moyen 1N2 | 0,8772 | 0,8782 |
| Somme des probabilités des scores 1-1 | 2,57 | 2,46 |
| Scores réels 1-1 | 4 | 4 |

La somme des *scores modaux* est 49 buts et n'est **pas** l'espérance de buts du modèle : l'espérance avant calibration est d'environ 71,97 buts. Le modèle ne surestime pas systématiquement le 1-1 dans cette cohorte : il en attend 2,57 et il y en a 4.

**Vérification supplémentaire, 1–10 novembre (15 rencontres terminées, toutes les affiches disponibles, pas seulement le Top10)**

| Mesure | Initial | Calibré |
|---|---:|---:|
| Scores exacts Top 1 | 1 | 1 |
| Résultats 1N2 corrects | 9 | 9 |
| Somme des buts attendus | 41,95 | 42,88 |
| Somme des buts réels | 30 | 30 |
| NLL moyen score exact | **2,5671** | 2,5791 |
| NLL moyen 1N2 | 0,9300 | **0,9279** |

La variation octobre/novembre contredit l'idée de relever systématiquement les buts ou de corriger le score 1-1 à la main.

## Méthode

`goal_calibration.py` procède *pour chaque date de prédiction* :

1. Coupe les historiques à **20 h UTC la veille** des matchs de la journée cible.
2. Ajuste un modèle ancien sur les résultats précédant le cutoff de 240 jours.
3. Estime un multiplicateur commun domicile/extérieur entre **0,85 et 1,20** sur les matchs des jours -240 à -60 (fenêtre recouvrant l'intersaison).
4. Valide sur un ensemble plus récent et disjoint, jours -60 jusqu'au cutoff.
5. N'accepte l'ajustement que s'il améliore le NLL des scores exacts, n'aggrave pas excessivement la MAE des buts et n'aggrave pas excessivement le NLL 1N2.
6. Sinon, ou lorsque les historiques/équipes/contraintes sont insuffisants, revient au modèle d'origine (**multiplicateur 1,0**).

**Décision :** au vu de novembre, l'ajustement ne présente **pas encore de preuve stable d'amélioration des scores exacts** ; il reste explicitement **désactivé par défaut** pour les vidéos automatiques. Aucune hausse systématique des buts, ni aucun traitement arbitraire du 1-1, n'est autorisé.

En cas de test manuel documenté, seule l'option `python -m dcscore.daily --source espn --calibrate-laliga-goals` active les ajustements historiquement validés sur la Liga, jamais les autres championnats. La production nocturne ne transmet pas ce drapeau.

## Limites

- Reconstructions historiques ESPN : ce ne sont pas des copies immuables des pronostics diffusés avant les matchs.
- La seule réussite au score exact peut être très variable, et un mois n'est pas suffisant pour établir un avantage.
- Un meilleur NLL n'implique pas automatiquement davantage de scores exacts Top 1.
- Il n'existe aucune cote des opérateurs, donc aucun calcul légitime de ROI.
- Prévoir un contrôle hors-échantillon mensuel et réexaminer la mise en service lorsque plusieurs périodes confirment un gain robuste.

Rapports produits par la GitHub Action `laliga-goals-calibration-audit.yml` : JSON et CSV complets d'octobre et le rapport de novembre.
