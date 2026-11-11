# Mr XPRONOS — Audit d'implémentation Top10 quotidien V3

**Objectif** : augmenter le nombre de journées atteignant 10 pronostics réels, sans inventer de matchs ni abaisser aveuglément les exigences du moteur Dixon-Coles. Une production de 10 matchs CHAQUE jour n'est pas garantie par un nombre de ligues : le calendrier, les données et les logos restent des contraintes externes.

## Liste de contrôle (état du code)

- [x] **1 — Extension des sources** : 48 compétitions dans le catalogue ESPN, dont **31 activées** et **17 candidates écartées/à revérifier**. Les 17 ajouts activés ont passé un audit sur trois années : >=80 résultats, >=8 équipes disposant de 4 matchs, dernier résultat <=35 jours, >=5 affiches archivées avec deux URL d'écussons valides, aucune année tronquée exactement à 400 résultats. **Validation : complète pour la liste activée ; couverture quotidienne garantie : non.**
- [x] **2 — Classement A/B/C** : A importance >=220, B 145–219, C inférieur à 145 (avec plancher de sélection à 70 dans le workflow). Une première passe respecte le quota de 4 par ligue ; le complément peut le dépasser pour éviter de manquer de matchs fiables. Une finale/un derby restent les plus prioritaires. Les U21/réserves n'héritent pas du prestige des seniors.
- [x] **3 — Modes** : strict=10, flexible=1–10 ; CLI, filtre `run_daily`, rendu néon, validateur, manifeste et légende adaptés. Le mode flexible est **opt-in manuel**, et la tâche planifiée de 20 h utilise **strict**. Les tests de données et validateurs sont prévus ; validation audiovisuelle finale sur chaque réseau social : **partielle**.
- [x] **4 — Filtres de fiabilité** : 80 matchs/compétition, 4 par équipe, historique 35 jours, résultat antérieur au cutoff, URLs de logos authentiques ; rejet des archives annuelles de 400 matchs possiblement tronquées ; pas de match inventé, pas d'initiales si un logo échoue en rendu.
- [x] **5 — Diagnostic** : `selection_diagnostics` donne découverts, examinés, éligibles, retenus, manquants, raisons des exclusions, répartition A/B/C, par championnat et avertissements ; `skipped.json` et `predictions.json` archivés à chaque GitHub Action.
- [x] **6 — Backtest codé** : simulation d'octobre 2026 sur les ligues activées, en 5 blocs GitHub Actions, scores réels isolés des prédictions, rapport par jour, par championnat et éligibilité stricte/flexible. **Le résultat chiffré ne doit pas être déclaré tant que le job de 31 jours et son agrégation n'ont pas réussi.**

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
