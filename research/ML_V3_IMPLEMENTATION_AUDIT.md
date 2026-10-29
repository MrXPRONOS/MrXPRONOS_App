# Mr XPRONOS — ML V3 : audit d'implémentation avant nouveau backtest

**État : code expérimental sur PR #227**, branche `research/single-ml-v2-20261024`. Le périmètre concerné est **HistGradientBoosting, Hybride Dixon-Coles et classification directe**.

**IMPORTANT : implémentation du code ≠ amélioration statistique démontrée.** Ici, nous ne réévaluons AUCUN score exact historique. Le prochain backtest est intentionnellement réservé à une étape distincte. Tous les tests d'intégration utilisent des matchs **synthétiques** sans donnée de production.

## 1 — HistGradientBoosting V3

| ID | Amélioration | État du code | Vérification |
|---|---|---|---|
| H1 | Donner plus de poids aux observations récentes, demi-vie 180 jours | **Complète** | `MLConfig(half_life_days=180)` et `fit_histgb(...,asof=jour)`, validation chronologique, entraînement effectif sur données synthétiques |
| H2 | Maintenir l'utilisation maximale de 65 000 exemples historiques | **Complète (capacité), pas un changement par rapport à V2** | `HIST_CONFIG.max_rows=65000` ; ne pas présenter comme une capacité supérieure à V2 |
| H3 | Réduire la confiance ML si la forme récente domicile/extérieur est lacunaire | **Complète** | Mélange pré-match avec la grille Poisson, poids maximum 20 %, contrôles de normalisation |
| H4 | Réajuster P(1–1) uniquement à partir d'anciennes prédictions évaluées | **Complète** | Minimum 180 prévisions sur 14 jours ; lissage, facteur entre 0,75 et 1,25 ; prédiction du jour exclue ; tests fuite temporelle |
| H5 | Augmenter de façon démontrée le nombre de succès Top 5/10/20 | **Non vérifiée : prochain backtest** | Pas de gain présumé |

## 2 — Hybride Dixon-Coles V3

| ID | Amélioration | État du code | Vérification |
|---|---|---|---|
| Y1 | Remplacer la composante HistGB V2 par la nouvelle distribution HistGB V3, sans modifier DC indépendant | **Complète** | Trois sorties V3 branchées dans `single_ml_v2.backtest(v3_models=True)` |
| Y2 | Apprendre un poids DC à partir des seules prévisions V3 des journées passées | **Complète** | Historique V3 séparé ; `calibrate(...,base_weight=.35)`, au moins 80 observations et 12 journées, fallback fixé si insuffisant |
| Y3 | Empêcher des variations brusques du poids entre réentraînements | **Complète** | Variation maximale ±0,12 par calibrage, poids absolu entre 0,10 et 0,65 |
| Y4 | Réduire l'influence de DC quand les distributions du ML et du modèle statistique divergent beaucoup | **Complète** | Ajustement par distance de variation totale, grille renormalisée, tests synthétiques |
| Y5 | Gain historique et prospectif | **Non vérifié : prochain backtest puis prospective** | Aucune annonce de performance |

## 3 — Classification directe V3

| ID | Amélioration | État du code | Vérification |
|---|---|---|---|
| D1 | Étendre la fenêtre d'apprentissage de 20 000 à 65 000 matchs | **Complète dans le code** | `DIRECT_CONFIG.max_rows=65000` ; entraînement synthétique avec 850 matchs, pas encore benchmark à 65 000 |
| D2 | Pondérer modérément les classes de scores fréquents / rares | **Complète** | Rééquilibrage `class_weight_power=0.25`, poids bornés 0,6–2,0, normalisation ; V2 par défaut = aucune pondération |
| D3 | Augmenter l'effort d'entraînement et la régularisation de manière contrôlée | **Complète** | `max_iter=90`, `max_leaf_nodes=16`, `l2_regularization=15` versus V2 : 60, 12 et 12 |
| D4 | Adapter le mélange avec la grille Poisson sur des prévisions réellement anciennes, sans fuite du jour | **Complète** | Classifieur V3 brut puis calibrateur préquentiel du poids du prior (défaut 0,20, poids calibré borné 0,05–0,65) |
| D5 | Garder une distribution complète, y compris les scores rares au-delà de 5 buts | **Complète par héritage V2** | 36 catégories scores 0..5 + classe rare, distribution finale 11×11, validation de somme des probabilités |
| D6 | Améliorer objectivement la régularité des jours ≥1 ou ≥2 bons scores | **Non vérifié : prochain backtest** | Nécessite vraie sélection Top K hors échantillon |

## 4 — Tests d'intégration et isolation

- Implémentation : `research/single_ml_v3.py` avec trois identifiants expérimentaux indépendants `machine_learning_v3_histgb`, `machine_learning_v3_hybrid`, `machine_learning_v3_direct`.
- **Interrupteur désactivé par défaut :** `backtest(...,v3_models=False)`, CLI `--experimental-v3` sur le runner et le pont d'archives chiffrées.
- V2 : paramètres par défaut préservés, aucun changement de prévision attendu si V3 est désactivé. Les appels V2 restent disponibles en parallèle lorsque V3 est activé.
- Chronologie : apprentissage à partir des journées UTC terminées précédentes ; les nouvelles prévisions du jour entrent dans les historiques de calibration uniquement après la résolution des matchs ; aucun résultat de la journée n'entre dans les grilles de cette même journée.
- CI : `.github/workflows/research-ml-v3-implementation-tests.yml` compile les modules ; exécute les tests V3 incluant l'entraînement réel sur jeux synthétiques et l'intégration du moteur ; exécute les tests de non-régression V2 ; atteste du caractère *opt-in*.
- **Aucun entraînement/backtest historique V3 en conditions réelles réalisé à cette étape.** Cela est intentionnel.

## 5 — Restant partiel / hors périmètre de cette étape

1. **Comparateur Top 5/10/20 V3 — TERMINÉ** : `research/ml_v3_topk_compare.py` compare les **cinq V2 + trois V3**, refuse les journées manquantes, impose les **mêmes fixtures et vrais scores** pour huit modèles, sélectionne séparément les Top 5/10/20 par confiance *avant* lecture des résultats, vérifie les sélections emboîtées, compte les journées avec ≥1/2/3 bons pronostics et calcule des intervalles bootstrap appariés par journée / sensibilité 7 jours. Quatre mois préfixés (mai et août 2025, mai et août 2026), génération des seuls agrégats anonymisés. **Tests passés** ; le vrai backtest n'a pas été lancé.
2. **Optimisation des hyperparamètres et des poids** : valeurs V3 fixées en amont, mais non optimisées par sélection emboîtée sur une fenêtre distincte. **Statut : non réalisé volontairement**, pour limiter le risque d'overfitting pré-backtest.
3. **Capacité d'entraînement sur 65 000 exemples — TERMINÉE SUR SYNTHÉTIQUE, charge réelle à confirmer** : les deux vraies configurations V3 ont été entraînées sur 65 000 rencontres **synthétiques**, avec les **160 caractéristiques** et une classification directe à **37 classes**. HistGB V3 71,20 s, classification directe V3 108,36 s, pic RSS 551,42 Mio (runner GitHub Linux), validations des grilles 11×11. Le test est reproduisible via `research/ml_v3_capacity_65000.py` et `.github/workflows/research-ml-v3-completion-audit.yml`. Il démontre la capacité technique à cette charge sur ces données ; les durées réelles par mois, le coût d'un rejeu historique complet et la performance hors échantillon restent non vérifiés tant que le backtest séparé n'a pas été exécuté.
4. **Ajout d'xG historiques authentifiés, de cotes score exact et de nouvelles sources identitaires** : **non réalisé**, car non présents dans les archives certifiées actuellement disponibles.
5. **Preuve d'amélioration / estimation du ROI** : **non réalisée** avant le prochain backtest, et aucune cote de score exact historique vérifiée pour le ROI.
6. **Déploiement** : **non réalisé et non autorisé**. Aucun changement du site, des signaux Telegram, de `main`, Supabase ni de la production.

## Décision pour la suite

La suite sera de préparer un **backtest historique comparatif V2 contre V3** et Top 5 / Top 10 / Top 20, sur des mois préenregistrés et qui n'ont pas servi aux paramètres V3. Résultats quotidiens >=1, >=2, >=3 ; taux, calibration, taux de jours couverts, intervalles bootstrap appariés. À lancer seulement sur demande ultérieure de l'utilisateur.

**Preuves GitHub Actions finales** : [42 tests d'intégration V3/V2 antérieurs](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40957279863) ; [37 tests TopK V2/V3 + entraînements à 65 000 matchs synthétiques, tous réussis](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40958575020). Aucun nouveau backtest historique, aucun déploiement.


## 6 — Complément : état final de ce qui était « partiel »

| Point | Avant | Après cette étape | Preuves |
|---|---|---|---|
| Comparateur V2 versus V3 quotidien Top 5/10/20 | Partiel | **Code terminé et validé**, huit modèles, trois cohortes imbriquées et bootstrap par journée | 37 tests automatiques, 4 mois gelés |
| Validation d'un entraînement de 65 000 exemples pour les deux moteurs V3 | Partiel | **Test de capacité réussi** sur 65 000 matchs synthétiques, 160 caractéristiques, classifieur 37 classes | 71,20 s HistGB + 108,36 s Direct ; 551,42 Mio RSS |
| Backtest de gains réels | Non lancé volontairement | **Toujours non lancé** : test distinct prévu après l'audit | Workflow manuel seulement |

Code prêt : `research/ml_v3_topk_compare.py`, `research/ml_v3_capacity_65000.py`, et `.github/workflows/research-ml-v3-topk-backtest-manual.yml`. Ce dernier n'a **aucun déclenchement push ou schedule** ; il doit être activé volontairement lors de l'étude suivante. Les mois enregistrés sont mai/août 2025 et mai/août 2026, quatre mois qui n'ont pas été choisis d'après des résultats V3. La capacité sur matchs **réels** ne peut être certifiée que pendant l'essai historique : ne pas confondre ce contrôle technique synthétique et une validation hors échantillon.
