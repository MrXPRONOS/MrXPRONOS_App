# Mr XPRONOS — ML V2 : audit du score 1–1 et comparaison rétrospective multisaison

Audit produit le **26 octobre 2026** sur branche isolée `research/single-ml-v2-20261024`. Enregistrement des périodes avant exécution dans `ML_V2_1_1_MULTIPERIOD_PROTOCOL.md`.

**GitHub Actions : [exécution réussie #40409360258](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40409360258)**, cinq jobs `success` (4 périodes + comparaison globale), tests unitaires préalables réussis. Artifacts agrégés téléchargeables dans l'exécution : `ml-v2-four-period-pooled-aggregate` et `ml-v2-long-*`.

## Périmètre et statut de preuve

- Source : union historique chiffrée 2024–2026, **255 716** résultats de football certifiés (source SportScore/BSD et OpenFootball 2024), sans les identités contradictoires mises en quarantaine.
- Quatre blocs de **28 jours** : 2025-03-01..28 (**6 812** matchs), 2025-09-01..28 (**7 243**), 2026-03-01..28 (**7 296**), 2026-09-01..28 (**7 787**) ; ensemble **29 138 matchs, 112 journées UTC**.
- Toutes les méthodes ont reçu les **mêmes fixtures**, les mêmes caractéristiques d'avant-match, seulement les scores des jours antérieurs à la journée évaluée. Cadence de réentraînement 30 j et paramètres fixes, sans tuning sur le test.
- **C'est un rejeu chronologique rétrospectif**, PAS 29 138 pronostics horodatés avant les coups d'envoi. Aucune preuve de rendement financier ; aucune cote score exact pré-match vérifiée, xG historiques inexistants dans ces archives. Certains fournisseurs plafonnent à 200 matchs/jour : la couverture mondiale n'est pas exhaustive.
- Le premier test exploratoire du 2026-10-20 au 2026-10-22 (707 matchs) n'a pas été réutilisé dans les quatre périodes.

## Cinq modèles : cohortes strictement appariées

| Modèle | Hits / 29 138 | Top 1 % | Wilson 95 % | Top 3 % | Log-loss | Brier du top 1 |
|---|---:|---:|---:|---:|---:|---:|
| HistGradientBoosting (référence) | **3 114** | **10,6871** | 10,338–11,047 | **28,4817** | **3,183664** | 0,094716 |
| ML + Dixon–Coles hybride | 3 056 | 10,4880 | 10,141–10,845 | 28,4645 | 3,184728 | 0,093150 |
| CatBoost | 3 037 | 10,4228 | 10,077–10,779 | 28,1969 | 3,192107 | 0,092720 |
| LightGBM | 3 024 | 10,3782 | 10,033–10,734 | 27,8365 | 3,193484 | 0,092331 |
| Classification directe | 2 922 | 10,0281 | 9,689–10,378 | 28,3822 | 3,189524 | **0,089696** |

HistGradientBoosting se classe premier au Top 1 ET au log-loss dans **les quatre fenêtres**. Le Brier du score modal (moyenne du carré de l'écart entre confiance top-1 et exactitude observée) avantage au contraire la classification directe ; cette métrique simplifiée ne représente pas le Brier multiclasses complet.

### Intervalles de différence de Top 1 (modèle – HistGB, en points de %)

Bootstrap stratifié apparié par journée UTC : **3 000 tirages**, **112 journées**. Les modèles comparent exactement les mêmes matchs dans chaque fenêtre.

| Concurrent | Écart observé pp | IC bootstrap à 95 % |
|---|---:|---:|
| Hybride | -0,1991 | [-0,4034 ; +0,0138] |
| CatBoost | -0,2643 | [-0,5088 ; -0,0239] |
| LightGBM | -0,3089 | [-0,5566 ; -0,0525] |
| Direct | -0,6590 | [-1,0920 ; -0,2467] |

L'IC de l'hybride contient zéro : **pas de supériorité statistique établie de HistGB sur l'hybride par bootstrap journalier**. Sur CatBoost, LightGBM et Direct, les IC descriptifs de cette évaluation favorisent HistGB. **Il ne s'agit pas de preuve de performance future ni d'une correction pour comparaisons multiples.** Des contrôles par blocs de 7 jours ont aussi été calculés : ils sont accessibles dans le rapport `four-period-pooled-results.json` ; avec seulement ~16 blocs, leur portée reste limitée.

## Diagnostic : un 1–1 modal fréquent n'est pas un P(1–1) de 50 %

Le 1–1 est réellement survenu dans **9,4001 %** des 29 138 matchs. Les grilles de probabilités disent :

| Modèle | 1–1 choisi comme score Top 1 | Probabilité P(1–1) moyenne | Biais P(1–1) – réalité |
|---|---:|---:|---:|
| HistGB | 52,5843 % | 10,1774 % | **+0,7773 pp** |
| Hybride | 56,6820 % | 10,3561 % | +0,9560 pp |
| CatBoost | 55,5598 % | 10,2794 % | +0,8793 pp |
| LightGBM | 59,3246 % | 10,2739 % | +0,8738 pp |
| Direct | 34,3538 % | 9,7741 % | +0,3740 pp |

L'intervalle bootstrap par journée pour **le biais de la cellule P(1–1) de HistGB** est **[+0,4161 ; +1,1389 pp]** ; sensibilité par blocs de 7 jours **[+0,4976 ; +1,0873 pp]**. La surestimation est relativement modérée en amplitude, mais récurrente sur les périodes retenues.

**Mécanisme explicatif plausible** : avec deux buts modélisés comme deux Poisson indépendants et deux intensités comprises chacune entre 1 et 2 buts, **1–1 est le score modal** (plus probable parmi les scores individuels), même si P(1–1) vaut seulement de l'ordre de 10–15 %. En conséquence, supprimer automatiquement 1–1 des pronostics parce qu'il représente >50 % des modes est une mauvaise correction statistique. Cette explication est structurelle ; le diagnostic ne prouve pas qu'elle explique 100 % des décisions individuelles.

Le contrôleur de recherche enregistre désormais la vraie probabilité P(1–1), le second score et l'écart modal, des tranches de calibration, ainsi que des contrefactuels **non optimisés** quand 1–1 devance à peine le second score. Aucune correction post-hoc n'a été appliquée au test.

## Décision prudente / feuille de route

1. Conserver **HistGradientBoosting comme référence de recherche** ; pas de remplacement automatique en production, l'avance Top 1 (0,2 à 0,66 point) est limitée et évaluée rétrospectivement.
2. Examiner les bins P(1–1) et la force de forme/identité/compétition par cohorte, pour séparer la surestimation modérée des problèmes de couverture/qualité des matchs.
3. Expérimenter un **recalibrage P(1–1)** exclusivement sur une période de développement antérieure ; renormaliser les 121 cellules sans antidater les observations ; vérifier sur un holdout réellement indépendant le log-loss et les hits (un recalibrage peut dégrader le Top 1).
4. Enregistrer de véritables grilles chiffrées **avant** coup d'envoi et les résultats indépendants ensuite, puis cumuler suffisamment de matchs et de semaines pour une validation prospective. Activer le workflow futur seulement avec autorisation sur les dépenses de requêtes API.
5. Les chiffres présents n'impliquent aucune garantie de réussite ou ROI de paris.

**Isolation** : tous les changements sont dans `research/` et des workflows de recherche. Aucune modification du site, de Telegram, de Supabase/Neon ou de `main`.


## Diagnostic approfondi : où se situe la surestimation du 1–1 ?

**HistGB, quatre périodes réunies**, stratification par la vraie probabilité annoncée `P(1–1)` (les bins sont définis dans le code, pas choisis après les scores) :

| Probabilité P(1–1) annoncée | Matchs | Moyenne prévue | Fréquence réelle |
|---|---:|---:|---:|
| 0 % à moins de 5 % | 1 276 | 3,72 % | 1,80 % |
| 5 % à moins de 10 % | 10 299 | 8,18 % | 6,48 % |
| 10 % à moins de 15 % | 17 563 | 11,82 % | 11,67 % |

La **surestimation se concentre surtout dans les rencontres où P(1–1) est déjà faible**. Dans la tranche 10–15 %, la calibration empirique est beaucoup plus proche des probabilités. Ceci fournit une piste pour un recalibrage *conditionnel*, à tester sur des données ultérieures et non sur ces résultats.

### Diagnostic de substitution du 1–1 par le second score

Des seuils de faible écart de probabilité Top 1 – Top 2 ont été **fixés en avance** (0,005 ; 0,01 ; 0,02 en probabilité absolue). Une substitution uniquement si le Top 1 est 1–1 montre les changements de nombre de succès suivants, sur les quatre périodes :

| Modèle | Écart ≤ 0,005 | Écart ≤ 0,01 | Écart ≤ 0,02 |
|---|---:|---:|---:|
| HistGB | **0** | **−59** | **−97** |
| Hybride | +4 | −34 | −71 |
| LightGBM | +8 | +28 | −96 |
| CatBoost | +40 | +22 | −71 |
| Direct | +24 | −41 | −69 |

Ces écarts ne sont **pas des gains validés ni une stratégie retenue** : ils sont estimés sur le même jeu d'observation rétrospectif, sans intervalles par sous-groupe, et doivent être vérifiés sur un nouveau holdout préenregistré. **Surtout, forcer HistGB à éviter 1–1 peut dégrader nettement ses scores exacts**. Aucun changement de décision n'a été déployé.
