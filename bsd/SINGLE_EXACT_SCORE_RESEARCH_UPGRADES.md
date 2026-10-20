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
