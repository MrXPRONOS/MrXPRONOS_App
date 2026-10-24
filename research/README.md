# Exact-score research / 2026 backtest

This is an isolated research branch; the public site, production ML and scheduled jobs are untouched.

## Scope and method
- UTC match days 2026-01-01 through 2026-10-19. Data before 2026 is used only for initial history.
- All forecasts within the same UTC date are issued before any scores for that day are learned.
- Raw finished scores are deduplicated by game ID and sorted chronologically.
- Feature rates are season-independent exponentially time-decayed (240-day half life), league and team stratified, shrunk to fixed priors.
- Both Dixon-Coles and bivariate Poisson parameters refit only monthly from past outcomes.
- ML retrains monthly with prior-date features, not random train/test split.
- xG model uses only earlier games' real xG; absent historical xG => excluded, NOT fabricated.
- Market model uses verified previous-day 1X2 odds and its normalized marginal match result probabilities. Cotes of exact scores need a full valid set to be used directly; the pipeline does not fabricate absent odds.
- Monte Carlo explicitly models common match tempo; it is a simulation method, not evidence of an independent superior estimator.
- Random seeds fixed; Bayesian Gamma posterior predictive via deterministic seeded Monte Carlo.

## Evaluation
Number of evaluated matches, exact-hit percentage for top score, mean top-score confidence, calibration gap, log loss (proper scoring rule) and available realized flat-stake ROI. Different model coverage must be compared fairly and data quality must be audited. No ROI when score-odds were not recorded prior to kickoff.

## Run
```bash
pip install numpy scipy scikit-learn
python research/exact_scores_2026.py --self-test-only
python research/exact_scores_2026.py --source cache/all_matches.json --start 2026-01-01 --end 2026-10-19
```
View GitHub Actions workflow **Exact Score 2026 - Research Backtest** and download artifact with `summary.json`, `all_predictions.csv`, log.

## Limitations
This is a full runnable RESEARCH implementation of the 8 model families, not evidence that each has externally validated predictive performance. Historical xG and odds are not present in the documented `allmatches.py` extraction. Correlations, priors, decay and hyperparameters are defaults, NOT exhaustively tuned. No guarantees of score exactness or profit. These results should not be merged into the production site before independent audit.

## 2026 historical repairs and provisional xG
- The refresh utility retries missing UTC dates one at a time. API failures are recorded, not silently omitted. Routine GitHub Actions uses `--max-days 15` to avoid runaway requests; for exhaustive recovery, run locally using `--max-days 0`.
- The optional xG bridge requests *read-only* historical `live_stats_sources` snapshots. It accepts only snapshots observed at minute 90 or later, valid non-negative xG, matching both normalized teams on the same calendar day with kickoff within 90 minutes. Source quality is tagged `supabase_late_match_provisional_90plus`.
- A late snapshot is not a certified final xG and does not necessarily include added-time chances. Interpret any xG-subset backtest as exploratory, not a full official xG benchmark.
- Supabase also contains recorded double-chance 1X/X2 odds; those are not a correct-score odds distribution and are not reused as though they were one.
- Check `refresh_audit.json` and `xg_audit.json` for exact coverage, failures and missing data; `summary.json` reports the last date actually backtested.
