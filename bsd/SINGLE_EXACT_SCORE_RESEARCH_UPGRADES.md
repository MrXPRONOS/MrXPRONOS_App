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

## Encrypted xG persistence
A separate `bsd/single_exact_score_xg_history.enc.json` saves only BSD *measured* home/away xG from finished games observed >=4h after kickoff. Event ID, team IDs, dates and UTC captures must match before applying. A newly captured xG value is available only to *future* feature calculations; no prior forecast is rewritten. The prospective workflow commits this encrypted file alongside (but separately from) the existing encrypted score ledger. No public xG records are uploaded. BSD may provide no measured xG for some competitions; that is not fabricated.

## Logic audit fixes — 2026-10-20
1. **As-of measured xG**: every accepted prior-match xG must carry an observed UTC timestamp <= the fixture being predicted. Cache restores the original capture time. No historical post-match xG can leak backward.
2. **Capture clock**: the UTC clock is re-read immediately before issuing each ONE-score prediction; no stale run-start clock is accepted.
3. **Training periods**: goal train 2024 Jan-Jun, validation Jul-Aug; score-mass train Jan-Aug, validation Sep-Oct; reliability train Nov, validation Dec. Minimum training counts are enforced by full historical CI. Validation may still correctly decline a modification.
4. **Identity correction**: model strength=0 reproduces the exact reference Poisson+Under2.5 matrix, including the same home scaling and rate clipping.
5. **Frozen pre-match Top3**: separate encrypted `bsd/single_exact_score_top3.enc.json`, exactly one score each across three distinct fixtures, snapshot integrity hash, immutable selection, three-match settlement, no retrospective score switching. Selection is restricted to records whose real capture time and rank preceded all fixtures. Importantly, no daily automation is claimed on this experimental branch.
6. **Rank independence**: base, under and advanced scores are highly related; agreement is counted at most once using independent DC advisory. Ranking requires no outcome labels.
7. **Injuries/lineups**: only verified timestamped BSD unavailable-player counts from first-seen prematch snapshots may train the experimental adjustment; must pass chronological validation on at least 240 settled observations. No adjustment until it actually passes.
8. **Reproducibility**: learned coefficient and selection-rule cryptographic fingerprints accompany each *new* prospective forecast and first-seen Top3.
9. **CI**: isolated unit tests, chronological smoke check and full history assertions. Encrypted archives and main production remain untouched.

**Scope**: The last three elements requiring live BSD lineups, live measured xG and the scheduled daily prospective capture are conditional on external data/service configuration; do not mark them as production-complete until an actual successful prospective run and enough settled captures exist. A full historical backtest cannot verify these live requirements.

## Automated pre-match data monitoring
The isolated daily workflow reports verified pre-match lineup coverage, number of settled observations eligible for absence training and validation losses. A missing or weak provider signal never becomes a made-up adjustment; the training gate remains inactive until the independent prospective sample passes. The historical baseline stays separate.
