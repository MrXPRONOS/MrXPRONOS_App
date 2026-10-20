# Research upgrade audit, 2026-10-20

This branch remains experimental. No production, grouped scores, Telegram, bookmaker odds or encrypted ledger changes.

1. Score bias: IMPLEMENTED diagnostics of score-by-score hit rates, predicted vs observed score frequencies. Model bias not forcibly corrected.
2. Top-three: IMPLEMENTED deterministic label-blind research ranking, per-day basket metrics and coverage sweeps. Historical daily grouping is not a pre-kickoff simultaneous snapshot.
3. Reliability learner: PARTIAL. Reliability diagrams and probability-bin ECE plus fixed ranking; no independent fitted model or blind holdout yet.
4. Expected goals: PARTIAL. Existing recent-match and venue sample counts retained for quality ranking, but no newly validated xG or injury source; BSD V2 unchanged.
5. Score distributions: IMPLEMENTED experimental fixed-parameter Dixon-Coles, bivariate Poisson and negative binomial, paired over exactly the same matches. Not auto-selected.
6. Context: PARTIAL. Strict as-of timestamp validation for optional verified injury/rest counts; context advisory only, not mixed into scores.
7. Conditional Double Chance: IMPLEMENTED explicit non-production conditional variant and paired deltas. Thresholds remain exploratory.
8. Top-three baskets: IMPLEMENTED research basket hit rates, Wilson intervals and selectable coverage. Prospective simultaneous-issue validation still needed.

2025/2026 were examined in previous development. Any further result is exploratory, NOT unbiased test performance. Top 1 != top 3 != group-bet success != financial returns. Do not claim 33% is attainable yet.

## Completion upgrade (2024-frozen)
- 1-1 bias correction: eight outcome-specific probability-mass weights are fitted on Jan-Jun 2024 and selected on Jul-Aug 2024 via full-score log loss. Renormalizes the full score matrix; never forces another score. Zero blend is a VALID no-gain result.
- Goal estimates: 2024-fitted offset Poisson regression learns home/away adjustments using baseline BSD xG proxies, venue sample strength, verified rest days and prior *measured* (not estimated) BSD xG. Model strength picked on May-Jun 2024.
- Independent reliability: logistic success-vs-failure meta-model trained Sept-Oct 2024 and probability blended on Nov-Dec 2024 using Brier. No labels after 2024 used.
- Context: BSD v2 /events/{id}/lineups/ used before kick-off with a bounded 6-request budget and timestamps; previous settled matches' /stats/ xG enriched with a 12-request cap; model may use measured xG from prior games only. Missing information stays missing, and no 2025/2026 context is backfilled from post-match lineups.
- Old engine score remains immutable. Advanced branch writes a distinct experimental ablation for **new** ledger records only, and advanced fields are evaluated in research historical reports.
- This completes implementation of the training and capture pipelines, NOT proof that the new model beats baseline. Historic 2025/2026 scores are exploratory and historic 2024 lineup coverage is limited.
