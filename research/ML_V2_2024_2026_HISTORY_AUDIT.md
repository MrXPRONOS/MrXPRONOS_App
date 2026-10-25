# Mr XPRONOS — Résultats historiques chiffrés 2024–2026

Dernière vérification : **25 octobre 2026**, à partir des fichiers d'audit réellement publiés par GitHub Actions.

## Couverture vérifiée

| Mesure | 2024 | 2025 | 2026 (au 24 octobre) |
|---|---:|---:|---:|
| Dates prises en compte | 366 | 365 | 297 |
| Fichiers mensuels BSD + SportScore | 12/12 | 12/12 | **10/10** |
| Journées SportScore initialement en échec | 19 | 10 | 0 |
| Journées en échec après réparation | **0** | **0** | **0** |
| Source BSD retenue après nettoyage | 20 229 | 20 251 | 22 272 |
| Source SportScore retenue | 66 579 | 67 200 | 54 671 |
| Source OpenFootball supplémentaire | 4 523 | — | — |
| Identités date/équipes conservées après contrôle et dédoublonnage | **91 331** | **87 451** | **76 943** |
| Dates ayant touché le plafond SportScore 200 dans la collecte initiale | 278 | 281 | 251 |

**Total des enregistrements retenus sur les trois périodes : 255 725**, dont 76 943 pour 2026 (janvier jusqu'au 24 octobre inclus).

Ce sont des **identités datées de rencontres** dédupliquées par date et noms d'équipes normalisés, et non une preuve de 255 725 rencontres réelles mondialement uniques. Des alias d'équipes ou de compétitions entre fournisseurs peuvent subsister et réclament un rapprochement plus sophistiqué avant entraînement.

Pour 2026 : 297 jours sur 297 contiennent au moins une rencontre validée. **La totalité des rencontres du monde n'est pas garantie**, notamment parce que SportScore coupe à 200 résultats sur 251 dates (la pagination `page`/`offset` ne fonctionne pas, contrôle empirique vérifié), et BSD n'a pas nécessairement tous les matchs de SportScore.

## Sécurité et stockage

Tous les résultats détaillés sont chiffrés **AES-256-GCM** avec le secret Actions `ML_V2_HISTORY_KEY_B64`. Aucun JSON de matchs en clair n'a été commité au dépôt. La provenance BSD/SportScore reste identifiable par enregistrement. Les 29 journées en échec de 2024/2025 ont été récupérées dans des patches chiffrés séparés et les archives mensuelles originales n'ont pas été écrasées.

- `research/encrypted_football/openfootball/2024.enc`
- `research/encrypted_football/bsd_sportscore/2024/01.enc` à `12.enc`
- `research/encrypted_football/bsd_sportscore/2024_repair.enc`
- `research/encrypted_football/bsd_sportscore/2025/01.enc` à `12.enc`
- `research/encrypted_football/bsd_sportscore/2025_repair.enc`
- `research/encrypted_football/bsd_sportscore/2026/01.enc` à `10.enc` — Octobre s'arrête au 24/10/2026.

Les rapports publics ne contiennent que des **métriques agrégées** :
`research/2024_multisource_audit.json`,
`research/2025_multisource_audit.json`,
`research/2026_multisource_audit.json`.

Le module `research/single_ml_v2_2024_union.py` recompose une année demandée uniquement en mémoire ou dans `/tmp` lors des tests GitHub ; pour 2026 il faut passer `--year 2026 --through 2026-10-24`.

## Exécutions GitHub vérifiées

- 2024 : réparation [40188754992](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40188754992), audit final [40189472398](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189472398).
- 2025 : collecte [40188892482](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40188892482), réparation [40189411683](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189411683), audit final [40189596063](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189596063).
- 2026 : collecte [40192238592](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40192238592), contrôle automatique d'absence d'échecs [40192464479](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40192464479), audit final [40192709511](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40192709511).

## Important pour ML V2

- Aucun xG historique ni cote d'avant-match n'a été inventé.
- Les résultats complets ne sont pas des prévisions réalisées avant les matchs ; **les backtests chronologiques et tests prospectifs doivent encore être exécutés** avec contrôle strict du leakage.
- Les données d'août–octobre 2026 peuvent servir aux tests de validation selon les découpages temporels définis, avec bornage au 24/10/2026.
- Les données et expériences restent sur la branche de recherche `research/single-ml-v2-20261024` : aucun changement du site, des envois Telegram, de Supabase ou de Neon.
