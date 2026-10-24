# Single exact-score ML V2 — integration audit (2026-10-24)
Scope: research only. Branch `research/single-ml-v2-20261024`. No production, grouped coupons, live publishing or Telegram changes.

## Implementation by improvement
1. Football provenance: **PIPELINE CODE COMPLETE; BACKFILL NOT COMPLETE**. New `single_ml_v2_data.py` reconstructs from SportData, checks `sportId=1` at ORIGINAL source, refuses unknown sport/invalid fixture ID, audits every UTC day, resumes from verified daily checkpoints, rejects conflicting fixture IDs, and publishes ONLY when the entire requested interval is covered. Old `cache/all_matches.json` lacks sportId and remains excluded. Existing 2024–2026 full archive is NOT yet backfilled: provider API credentials, quota and runtime are needed. Optional manual 3-day smoke CI created.
2. Recent 5/10 match form: **CODE IMPLEMENTED**. Prior-team rollups (scored, conceded, prior sample counts, rest days) appended to independent feature vector. Chronological performance not proven.
3. Real previous xG: **PIPELINE CODE COMPLETE; COVERAGE/VERIFICATION PARTIAL**. `single_ml_v2_xg.py` consumes recorded `api_original` measured expected_goals from Supabase `live_stats_sources` captured at minutes 90–135, validates exact fixture identity (name/date/kickoff +/-90min), rejects ambiguous matches, records provider, capture time and provisional 90+ quality; only uses snapshots as-of their real availability. `single_ml_v2.py` accepts ONLY specifically tagged timestamped observations and releases them into historical features the next UTC day AFTER the snapshot was recorded; otherwise marks missing. This is TRUE observed late-game xG but **not provider-certified final xG**; cannot claim full official xG coverage. Supabase was verified to contain 439 90+ `api_original` rows before final football fixture matching, not 439 guaranteed complete football games.
4. ML + Dixon-Coles: **CODE IMPLEMENTED**. New `ml_hybrid_grid` blends 65% ML Poisson and 35% DC on same ML predicted goal rates. Fixed weights are exploratory, not optimized or tested for superiority.
5. Direct classifier: **PARTIAL**. Separate `single_ml_v2_experiments.py` implements `train_direct_score` and `direct_grid`, including rare-score probability preservation. Not wired into year-round walk-forward runner or evaluated prospectively.
6. Opponent strength: **CODE IMPLEMENTED**. Each opponent's prior 10 goal differences are frozen before historical match ingestion and appended to the target team's rollups. Identity harmonization across multiple competitions remains a limitation.
7. CatBoost and LightGBM: **PARTIAL**. Optional constructors and paired-fitting API in `single_ml_v2_candidates.py`. They are not installed by the CI workflow or run on certified football history. Neither is declared the winner.
8. Retraining/tuning: **PARTIAL**. Baseline ML receives configurable predeclared hyperparameters and 7/14/30/60 day retrain intervals. No nested time-series search has been performed. This is *not* automated tuning.
9. Selection/abstention: **PARTIAL**. `train_reliability`, `selection_features` and `select_forecast` implemented in separate experimental module. Without a trained independently validated reliability model it ABSTAINS. No verified coverage/accuracy gain.
10. Chronological validation: **PARTIAL**. Original daywise no-leakage training preserved; unit tests added for sportId, features, normalization and abstention; isolated workflow added. No successful remote CI run or prospective immutable evaluation observed when writing this audit.

## Validation contract before marking fully DONE
- Obtain authorized football-only archive with `sportId=1` on each target and historical observation; audit missing dates and conflicts.
- Chronological partitions with untouchable final test, plus inner rolling validation for hyperparameters.
- Each ablation must run on precisely matched matches and dates. Report Top-1 hit rate, count, bootstrapped intervals, multiclass log-loss, score-wise frequency, calibration and concentration on 1-1.
- Compare selection coverage as well as rate, with no hindsight thresholds. With absent pre-match score odds, ROI is NOT EVALUABLE.
- Independent pre-kickoff, immutable snapshots and live settlements are needed before production.
- No promise of improving 11.23%; this prior result is only 21/187 in a retrospective one-day football-only check, not a reliable long-term baseline.

## October 24 follow-up
- Point 1: programmatic ingestion/validation COMPLETE. Full 2024–2026 backfill NOT performed or certified; dataset incomplete. No production writes.
- Point 3: historical provisional observed xG ingestion, matching, origin, timestamp and strict as-of state COMPLETE in code. Not complete in the sense of official final xG or complete coverage; additional provider data are required.
- Unit tests added (`test_single_ml_v2_data.py`) and CI workflow updated; **no green CI run observed yet**, so do not call tested/verified in production.

## Point 1 — finalized end-to-end implementation
- Durable PRIVATE Supabase Storage bucket `mrxpronos-mlv2-football-history` created and checked for public=false.
- `single_ml_v2_cloud.py` resumes by listing per-day SHA-verifiable gzip checkpoints, filters original API source by `sportId=1`, rejects source conflicts, fails closed on contaminated days, persists each day before continuing, and verifies full requested-date coverage.
- On completion publishes `certified/football_history_latest.json.gz` plus SHA-256 manifest LAST. Consumers verify compressed and uncompressed hashes and sport provenance before reading. Legacy mixed cache is never imported.
- `.github/workflows/research-certified-football-backfill.yml` implements manually dispatched incremental backfill with Supabase and SportData GitHub secrets. Repeated dispatch resumes existing progress; optional post-completion ML backtest consumes only the certified resulting archive.
- **Deployment state:** code and private bucket implemented. No confirmed full 2024–present backfill has run, and workflow in research branch is not yet enabled on default branch. Operational backfill, tests, and independent data-audit remain pending. Do not claim a complete populated dataset or a new model accuracy.
