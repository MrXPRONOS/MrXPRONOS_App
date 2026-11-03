# Hybride V3 — entraînement privé et inférence rapide

## Exécution quotidienne

1. `prepare-hybrid-v3-checkpoint.yml` (02:17 UTC, ou changement de la chaîne) authentifie le corpus scellé, complète les journées SportData jusqu'à J-1, et entraîne **uniquement** le véritable couple HistGradientBoosting utilisé par le modèle Hybride V3. Les autres candidats de recherche (CatBoost, LightGBM, Direct V2/V3) ne sont plus entraînés par ce job. Le modèle, son état statistique et ses calibrations historiques sont sauvegardés en AES-256-GCM dans `research/score_v3_model_checkpoints/YYYY-MM-DD.enc`, sans données en clair sur GitHub.

2. Lorsque la préparation réussit, le déclenchement `workflow_run` peut publier. `exact-scores-v3-daily.yml` reste programmé à 05:17 et 12:17 UTC et reste lançable manuellement. Il charge **obligatoirement** le checkpoint authentifié de J-1, récupère les vrais matchs de J et J+1, calcule les mêmes grilles Hybride V3 11x11 puis produit les Top 5 A/B. Il n'exécute **aucun backtest, apprentissage ni recalibrage à partir de résultats futurs**.

3. Les archives de publication restent `scores-exacts-daily/YYYY-MM-DD.json`, avec déploiement public via `deploy.yml`. Les checkpoints chiffrés et les archives d'entraînement ne doivent jamais être inclus dans le builder Pages `scripts/build_public_site.py`.

## Chronométrage et surveillance

La préparation émet `V3_PREPARE_TIMING` pour le déchiffrement/certification, le rattrapage et le fitting. La publication émet `V3_FAST_TIMING` pour le chargement du checkpoint, les matchs futurs et les grilles/publication. `V3_FAST_PUBLICATION_READY` récapitule les Top 5. Les temps réels varient selon SportData, le runner et la taille du corpus; ne pas annoncer de durée garantie.

Si la préparation échoue ou si le checkpoint ne correspond pas exactement à la veille, le workflow rapide **échoue sans recycler de fausses prévisions**. Pour rétablir le service, corriger la préparation, la relancer, vérifier le checkpoint scellé, puis relancer la publication. Ne jamais inclure une clé dans les journaux.

## Validation requise avant déclaration de succès production

- Recherche PR #288 intégrée sur `research/single-ml-v2-20261024`.
- Tests d'authentification AES-GCM réussis (mauvaise clé, mauvaise date, corruption).
- Comparaison originale/optimisée/checkpoint rechargé des 121 probabilités à `atol=1e-12` dans les tests.
- Anciennes protections de publication et de page toujours vertes.
- En production réelle, vérifier un checkpoint J-1 non vide, `V3_FAST_PUBLICATION_READY` et les fichiers `scores-exacts.json`, archives J/J+1, puis `gh-pages`.
- Comparer les temps réels des étapes à ceux de l'ancien workflow. La vitesse effective ne peut pas être garantie uniquement par les tests simulés.

## Retour arrière

Le mode historique du script `run_exact_scores_v3_daily.py` reste accessible sans `--fast-inference` pour diagnostic ponctuel, mais il est coûteux. Pour un retour arrière de production, annuler le changement du workflow de publication vers `--fast-inference` tout en préservant la provenance des prédictions et la confidentialité des données. Ne pas réutiliser une prévision produite après le coup d'envoi.
