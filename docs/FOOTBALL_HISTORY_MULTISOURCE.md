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
