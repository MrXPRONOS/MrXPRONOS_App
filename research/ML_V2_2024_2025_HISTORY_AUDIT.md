# Mr XPRONOS — Historique football chiffré 2024 + 2025

Actualisé le 25 octobre 2026. **Résultats réels audités depuis GitHub Actions.**

## Opérations réellement réalisées

| Élément | 2024 | 2025 |
| --- | ---: | ---: |
| Calendrier traité | 1 jan. – 31 déc. | 1 jan. – 31 déc. |
| Archives mensuelles BSD + SportScore AES-256-GCM | 12 / 12 | 12 / 12 |
| Matchs BSD récupérés | 20 239 | 20 251 |
| Matchs SportScore initiaux | 63 186 | 65 267 |
| Anciennes journées SportScore en échec | 19 | 10 |
| Journées récupérées après rattrapage | **19 / 19** | **10 / 10** |
| Enregistrements supplémentaires lors du rattrapage | 3 530 | 1 991 |
| Matchs OpenFootball de base (2024 uniquement) | 5 789 | — |
| Doublons exacts même score éliminés | 1 393 | 58 |
| Conflits de résultats mis en quarantaine | 10 | 0 |
| **Matchs distincts retenus par la règle conservatrice** | **91 331** | **87 451** |

**Total de la réunion annuelle actuelle : 178 782 enregistrements datés** (91 331 + 87 451). « Distinct » signifie identité `date + noms normalisés domicile + extérieur`. **La même rencontre utilisant deux noms différents selon les fournisseurs peut encore subsister en double** ; ce nombre n'est pas une estimation certaine de rencontres mondialement uniques.

## Limitations de source documentées

- Les limites SportScore **200 événements par jour** demeurent : 278 dates initiales à ce plafond en 2024 et 281 en 2025. Les vérifications séparées `page=2` et `offset=200` ont renvoyé les **mêmes événements**, donc nous n'avons pas fabriqué de deuxième page ni qualifié les réponses SportScore d'exhaustives.
- Les 19 erreurs réseau/API de 2024 et les 10 de 2025 ont, elles, réellement été récupérées et chiffrées. Certains jours rattrapés sont eux-mêmes au plafond SportScore de 200.
- BSD est interrogée avec pagination complète documentée (`limit=200`, `offset`), mois par mois. SportScore apporte une couverture supplémentaire ; sa couverture globale peut rester incomplète.
- Les dix identités exactes de 2024 pour lesquelles les scores sources diffèrent ont été exclues de la version ML réunifiée.
- Les sources sont conservées séparément avec leurs champs de provenance ; aucune valeur xG ni cote pré-match manquante n'a été inventée.
- Il s'agit d'un jeu de **recherche rétrospective** ; il ne constitue pas une preuve de pronostics effectivement produits avant un match ni une mesure de rentabilité. Le backtest ML V2 sur ce nouveau total reste à réaliser.
- La couverture dépend des fournisseurs ; les chiffres ne prouvent pas que **tous les matchs de football du monde** sont disponibles. Pour toute publication publique de données SportScore, respecter leur attribution.

## Archives privées GitHub

Les archives contenant les matchs sont exclusivement chiffrées avec `ML_V2_HISTORY_KEY_B64` :

- `research/encrypted_football/openfootball/2024.enc` (archive d'origine inchangée)
- `research/encrypted_football/bsd_sportscore/2024/01.enc` à `12.enc`
- `research/encrypted_football/bsd_sportscore/2024_repair.enc`
- `research/encrypted_football/bsd_sportscore/2025/01.enc` à `12.enc`
- `research/encrypted_football/bsd_sportscore/2025_repair.enc`

Les rapports **agrégés sans scores individuels** sont dans `research/2024_multisource_audit.json` et `research/2025_multisource_audit.json`.

Les 2 versions réunifiées se reconstituent temporairement avec `PYTHONPATH=.:research python research/single_ml_v2_2024_union.py --year 2024|2025 --export --output /tmp/...`. Les exports en clair doivent rester dans un répertoire temporaire privé et être supprimés avant la fin du job.

## Exécutions GitHub Actions vérifiées

- Collecte 2025 : [workflow 40188892482](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40188892482) — SUCCESS.
- Réparation 2024 : [workflow 40188754992](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40188754992) — SUCCESS.
- Réparation 2025 : [workflow 40189411683](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189411683) — SUCCESS.
- Audit final après réparation 2024 : [workflow 40189472398](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189472398) — SUCCESS.
- Audit final après réparation 2025 : [workflow 40189596063](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/40189596063) — SUCCESS.

**Aucune modification de la production, du site, de Telegram, de Supabase ou de Neon dans cette opération.**
