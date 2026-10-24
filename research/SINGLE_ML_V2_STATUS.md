# Single exact-score ML V2 — integration audit (2026-10-24)
Scope: research only. Branch `research/single-ml-v2-20261024`. No production, grouped coupons, live publishing or Telegram changes.

## Implementation by improvement
1. Football provenance: **PIPELINE CODE COMPLETE; BACKFILL NOT COMPLETE**. New `single_ml_v2_data.py` reconstructs from SportData, checks `sportId=1` at ORIGINAL source, refuses unknown sport/invalid fixture ID, audits every UTC day, resumes from verified daily checkpoints, rejects conflicting fixture IDs, and publishes ONLY when the entire requested interval is covered. Old `cache/all_matches.json` lacks sportId and remains excluded. Existing 2024–2026 full archive is NOT yet backfilled: provider API credentials, quota and runtime are needed. Optional manual 3-day smoke CI created.
2. Recent 5/10 match form: **IMPLEMENTATION COMPLETE IN RESEARCH CODE, TESTS ADDED**. New `single_ml_v2_form.py` calculates full prior 5/10 rolling form both overall and specific to home/away for BOTH teams. Each window has sample count, goals for/against, goal difference, PPG, W/D/L rates, clean sheet, failed-to-score, both-score, over-2.5, days since match and explicit missing flag. 112 named form features; 130 total model features. `FormState` stores league-scoped compact 10-game histories and commits entire UTC days atomically AFTER forecasting; rejects same-day/future leakage and duplicates. Feature schema documented in backtest report; train features validated. No real-data full backtest or prospective gain measured.
3. Measured prior xG: **FULL RESEARCH CODE INTEGRATION, PROVIDER AVAILABILITY NOT VALIDATED**. The old Supabase bridge was removed and replaced by `single_ml_v2_xg.py` using SportsAPIPro V2 football match statistics. It verifies V1/V2 ID, both team names, and kickoff before accepting explicit full-match measured xG. It records the TRUE first-seen timestamp, never backdates xG to the historical match. Each measured/negative checkpoint is AES-256-GCM encrypted in Git, negative observations expire after a 14-day retry cooldown. The ML V2 uses only time-eligible prior observations. The workflow uses explicit xG request budgets and temporary decrypted Git-only history. Data missing/unsupported are never fabricated. Real-world source match ID compatibility, source coverage, and green tests are pending.

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

## Feature #2 completion — 2026-10-24
- Model wiring complete: 5/10 overall and 5/10 home-vs-away venue performance for each team; real earlier finished games only, missingness and finite vector guards.
- Existing ML regressor is trained on all 130 named features and inference uses identical schema; report includes feature names and source-support sample counts.
- Unit tests `research/test_single_ml_v2_form.py` cover all edge cases and delayed same-day result ingestion; GitHub Actions research workflow updated. **Actual passing execution still needs verification**.
- No Supabase or Neon usage in the form pipeline; previous storage decisions respected.
- Training history still depends on completion of encrypted GitHub-only football archive and the secret to decrypt it. Numerical hit-rate improvement not established.

## Improvement #3 — final code integration 2026-10-24
- **Source:** SportsAPIPro V2 /v2/football/api/match/{matchId}/statistics (availability varies by league); provider documents measured xG but does not guarantee all fixtures.
- **Data security:** all persisted records are encrypted per match under `research/encrypted_football/xg/matches/XX/<HMAC>.enc`; HMAC filenames hide fixture IDs; AES-256-GCM key remains GitHub Actions secret `ML_V2_HISTORY_KEY_B64`. No plaintext or API credentials in Git.
- **Source checks:** require football-certified fixture from independently encrypted Git archive, matching numeric match ID, both team identities and kickoff within 90 min. Never infer one API version's ID mapping from ambiguous data. Missing/contradictory data are not accepted.
- **As-of:** xG capture timestamp is the time the source was ACTUALLY queried (not retroactively assigned to kickoff). Existing `FormState` activates the observation only from the next UTC day after its capture.
- **Quota & retry:** independent `xg_matches_per_run` and `xg_requests_per_run` workflow parameters, with a provider quota hard ceiling and negative results encrypted with 14-day retry cooldown.
- **ML integration:** `single_ml_v2_prepare_xg.py` joins authenticated xG only to matching certified football archive for research training/inference. xG fields are ignored when not observed at the time.
- **Prior Supabase xG collectors:** `single_ml_v2_xg.py` no longer queries Supabase or Neon; legacy `enrich_late_xg.py` remains in older experimental research branch but is NOT invoked by this Git-only workflow. Do not use it.
- **Tests:** `test_single_ml_v2_xg_git.py` checks zero-valued xG, unsupported period, identity conflict, ciphertext and ML loader. CI configured with cryptography. No green Actions run or real V2 match-identity confirmation observed yet; cannot claim actual xG coverage or a higher prediction hit rate.
