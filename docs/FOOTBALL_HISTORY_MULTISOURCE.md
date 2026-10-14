# Multisource historical research – isolated shadow mode

BSD V2 remains authoritative for daily predictions. Its 2024–2026 encrypted archive stays private. Nothing in this feature runs from existing production workflows, writes data.json, updates private BSD history, changes model thresholds, calls Supabase, or sends Telegram notifications.

## Run on a local machine
1. PHP syntax and parser tests: php -l scripts/football_history_import.php ; php scripts/football_history_import.php --self-test
2. Historical collection: php scripts/football_history_import.php --source=both --seasons=2024-25,2025-26 --max-files=24 --out=tmp/history-raw.jsonl
3. Merge and conflict report: python scripts/football_history_shadow.py --input=tmp/history-raw.jsonl --output=tmp/history-shadow.json --report=tmp/history-quality.json
4. Tests: python -m unittest discover -s tests -p test_football_history_shadow.py -v

The GitHub Actions workflow can be launched manually on the feature branch for a capped historical probe. Pull requests only run offline syntax and parser tests.

## Source policy
- BSD is the reference match/history provider; never disclose its private archive.
- OpenFootball provides freely licensed historical results; not necessarily real-time fixtures.
- Football-Data.co.uk provides historical CSVs. Respect terms before redistributing original data.
- ESPN, SportScore, TheSportsDB and OpenLigaDB already serve the daily supplementary collection; they are NOT automatically BSD model-training inputs.
- API-Football is currently LIVE-oriented and has plan limitations; not yet part of daily training.

## Trust and safety
Historical files use fixed allowlisted endpoints, no login/captcha bypass or undocumented crawling, a maximum of 120 files from PHP and stricter limit of 48 in Actions, plus delay between requests. Raw data is never uploaded as an artifact.
Merge uses normalized exact date, league, home and away names. Matches with differing scores are quarantined. Exact normalization is provisional and can still merge homonyms; therefore ALL rows are marked for_training=false, and the quality report declares publication_enabled=false. No prediction performance claims are made from this dataset.

## Remaining integration stages
1. Manually verify source accessibility, licensing, historical CSV and JSON schema, and coverage statistics.
2. Build stable team and competition ID mappings, plus kickoff, gender, reserve-team and alias checks.
3. Add capped adapters for ESPN, SportScore, TheSportsDB, OpenLigaDB, API-Football and BSD historical features with provenance and quotas.
4. Run chronological out-of-sample shadow backtests against the existing BSD-only baseline. Never use future outcomes in features.
5. Only if performance measurably improves and after approval, enable a feature-flagged daily contribution to model calculations.
6. Resolve production race causing git rebase conflicts independently of this experimental work.

Do not commit raw licensed datasets, secrets, plaintext BSD archive, or generated predictions.

## Production-free daily multisource audit

Command:

```bash
python -m pip install requests
python scripts/football_daily_multisource_shadow.py --day=2026-10-14 --max-http=12 --out=tmp/day-shadow.json --report=tmp/day-health.json
```

The daily collector reuses the original ESPN, SportScore, TheSportsDB and OpenLigaDB adapters. BSD can be supplied with `--bsd-fixtures=<private-local-fixtures.json>` to compare with BSD's authoritative fixture IDs. An existing API-Football `/fixtures` response can be supplied using `--api-football-fixtures=<local-json>`, **without any additional API-Football request**, to preserve the separate LIVE key's quota. Historical OpenFootball and Football-Data are used for *history*, not a live slate.

Verified at 2026-10-14 03:00 UTC: 88 ESPN, 200 SportScore, 3 TheSportsDB and 0 OpenLigaDB events; 285 distinct fixtures, 4 cross-provider corroborations and 7 HTTP calls. This is only a day's coverage sample. A zero provider count must not be presented as definitive outage without inspecting provider health and coverage.

## Historical coverage validation

The real test of `2024-25` Premier League returned 380 finished matches from **each** of OpenFootball and Football-Data (760 source rows). Initial strict string comparison had zero joins. Removing only a terminal `FC` designator increased reliable-name joins to **72 fixture agreements**; no conflicting final scores were observed among these 72. Other fixtures remain separate until a trustworthy team-ID/alias mapping is validated. This is an intersection of sources, **not** 760 different football matches.

Prepare manual review suggestions for the remaining aliases:

```bash
python scripts/football_alias_candidates.py --input=tmp/history-raw.jsonl --out=tmp/aliases-to-review.json
```

Review proposals independently: matching on the same final score and date does *not* prove fixture identity. Alias proposals have `approved=false` and are never automatically promoted to the trusted archive.

## Leakage-safe research features

```bash
python scripts/football_history_features.py --history=tmp/history-shadow.json --fixtures=tmp/day-shadow.json --out=tmp/feature-candidates.json --report=tmp/feature-coverage.json
```

Creates descriptive home/away form values and historical BTTS/Over2.5 rates **only** when each target team has at least five prior confirmed matches in the same verified competition. These rates summarize earlier results; they are not calibrated probabilities, guaranteed outcomes or market odds. Events on and after the target match's UTC day are rejected to avoid hindsight and leakage. No production model imports this file yet.

### Rollout gates (do not skip)
1. Audit licenses, provider budgets, team and competition identifiers, season overlaps and accuracy of scores.
2. Expand independently verified history and date-stamped features; quarantine ambiguous aliases and conflicting source facts.
3. Add a chronological baseline-vs-multisource shadow backtest on the same markets with proper probability calibration and out-of-sample separation. Enforce minimum sample size.
4. Integrate only demonstrated incremental signal into BSD V2 behind a **default-off** feature flag, keeping published fixture IDs and picks stable.
5. Repair the independent GitHub workflow publication conflict before scheduling additional writers. This research workflow has contents:read and no Telegram, Supabase or production write privileges.
