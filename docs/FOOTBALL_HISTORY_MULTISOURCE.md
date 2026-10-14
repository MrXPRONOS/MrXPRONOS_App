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
