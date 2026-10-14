# Mr XPRONOS — multisource prematch research, licensed sources only

## Current status

This is an ISOLATED research system on PR #96; it has no authority to modify BSD V2, GitHub Pages data.json, Supabase, bookmaker prices, or Telegram. The goal is to inventory as many daily fixtures as accessible through approved providers, choose the most useful trusted statistics source **for each individual game and each market family**, and evaluate improvements chronologically before any activation.

### Provider terms / legal boundary (2026-10-14)

- **OpenFootball / football.json**: explicitly public domain; permitted automated historical collection from its fixed GitHub raw JSON endpoints. https://github.com/openfootball/football.json
- **Football-Data.co.uk**: the provider expressly says its public downloads are **for private individuals and not commercial/AI data-training products using automated scrapers or bots**. Its automated collection was removed. Do not collect or reuse those data commercially without an appropriate license. https://football-data.co.uk/contact.php
- **Licensed CSV**: the PHP module retains a parser tested solely on *synthetic in-memory examples*; it does not download CSVs and is not connected to production. Only customer-owned or explicitly licensed datasets may be connected after rights verification.
- **BSD**: production provider and encrypted proprietary archive; remain private. Additional historical source use depends on contractual rights.
- **ESPN / SportScore / TheSportsDB / OpenLigaDB**: pre-existing public-source adapters. Their eligibility for commercial/model use must be assessed provider by provider, not inferred from publicly accessible endpoints.
- **API-Football**: existing quota-sensitive LIVE integration; in this experimental daily program it can be added via a licensed, pre-collected fixture snapshot without consuming LIVE quota.

Do not automatically crawl websites or bypass authentication/rate restrictions. Public access alone does **not** imply commercial reuse permission.

## Automated public-domain historical import

\`\`\`bash
php scripts/football_history_import.php --self-test
php scripts/football_history_import.php --source=openfootball --seasons=2024-25,2025-26 --max-files=12 --out=tmp/openfootball.jsonl
python scripts/football_history_shadow.py --input=tmp/openfootball.jsonl --output=tmp/historical-shadow.json --report=tmp/historical-quality.json
\`\`\`

The importer accepts only OpenFootball JSON from the allowlisted GitHub raw domain. Historical rows include league, match day, teams, verified final scores when available, provider ID, and source provenance. Some OpenFootball data include halftime results. It does not include reliable corners/cards/shot counts for all matches.

**Important**: One OpenFootball source does not independently verify itself. The canonical-history module requires results from **at least two separate, authorized providers** before marking a match multi-source confirmed. With only public-domain OpenFootball in the automated job, no rows are automatically approved for cross-source training. Previous exploratory Football-Data comparisons must not be reused as a commercial training dataset.

## Daily union and source priorities

\`\`\`bash
python -m pip install requests
python scripts/football_daily_multisource_shadow.py --day=2026-10-14 --max-http=12 --out=tmp/fixtures.json --route-out=tmp/source-selection.json --report=tmp/source-health.json
\`\`\`

The research collector reuses ESPN, SportScore, TheSportsDB and OpenLigaDB adapters with 12-HTTP-request cap and cache. Other providers can contribute from a local, authorized snapshot:

\`\`\`bash
python scripts/football_daily_multisource_shadow.py --day=2026-10-14 \
   --bsd-fixtures=/private/bsd-fixtures.json \
   --api-football-fixtures=/private/licensed-api-football-fixtures.json \
   --prematch-stats=/private/validated-provider-stats.json \
   --out=tmp/fixtures.json --route-out=tmp/source-selection.json \
   --report=tmp/source-health.json
\`\`\`

Every match retains discovery source, individual original provider IDs, UTC kickoff and competition labels, plus ambiguity and final-score disagreement flags. Strict home/away identity, league, and kickoff checks guard against joining different games or youth/women/reserve teams accidentally. Similar names are never blindly joined. Matches with no trustworthy data remain in the fixture inventory but not in eligible market analysis.

The per-market router selects among verified observations for GOALS, BTTS, TOTALS, CORNERS, and CARDS. A complete feature family requires stable original provider fixture ID, authorized use, sample >= 5 per team, complete finite values, dates of historical cutoff and snapshot collection *before both the time of analysis and kickoff*, plus no identity ambiguities. **Never substitute zero for missing statistics.** Provider reliability lists are provisional heuristics until measured on independent historical cases; the discovering provider may be used first when data quality is comparable, with per-family fallback.

JSON expected for \`--prematch-stats\`: \`{ "provider": { "source_fixture_id": { "provider_fixture_id": "source_fixture_id", "phase": "prematch", "observed_at": "2026-10-14T08:00:00Z", "history_until": "2026-10-13T23:00:00Z", "samples": {"home": 12, "away": 10}, "verified_identity": true, "license_ok": true, "families": { "goals": { "home_goals_for": 1.4, "home_goals_against": 1.0, "away_goals_for": 1.3, "away_goals_against": 1.2 } } } } }\`.

These example booleans require actual external verification by the ingest pipeline. A user-supplied true flag alone is not proof of commercial rights.

## Historic forms and experimental probability baseline

Authorized, cross-provider-confirmed match history can be added through \`--verified-history=...\` and \`--historical-feature-out=...\`. The strict history feature builder computes team goal averages, BTTS, totals, and, only for a separately authorized supplementary provider with enough observed records, corners, shots and cards. Each supplementary source remains separately attributable; a single provider's corner counts are not presented as independently validated.

\`\`\`bash
python scripts/football_prematch_probability_shadow.py \
  --routed=tmp/source-selection.json \
  --out=tmp/uncalibrated-probabilities.json \
  --report=tmp/chronological-quality.json
\`\`\`

This is an **uncalibrated Poisson baseline**, not approved recommendations. It generates no betting signals, no VIP selections, and no Telegram posts. It abstains unless goal statistics pass every timestamp and identity gate. Optional chronological diagnostics deliberately exclude results occurring on or after the target fixture day. A broad (>=200 scored games) authorized out-of-sample test and direct BSD V2 comparison on identical fixtures are still needed before using probabilities to choose markets.

## Automation and deployment

The experimental read-only GitHub workflow has a proposed daily schedule of **04:15 UTC**. GitHub Actions schedules run from the repository default branch; nothing is scheduled from this draft feature branch. It only uploads small source-health summaries, never original match datasets or plaintext BSD archives. Neither LIVE predictions nor existing daily BSD V2 generation is modified.

### Gates still open before production
1. Audit explicit rights, quotas, provider sports coverage and stable team/league identifiers.
2. Create verified daily pregame feature snapshots for each provider, prioritizing its own fixtures; use another source only when validated.
3. Measure source-level historic accuracy and missingness per competition and market.
4. Expand authorized matched history, test chronologically against BSD-only, calibrate probabilities, exclude future data.
5. Add default-disabled BSD production feature flag only after measurable benefit. Keep previously published picks immutable.
6. Separately fix the known Git rebase conflict in the BSD publishing workflow, without touching its selection logic in this PR.

Coverage is limited by rights and APIs. The software must never claim to analyze every match in every championship or publish unwarranted predicted probabilities.


## Mise à jour du 14 octobre 2026 — preuves sur plusieurs saisons

- OpenFootball Premier League 2023-24, 2024-25, 2025-26 et début 2026-27 : 1 158 scores finaux disponibles (353 scores connus sur 380 matchs de 2025-26; 45 sur 380 matchs planifiés 2026-27, à la date du contrôle). Les scores des rencontres futures ne sont jamais utilisés.
- Évaluation chronologique sur 318 matchs, période 19 octobre 2025 au 20 septembre 2026, sans données du jour. Brier 1X2 : Poisson 0,614427 contre prior de championnat 0,647941; log loss 1X2 : 1,025544 contre 1,069931. Le modèle BTTS (0,237480 contre 0,237210) et Over2.5 (0,248142 contre 0,240748) fait **moins bien** que le prior. La bonne réponse est de bloquer une promotion générale des marchés; seul le 1X2 paraît intéressant à examiner davantage.
- Aucun backtest apparié BSD V2 n'a encore été exécuté, donc aucune affirmation de supériorité de ce moteur face à BSD n'est permise. Probabilités non calibrées, source historique unique et usage recherche uniquement.

Commande du rapport historique (quatre petits téléchargements publics dans le workflow CI, aucun fichier source téléchargé n'est publié comme artifact) :

\`\`\`bash
python scripts/football_public_domain_backtest.py \
  --history-jsonl=tmp/four-season-history.jsonl \
  --report=tmp/four-season-holdout-quality.json
\`\`\`

### Résultats du test de collecte réellement effectué

Le 14 octobre 2026, un essai read-only a collecté 2 480 résultats historiques depuis 12 fichiers publics OpenFootball couvrant 2025-26 et 2026-27, puis découvert **284 rencontres du jour** via ESPN, SportScore, TheSportsDB et OpenLigaDB (7 appels de ces 4 APIs). À l'heure de l'essai, **0 nouveau match recevait des statistiques complètes** d'OpenFootball parce que les compétitions du jour étaient largement absentes de son périmètre. Des 284 rencontres : 83 n'avaient pas de championnat confirmé et beaucoup relevaient de championnats nationaux, compétitions de jeunes, ou coupes hors des six ligues historiques couvertes. Ce résultat n'est pas un défaut que l'on corrige en inventant les statistiques.

### Adaptateur historique privé BSD en recherche (sans clé ni archive dans la PR)

Un raccordement optionnel est disponible dans \`scripts/football_bsd_private_history.py\`. Il n'envoie **aucun** match d'archive aux fournisseurs externes, ne déchiffre pas l'archive dans la PR et ne touche pas le générateur \`bsd_v2_publish.py\`. Il produit uniquement des moyennes récentes par équipe, puis attribue les données à la rencontre du jour par deux mécanismes :

1. **Identifiant natif BSD** : le match est reconnu par son identifiant officiel de fixture du jour, ses IDs d'équipes et son coup d'envoi. Les noms et l'heure sont vérifiés; on conserve l'ID natif pour les statistiques et la provenance.
2. **Match découvert par une autre API** : recherche des deux équipes dans la même ligue, avec correspondances exactes normalisées et **un seul couple (league_id,team_id) possible par équipe**. Si plusieurs équipes ont un même nom, si les IDs divergent ou si le championnat manque, abandon. L'ID historique dérivé n'est jamais présenté comme un ID officiel BSD.

Les matchs BSD historiques doivent être terminés et avoir dépassé **quatre heures depuis leur coup d'envoi**, conformément au moteur BSD V2. Chaque équipe requiert au moins 5 matchs récents valides, avec âge maximal de 240 jours. Le routeur reste inactif pour corners/cartons absents. Aucun événement ou historique privé n'est exporté en artifact. Les sorties locales issues de l'archive sont protégées par permissions 0600 sous Linux.

Commande **uniquement en environnement local de confiance**, avec un historique BSD déjà restauré sur le système autorisé et des droits vérifiés :

\`\`\`bash
python scripts/football_daily_multisource_shadow.py \
  --snapshots=/private/daily-snapshots.json \
  --bsd-fixtures=/private/bsd-fixtures.json \
  --bsd-private-history-json=/private/all_matches_bsd.json \
  --authorize-bsd-private-internal-use \
  --analysis-at=2026-10-14T10:00:00Z \
  --day=2026-10-14 \
  --out=/private/day-fixtures.json \
  --route-out=/private/source-route.json \
  --report=/private/private-source-coverage.json
\`\`\`

Cet exemple impose les snapshots hors-ligne parce que \`--analysis-at\` sert seulement à rejouer une ancienne observation. Pour les API en direct, omettre cette option. L'autorisation explicite est requise : sans elle, le script refuse de lire le fichier privé. **Ne jamais attacher ce workflow aux événements pull_request avec les secrets BSD**. Les tests de CI utilisent uniquement de faux matchs locaux, aucun \`BSD_HISTORY_KEY\`.

### Étape de validation essentielle

Une fois la correspondance des équipes et les autorisations confirmées, il faudra confronter les probabilités BSD seules et les probabilités enrichies **sur exactement les mêmes fixtures**, dans chaque famille de marché, avec validation chronologique et calibrage séparé. Il faudra également résoudre la panne de commit concurrente du workflow BSD V2, distincte de ce travail. Aucun déploiement prédictif n'est activé par cette PR.

## Clarification fonctionnelle : BSD V2 reste l'unique moteur de calcul

La demande est **d'étendre les données d'entrée**, pas de créer une autre formule ou un autre moteur de sélection. Aucun changement des fonctions de calcul `bsd/bsd_v2_core.py`, `V2History`, `estimate_goals`, `predict_v2`, des règles de qualité, des calibrations ou des limites de publication.

- Les API existantes ESPN, SportScore, TheSportsDB, OpenLigaDB, ainsi que BSD quand il connaît le match, découvrent les rencontres et conservent leurs identifiants originaux.
- L'historique OpenFootball sous licence domaine public, constitué sur plusieurs saisons, est transformé en matchs terminés avec les champs BSD V2 : score, horaire, identifiants stables d'équipes et de compétition. Le jour historique seul est positionné de manière conservatrice à 23:59 UTC ; le moteur garde sa marge temporelle de validation de quatre heures.
- Les nouvelles rencontres externes deviennent des fixtures BSD V2 **compatibles en entrée** avec des identifiants internes calculés indépendamment des identifiants officiels BSD, dans un espace numérique distinct. Les fixtures déjà présents dans BSD ne sont pas doublonnés.
- Le module `scripts/football_external_bsd_v2_adapter.py` invoque **sans les modifier** les fonctions BSD V2 existantes. Le module H2H existant `bsd_h2h.local_h2h` résume les rencontres passées sur dix ans.
- Le module de calcul BSD V2 n'a pas actuellement de coefficient H2H explicite; ajouter une pondération H2H changerait la logique et serait contraire à l'instruction. Les confrontations historiques contribuent déjà à la forme des deux équipes lorsqu'elles appartiennent à leur historique, et le résumé H2H reste disponible en diagnostic.
- L'index historique externe est séparé pour ne pas modifier les estimations, les calibrations ou les sélections BSD publiées. Pour un déploiement, il faudra fournir aux nouveaux matchs les **modèles calibrés BSD existants**, les vérifications bookmaker et toutes les politiques de publication sans changer leurs règles.

L'adaptateur est testé sur une fixture provenant d'une API tierce et sur plusieurs saisons anciennes ; il vérifie aussi l'absence de données futures et de doublons. Le job journalier expérimental appelle désormais l'adaptateur BSD V2 existant, pas un second calculateur Poisson.

**Toujours non activé dans les pronostics publics.** Les données des championnats et des équipes absents de l'historique OpenFootball nécessitent d'autres fournisseurs historiques autorisés, avec correspondance vérifiée des équipes et compétitions. La seule découverte d'une rencontre ne suffit pas pour établir un H2H fiable.
