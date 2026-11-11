# Mr XPRONOS — Audit d'implémentation Top10 quotidien V3

**Objectif** : augmenter le nombre de journées atteignant 10 pronostics réels, sans inventer de matchs ni abaisser aveuglément les exigences du moteur Dixon-Coles. Une production de 10 matchs CHAQUE jour n'est pas garantie par un nombre de ligues : le calendrier, les données et les logos restent des contraintes externes.

## Liste de contrôle (état du code)

- [x] **1 — Extension des sources** : 48 compétitions dans le catalogue ESPN, dont **31 activées** et **17 candidates écartées/à revérifier**. Les 17 ajouts activés ont passé un audit sur trois années : >=80 résultats, >=8 équipes disposant de 4 matchs, dernier résultat <=35 jours, >=5 affiches archivées avec deux URL d'écussons valides, aucune année tronquée exactement à 400 résultats. **Validation : complète pour la liste activée ; couverture quotidienne garantie : non.**
- [x] **2 — Classement A/B/C** : A importance >=220, B 145–219, C inférieur à 145 (avec plancher de sélection à 70 dans le workflow). Une première passe respecte le quota de 4 par ligue ; le complément peut le dépasser pour éviter de manquer de matchs fiables. Une finale/un derby restent les plus prioritaires. Les U21/réserves n'héritent pas du prestige des seniors.
- [x] **3 — Modes** : strict=10, flexible=1–10 ; CLI, filtre `run_daily`, rendu néon, validateur, manifeste et légende adaptés. Le mode flexible est **opt-in manuel**, et la tâche planifiée de 20 h utilise **strict**. Les tests de données et validateurs sont prévus ; validation audiovisuelle finale sur chaque réseau social : **partielle**.
- [x] **4 — Filtres de fiabilité** : 80 matchs/compétition, 4 par équipe, historique 35 jours, résultat antérieur au cutoff, URLs de logos authentiques ; rejet des archives annuelles de 400 matchs possiblement tronquées ; pas de match inventé, pas d'initiales si un logo échoue en rendu.
- [x] **5 — Diagnostic** : `selection_diagnostics` donne découverts, examinés, éligibles, retenus, manquants, raisons des exclusions, répartition A/B/C, par championnat et avertissements ; `skipped.json` et `predictions.json` archivés à chaque GitHub Action.
- [x] **6 — Backtest codé** : simulation d'octobre 2026 sur les ligues activées, en 5 blocs GitHub Actions, scores réels isolés des prédictions, rapport par jour, par championnat et éligibilité stricte/flexible. **Résultat du backtest indépendant : 31 jours/31 et cinq segments réussis ; 14/31 journées à 10 matchs, 28/31 journées compatibles avec le mode flexible.**

## Ligues validées et activées (17 ajouts)

Portugal (`por.1`), Pays-Bas (`ned.1`), Turquie (`tur.1`), Écosse (`sco.1`), Belgique (`bel.1`), Brésil (`bra.1`), Mexique (`mex.1`), Arabie saoudite (`ksa.1`), Japon (`jpn.1`), Afrique du Sud (`rsa.1`), Libertadores (`conmebol.libertadores`), Sudamericana (`conmebol.sudamericana`), CAF Champions League (`caf.champions`), AFC Champions League (`afc.champions`), Coupe d'Allemagne (`ger.dfb_pokal`), Coupe du Roi (`esp.copa_del_rey`), Coupe de France (`fra.coupe_de_france`).

## Candidats explicitement refusés en l'état

- Sources absentes/invalides : `egy.1`, `kor.1`, `mar.1`, `caf.confederation`.
- Archives annuelles au plafond de 400 matchs, donc risque de troncature : `eng.2`, `col.1`, `usa.1`, `arg.1`.
- Historique trop ancien ou trop réduit selon le critère de 35 jours : `uefa.nations`, `concacaf.champions`, `ita.coppa_italia`, `fifa.worldq.uefa`, `fifa.worldq.caf`, `fifa.worldq.conmebol`, `conmebol.america`, `caf.nations`, `concacaf.gold`.

Les compétitions peuvent être réévaluées lors d'une autre période de saison. Le filtrage est une garde de *disponibilité*, pas une estimation de qualité des prédictions.

## Contrôles et preuves

- Audit réseau indépendant : GitHub Actions « Coverage V3 - candidate football league audit (no publishing) », run `43051241411`. Les requêtes proviennent du système ESPN public non officiel.
- Tests : `dixon-coles/tests/test_daily_top10_v3.py`, `tests/test_social_exact_score_video.py`, `dixon-coles/tests/test_daily_espn.py`, `dixon-coles/tests/test_backtest_top10_v3.py`.
- Backtest : `.github/workflows/backtest-top10-v3.yml`, `dcscore.backtest_top10_v3` et `dcscore.combine_backtest_v3`.
- Publication : `.github/workflows/dixon-coles-social-top10-20h.yml`, strict par défaut, modes de dispatch `strict/flexible`.
- Résultats du test V2 d'octobre : 8/31 jours à 10 matchs, 131 prédictions, 16 scores exacts. Il s'agit de l'ancienne source, **ne pas annoncer une amélioration V3 sans résultats propres**.

## Limites obligatoires

Un score de popularité n'est pas une mesure d'audience. La présence de 31 compétitions n'assure pas que 10 matchs ont lieu le même jour avec des historiques exploitables. ESPN n'est pas une validation officielle des championnats, et les droits d'usage commercial doivent être vérifiés. Le backtest rejoue les calendriers ESPN connus aujourd'hui : ce ne sont pas des enregistrements immuables de prévisions réellement publiées la veille. Sans cotes, aucun ROI ne peut être affirmé.

## Backtest V3 d'octobre (31 ligues actives)

Les cinq segments historiques ont été exécutés avec la branche V3 (sans scores futurs dans les entrées du modèle). Une agrégation indépendante a contrôlé les 31 jours sans doublons et créé les fichiers JSON/CSV.

| Mesure | V2 (14 ligues) | V3 (31 ligues) |
|---|---:|---:|
| Matchs détectés | 340 | 759 |
| Matchs admissibles | 205 | 497 |
| Pronostics sélectionnés | 131 | 202 |
| Journées à 10 matchs | 8 | 14 |
| Journées compatibles vidéo flexible | Non mesuré | 28 |
| Scores exacts Top 1 | 16 / 131 (12,21 %) | 22 / 202 (10,89 %) |
| Résultats 1N2 | 79 / 131 (60,31 %) | 127 / 202 (62,87 %) |

Le nombre de jours à 10 augmente de **6**, mais le taux de scores exacts diminue. Les cohortes sont différentes, ce qui interdit d'attribuer un changement de précision au classement éditorial seul. Sur V3, un score 1-1 systématique aurait trouvé 23/202 contre 22/202 pour le score modal de Dixon-Coles : il faut encore améliorer la qualité du score exact avant de prétendre à un avantage.

**Décisions** :
- [x] Activer les 17 ligues avec preuve historique : **31 sources active(s)** dans la branche V3.
- [x] Conserver la planification **stricte à 10** plutôt que de publier des matchs fictifs.
- [x] Exposer l'option flexible en dispatch manuel ; ce n'est pas une garantie d'envoi sur chaque réseau.
- [x] Sauvegarder les rapports JSON/CSV et la ventilation des rejets.
- [x] Backtest complet sur 31 jours (les cinq blocs ont réussi et les fichiers ont été réunis indépendamment).
- [ ] Prouver 10 pronostics **chaque jour** : impossible sur ce mois avec ces sources / seuils (seulement 14/31).
- [ ] Valider l'envoi effectif de vidéos flexibles sur toutes les plateformes : non fait.
- [ ] Démontrer un gain robuste de précision du score exact : non établi.

Liens des vérifications : tests GitHub et workflow `backtest-top10-v3.yml`. Les données historiques ESPN sont reconstruites et ne constituent pas des journaux de pronostics pré-enregistrés.
