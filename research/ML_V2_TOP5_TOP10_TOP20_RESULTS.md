# ML V2 — Top 5, Top 10 et Top 20 quotidiens : quatre mois historiques

**Statut** : backtest rétrospectif effectué le 26 octobre 2026 sur la branche isolée `research/single-ml-v2-20261024`.

**Évidence d'exécution** : [GitHub Actions #40415945575](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40415945575) : quatre tests mensuels et la consolidation **success**. Les rapports JSON agrégés, historiques quotidiens anonymisés et intervalles de confiance sont conservés dans les artifacts de cette exécution. La règle et les quatre mois avaient été fixés avant leurs résultats dans `ML_V2_TOP5_TOP10_TOP20_PROTOCOL.md`.

## Méthode

À chaque journée UTC, chaque modèle produit un score exact modal pour tous les matchs présents dans l'archive certifiée. Il classe ces matchs par **probabilité la plus haute du score exact qu'il prédit** (ordre décroissant, identité stable en cas d'égalité). Il retient Top 5, Top 10 (qui contient les cinq premiers) et Top 20 (qui contient les dix premiers). Les résultats des rencontres sont consultés **après** ce classement et ne sont pas des variables de sélection. Les cinq modèles partagent chaque jour le **même univers** mais sélectionnent des rencontres éventuellement différentes.

- Quatre mois complets : octobre 2025 (31 jours, 7 924 matchs), janvier 2026 (31 jours, 7 865), avril 2026 (30 jours, 7 966) et septembre 2026 (30 jours, 8 218).
- Soit **31 973 matchs**, **122 jours**. Toutes les journées disposent d'au moins 20 matchs (entre **133** et **520** rencontres selon la journée), donc aucun quota quotidien incomplet.
- Les cinq moteurs : HistGradientBoosting (HistGB), HistGB + Dixon-Coles hybride, LightGBM, CatBoost, classification directe.
- Chaque moteur est entraîné chronologiquement sur les journées précédentes, cadence de réentraînement 30 jours, sans changer de paramètres après avoir vu les résultats.
- Un Top 5 représente **610** choix par modèle, Top 10 **1 220**, Top 20 **2 440**.
- Les scores historiques sont de vrais résultats d'archives et les classements sont recalculés en rejeu chronologique ; **ce n'est pas une prédiction prospective archivée avant le coup d'envoi**. La possibilité de connaître *tous* les matchs de la journée avec la même couverture avant le premier match reste à confirmer en situation réelle.

## Résultats cumulés par taille de liste

| Modèle | Top 5 / 610 | Taux Top 5 | Top 10 / 1 220 | Taux Top 10 | Top 20 / 2 440 | Taux Top 20 |
|---|---:|---:|---:|---:|---:|---:|
| **HistGB** | **120** | **19,6721 %** | **233** | **19,0984 %** | **424** | **17,3770 %** |
| Hybride | 115 | 18,8525 % | 226 | 18,5246 % | 413 | 16,9262 % |
| LightGBM | 110 | 18,0328 % | 201 | 16,4754 % | 399 | 16,3525 % |
| CatBoost | 105 | 17,2131 % | 193 | 15,8197 % | 368 | 15,0820 % |
| Direct | 103 | 16,8852 % | 204 | 16,7213 % | 371 | 15,2049 % |

**HistGB est le premier modèle au cumul pour chaque K**, mais ses avantages sont modestes et varient selon le sous-groupe.

### Gagnants de chaque mois

| Mois | Top 5 : meilleur(s) scores exacts | Top 10 : meilleur(s) | Top 20 : meilleur(s) |
|---|---|---|---|
| **Oct. 2025** | **Direct** 30/155 (19,35 %) | **Direct** 52/310 (16,77 %) | **CatBoost** 96/620 (15,48 %) |
| **Jan. 2026** | **HistGB** 38/155 (24,52 %) | **HistGB** 79/310 (25,48 %) | **HistGB** 128/620 (20,65 %) |
| **Avr. 2026** | **HistGB et LightGBM** 30/150 (20,00 %) | **Hybride** 58/300 (19,33 %) | **HistGB** 102/600 (17,00 %) |
| **Sept. 2026** | **HistGB et Hybride** 28/150 (18,67 %) | **HistGB** 53/300 (17,67 %) | **HistGB** 100/600 (16,67 %) |

### Détail mensuel : taux de réussite par modèle

| Mois / K | HistGB | Hybride | LightGBM | CatBoost | Direct |
|---|---:|---:|---:|---:|---:|
| Oct 2025 / Top 5 | 15,48 % | 14,19 % | 12,90 % | 13,55 % | **19,35 %** |
| Oct 2025 / Top 10 | 15,16 % | 14,19 % | 13,87 % | 15,16 % | **16,77 %** |
| Oct 2025 / Top 20 | 15,16 % | 14,68 % | 14,03 % | **15,48 %** | 14,35 % |
| Jan 2026 / Top 5 | **24,52 %** | 23,23 % | 22,58 % | 23,23 % | 20,00 % |
| Jan 2026 / Top 10 | **25,48 %** | 24,19 % | 20,97 % | 19,68 % | 19,68 % |
| Jan 2026 / Top 20 | **20,65 %** | 20,16 % | 19,52 % | 18,23 % | 18,55 % |
| Avr 2026 / Top 5 | **20,00 %** | 19,33 % | **20,00 %** | 18,67 % | 14,67 % |
| Avr 2026 / Top 10 | 18,00 % | **19,33 %** | 16,67 % | 15,67 % | 17,00 % |
| Avr 2026 / Top 20 | **17,00 %** | 16,67 % | 16,83 % | 14,83 % | 14,33 % |
| Sept 2026 / Top 5 | **18,67 %** | **18,67 %** | 16,67 % | 13,33 % | 13,33 % |
| Sept 2026 / Top 10 | **17,67 %** | 16,33 % | 14,33 % | 12,67 % | 13,33 % |
| Sept 2026 / Top 20 | **16,67 %** | 16,17 % | 15,00 % | 11,67 % | 13,50 % |

## Lecture pratique HistGB : sélection plus serrée versus quantité

| Quota / jour | Scores exacts cumulés | Réussite des choix | Moyenne de bons scores/jour | Journées avec au moins un score exact |
|---|---:|---:|---:|---:|
| **5** | 120 | **19,67 %** | 0,98 | 75 / 122 (**61,48 %**) |
| **10** | 233 | 19,10 % | 1,91 | 102 / 122 (**83,61 %**) |
| **20** | 424 | 17,38 % | 3,48 | 119 / 122 (**97,54 %**) |

Le Top 20 a mécaniquement plus de réussites brutes car il contient le Top 10, lui-même contenant le Top 5. Son taux de réussite par sélection est inférieur. Le taux des choix additionnels **6–10** pour HistGB est (233−120)/610 = **18,52 %** ; les choix additionnels **11–20** sont (424−233)/1 220 = **15,66 %**. Cela montre une dégradation progressive de la qualité moyenne quand on descend le classement.

L'intervalle Wilson descriptif à 95 % du Top 5 HistGB est **[16,71 % ; 23,01 %]**. Les moyennes de confiance annoncées par HistGB sont **16,69 %** pour Top 5, **15,95 %** pour Top 10 et **15,05 %** pour Top 20 : leur calibration conditionnelle doit être vérifiée, notamment sur les scores extrêmes.

## Incertitude des comparaisons

Le rapport applique **4 000 rééchantillonnages** bootstrap **par journée UTC**, stratifiés par mois et appariés sur les journées communes. Les modèles choisissent parfois des matchs différents : **les pronostics sélectionnés ne forment pas une cohorte de matchs appariés entre modèles**. Une analyse de sensibilité refait le bootstrap par blocs de sept jours.

IC bootstrap 95 % de la différence de taux **concurrent − HistGB** en points de pourcentage :

| Modèle comparé | Top 5 | Top 10 | Top 20 |
|---|---|---|---|
| Hybride | [−2,79 ; +1,15] | [−1,80 ; +0,66] | [−1,31 ; +0,45] |
| LightGBM | [−5,08 ; +1,80] | [−4,75 ; −0,66] | [−2,54 ; +0,37] |
| CatBoost | [−5,90 ; +0,98] | [−5,57 ; −1,07] | [−3,81 ; −0,86] |
| Direct | [−6,89 ; +1,15] | [−5,25 ; +0,25] | [−3,98 ; −0,41] |

**Top 5 : aucun de ces intervalles n'exclut zéro**, donc la place de premier de HistGB sur les quatre mois ne prouve pas une supériorité statistique au Top 5.

**Top 10 :** les intervalles favorisent HistGB face à LightGBM et CatBoost ; pas de différence suffisamment établie face à l'Hybride ou Direct.

**Top 20 :** les intervalles favorisent HistGB face à CatBoost et Direct ; pas face à l'Hybride ou LightGBM.

Les intervalles sont exploratoires, non corrigés pour les nombreux tests entre modèles et tailles de sélections. Le sens statistique dépend du protocole d'échantillonnage (122 jours, quatre mois isolés), et aucune performance future n'est garantie.

### Comparer les tailles de sélection sur HistGB

IC bootstrap quotidien 95 % de la différence de taux **Top K − Top 5** :
- **Top 10 − Top 5** : [−2,87 ; +1,72] points.
- **Top 20 − Top 5** : [−5,20 ; +0,49] points.
- Sensibilité par blocs de 7 jours : Top 20 − Top 5 = [−4,47 ; −0,08] points.

L'ampleur du gain de précision du Top 5 par rapport au Top 20 **reste sensible au choix de la méthode bootstrap**. Il n'y a aucune preuve de gain économique sans les cotes.

## Recommandations et limites

1. **Tester HistGB Top 5 comme référence de recherche** si l'objectif est de limiter le nombre de suggestions. **Tester en parallèle HistGB Top 10** si l'objectif est d'avoir plus régulièrement un score exact parmi les pronostics (102/122 jours contre 75/122 au Top 5). Ne pas changer la production sur cette étude seule.
2. Garder l'Hybride comme deuxième candidat proche. Examiner également l'évolution des gagnants selon mois : en octobre 2025 Direct et CatBoost étaient en tête sur différents K.
3. Vérifier en mode prospectif l'univers réellement accessible **avant** les rencontres ; cette étude avait toutes les rencontres d'une journée historique disponibles au moment du rejeu.
4. Archiver chaque jour les scores, probabilités et Top K **avant coup d'envoi**, sans réviser rétroactivement les sélections ; vérifier les données de résultats indépendamment.
5. Aucun ROI calculable en l'absence de cotes de score exact historiques certifiées. Un fort taux de scores exacts n'implique pas nécessairement qu'un pari soit rentable. Ne pas présenter ces probabilités comme garanties.

**Sécurité et isolation :** les matchs et prédictions de chaque journée restent sur les runners temporaires GitHub. Seuls les indicateurs agrégés anonymisés sont téléchargés. Aucun changement à `main`, Telegram, Supabase ou au site.
