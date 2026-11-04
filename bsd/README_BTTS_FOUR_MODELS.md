# BSD V2 — quatre nouveaux systèmes BTTS

## Objectif et sorties
Les quatre systèmes ont été conçus pour améliorer la probabilité `BTTS_YES` **sans inventer d'indicateurs externes**. Toutes les entrées proviennent de matchs terminés, rendus disponibles par `V2History` au moins quatre heures après leur coup d'envoi. Les probabilités `BTTS_NO` restent `1 - P(BTTS_YES)`. Les marchés résultat, double chance et over/under ne sont pas réécrits.

## 1. LightGBM (machine learning)
- Module : `bsd_v2_btts_lgbm.py`.
- Deux classes (BTTS Oui/Non), algorithme de boosting sur arbres avec profondeur limitée, régularisation, graine fixe et un seul thread.
- Entrées : estimations des buts, buts marqués/concédés récemment, performances par terrain, probabilité pré-match d'être muet, clean sheets adverses, repos, quantité et fraîcheur de l'historique.
- L'algorithme est *LightGBM*, pas un XGBoost réécrit. Dépendance incluse en production et CI.

## 2. Poisson bivariée
- Module : `bsd_v2_btts_bivariate.py`.
- Modèle exact : `H=U+W, A=V+W`, avec `U,V,W` des Poisson indépendantes.
- Le paramètre `W` crée une covariance positive ajustée par vraisemblance des scores historiques; les deux moyennes marginales restent celles de BSD V2.
- Limite : la famille bivariée Poisson à composante commune ne représente pas une covariance négative.

## 3. Zero-Inflated Poisson
- Module : `bsd_v2_btts_zip.py`.
- Distribution `P(0)=π+(1-π)exp(-λ)` et `P(k>0)=(1-π)Poisson(k;λ)`.
- Le taux de zéro structurel `π` dépend des historiques de clean sheets et de matchs sans marquer; `λ` est corrigé pour conserver la moyenne `μ=λ(1-π)`.
- Paramètres domicile/extérieur distincts, ajustés par maximisation de vraisemblance sur 2024.
- Limite : ZIP ne permet pas à lui seul de modéliser les équipes avec *moins* de zéros que Poisson ; il peut revenir à `π=0`.

## 4. Ensemble Learning
- Module : `bsd_v2_btts_ensemble.py`.
- Combine l'ancien BTTS spécialisé, LightGBM, Poisson bivariée et ZIP.
- Poids non négatifs, somme égale à un, poids de l'ancien moteur d'au moins 40 %.
- Sélectionne ses coefficients exclusivement sur septembre-décembre 2024, puis confirme le gain sur septembre-décembre 2025.
- Exige une baisse du Brier Score sur **les deux périodes**. Si une validation échoue, les nouveaux coefficients restent zéro et l'ancien moteur est préservé.
- Le backtest 2026 est hors échantillon et ne sert pas au choix des paramètres.

## Exécution
- Commande des tests : `python -m unittest discover -s bsd -p 'test_*.py' -v`.
- Audit 2026 : `python bsd/bsd_v2_btts_backtest.py --max-test 30000 --start-date 2026-01-01 --end-date 2026-11-02`.
- Workflow : `.github/workflows/bsd-btts-four-2026-acceptance.yml`.
- En production, le workflow installe explicitement `lightgbm` et `scikit-learn`.
- `model_audit.btts_challenger_shadow` expose les probabilités des trois nouveaux modèles et les poids de l'ensemble, même lorsque l'activation est refusée.

## Limitations et politique de diffusion
Ce système utilise seulement les données disponibles. Les véritables xG, tirs, compositions et absences ne sont pas présents dans l'historique et ne sont pas inventés. Les scores de match rétrospectifs ne constituent pas des paris passés. Sans cotes pré-match enregistrées, on ne peut pas déduire un ROI, ni garantir 70 % ou 80 % de réussite. Le moteur continue à appliquer ses filtres de qualité, de cotes et de publication; les anciennes sélections restent figées.
