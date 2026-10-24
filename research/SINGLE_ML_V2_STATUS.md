# Single exact-score ML V2 — integration audit (2026-10-24)
Scope: research only. Branch `research/single-ml-v2-20261024`. No production, grouped coupons, live publishing or Telegram changes.

## Implementation by improvement
1. Football provenance: **PARTIAL**. `single_ml_v2.load_matches` now accepts ONLY `sportId=1`; other/unknown sports excluded; duplicate ID conflicts fail closed. Old `cache/all_matches.json` does NOT preserve sportId. No 2024–2026 complete certified archive has been rebuilt. A strict test will fail empty on the old archive by design.
2. Recent 5/10 match form: **CODE IMPLEMENTED**. Prior-team rollups (scored, conceded, prior sample counts, rest days) appended to independent feature vector. Chronological performance not proven.
3. Real previous xG: **PARTIAL**. Pre-existing pre-match rolling xG proxy preserved, with numeric previous-xG signals plus missingness flag. Actual measured xG and source timestamps not available in standard archive. The current loader requires stronger xG provenance before deployment.
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
