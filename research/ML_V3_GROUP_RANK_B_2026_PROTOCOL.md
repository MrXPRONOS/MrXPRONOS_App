# Predeclared experiment B — rank Hybrid V3 predictions by probability of the fixed correct-score group

Date frozen: 2026-11-03. Research only on `research/single-ml-v2-20261024`. Do not modify production/main, site, cron, Telegram, or send actual bets.

## One and only ranking variable change
For each eligible fixture, the existing Hybride V3 generates a normalized (11×11) exact-score probability grid **before its full-time result**. Its original predicted score is the modal cell: `s* = argmax(grid)`, with original modal confidence `p*=grid[s*]`.
Map `s*` into exactly the same fixed disjoint 3-score proxy group used by previous studies:
- H_LOW [1:0,2:0,2:1]; H_HIGH [3:0,3:1,3:2]
- A_LOW [0:1,0:2,1:2]; A_HIGH [0:3,1:3,2:3]
- DRAW_LOW [0:0,1:1,2:2].

**A baseline**: daily sort by decreasing `p*`; ties by stable fixture ID.
**B candidate**: daily sort by decreasing `sum(grid[score] for score in fixed group of s*)`; tie by decreasing `p*`, then stable fixture ID. An out-of-group predicted score is an abstention, ranked last (zero/absent group mass); abstentions stay counted in original K slots. **B does not change the modal score or select a new group**. Only daily fixture order can change.
One fixture per ranked slot; the exact score and group winner outcomes are evaluated after daily selection is locked. Grid export must omit actual outcomes entirely and must include timestamp/provenance and direct modal/group probabilities. Joins against independently generated frozen prediction CSV must be exact on (date,fixture ID,modal prediction) and check model provenance. No future-dependent features or group selection from the result.

## Frozen evaluation
One historical replay per month, with a paired A/B evaluation using the exact same candidate fixture universe and saved prematch grids. Jan–Sep 2026 = **273 full days** primary; Oct 1–24 2026 = **24 days** secondary. No full-year 2026 claim. All K=1,2,3,5 assessed daily, including exactly 273K or 24K original selection slots.
Metrics: exact simple hit count, fixed group hit count, rate on full K slots, daily >=1 exact/group successes, daily >=2 and >=3 group successes, mapping coverage, group frequencies and per-group results, A/B selection overlap, absolute percentage-point difference B−A with paired day-block bootstrap intervals, and hypothetical flat-uniform break-even decimal odds. No bookmaker historical quotes or EV/ROI proof. Report any negative B−A as such.

These cohorts were previously examined for other model selection studies; 2026 backtests are **exploratory** rather than independent confirmation. A genuinely untouched future chronological validation is required before deployment/claims of reliable improvement. This test is specifically **B versus A**, no retrospective feature tuning or calibrating a selector to the same target outcomes.
