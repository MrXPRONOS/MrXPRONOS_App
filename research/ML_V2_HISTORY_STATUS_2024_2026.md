# Mr XPRONOS — Contrôle des archives de matchs 2024–2026

Date de vérification : 25 octobre 2026. **Données de recherche uniquement.** Sources : BSD API, SportScore, et OpenFootball CC0 pour 2024.

## État effectivement confirmé par GitHub Actions

| Année | Période vérifiée | Journées SportScore initialement échouées | Journées réparées | Matchs retenus après rapprochement strict |
|---|---|---:|---:|---:|
| 2024 | 1er janv. – 31 déc. | 19 | 19 | **91 331** |
| 2025 | 1er janv. – 31 déc. | 10 | 10 | **87 451** |
| 2026 | 1er janv. – **24 octobre** | 0 | 0 (aucun échec) | **76 934** |
| **Total** | 2024 + 2025 + 2026 partielle | **29** | **29** | **255 716** |

Le total est celui des **identités de rencontres retenues sous la règle conservatrice** (date UTC + noms normalisés des deux équipes), **pas une garantie de 255 725 rencontres globalement uniques**. Des alias d'équipes différents entre sources peuvent encore créer des doublons, et deux véritables rencontres aux mêmes noms/date peuvent être confondues. Chaque archive source est conservée.

### Vérifications 2026

- Calendrier **297 jours sur 297** avec au moins un résultat de football certifié (1er janvier au 24 octobre 2026). Une journée avec un match certifié ne garantit pas que tous les matchs de cette journée sont couverts.
- **10 archives mensuelles chiffrées AES-256-GCM** vérifiées, depuis `research/encrypted_football/bsd_sportscore/2026/01.enc` jusqu'à `10.enc`.
- **415 requêtes** pour la collecte initiale BSD/SportScore ; **118 requêtes complémentaires** pour réconcilier l'intégralité des identifiants BSD de 2026.
- BSD a fourni **22 287** fiches certifiées avec identifiants fournisseur. Le premier rapprochement n'en avait conservé que **22 272**, soit 15 observations manquantes. Le contrôle indépendant a récupéré et conservé les **15** dans `research/encrypted_football/bsd_sportscore/2026_bsd_reconcile.enc` (AES-256-GCM) : **6** doublons mêmes équipes/date/même score et **9** identités avec score différent. Les **9 identités aux scores contradictoires sont exclues de l'entraînement** ; 22 263 fiches BSD participent au jeu réconcilié.
- SportScore a fourni **54 671** enregistrements supplémentaires retenus au rapprochement mensuel.
- **0 date SportScore en échec** (confirmé par le workflow de réparation 2026 : aucune réexécution nécessaire).
- **251 journées SportScore ont atteint le plafond de 200 résultats**. Les tests `page` et `offset` avaient confirmé que leur réponse n'était pas paginée correctement. BSD permet de récupérer des matchs complémentaires, mais la couverture globale **n'est pas exhaustive**.
- L'audit indépendant final vérifie les scores FT, les dates terminées, l'intégrité AES-GCM, les 15 identifiants BSD réconciliés et l'unicité de la cohorte conservée. **76 934** matchs retenus et **9 identités ambiguës mises en quarantaine**. Aucun résultat postérieur au 24 octobre n'est ajouté.

### Provenance, sécurité et limites

- Les données individuelles ne sont **jamais enregistrées en clair** dans GitHub ; seuls les fichiers `.enc` chiffrés contiennent des matchs. Les rapports `research/2024_multisource_audit.json`, `research/2025_multisource_audit.json` et `research/2026_multisource_audit.json` sont des agrégats.
- La clé de déchiffrement est le secret Actions `ML_V2_HISTORY_KEY_B64`, non affiché dans les journaux.
- **Ne pas interpréter ces archives comme des preuves de pronostics émis avant coup d'envoi.** Elles servent à construire un backtest chronologique (ML V2), non encore réentraîné et validé sur le total des trois années.
- Aucun xG historique, horaire de coup d'envoi ou cote pré-match absent n'a été inventé. L'attribution SportScore reste à respecter en cas de diffusion publique.
- Cette opération n'a pas modifié le site de production, les messages Telegram, Supabase ou Neon.

### Exécutions sources

- [Collecte 2026 réussie](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40192238592)
- [Contrôle des journées 2026 — aucune en échec](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40192464479)
- [Audit 2026 initial](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40192709511), [contrôle des 15 fiches BSD](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40194282354) et [audit 2026 corrigé réussi](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40194702270)
- [Réparation des 19 journées de 2024](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40188754992)
- [Réparation des 10 journées de 2025](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189411683)
- [Audit révisé 2024](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189472398) et [audit révisé 2025](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189596063)
