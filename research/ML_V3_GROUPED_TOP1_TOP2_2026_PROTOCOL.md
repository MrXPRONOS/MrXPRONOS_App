# Preregistration — Hybrid V3 grouped-score Top 1 & Top 2 evaluated in parallel

Date: 2026-11-02. **Frozen before any new annual evaluation run**. Research-only branch `research/single-ml-v2-20261024`. Site, Telegram, production and `main` are unchanged.

## Hypothesis and method
For every calendar day, the original Hybrid V3 model ranks all eligible matches by the probability of its predicted modal exact score, descending, tie-broken by stable match ID. **Top 1 = the first prediction; Top 2 = those same first two predictions**, before seeing any actual scores. Both are evaluated side-by-side in **one monthly historical replay**, sharing the trained model and identical candidate fixture universe; this avoids rerunning expensive training for each Top K. Top 3, 5, 10, 20 also evaluated using exactly the same code for nested consistency checks.

For each predicted score, use the exact same predefined disjoint **3-score proxy market** mapping already frozen in `ml_v3_grouped_scores.py` and `ml_v3_grouped_top3.py`:
- H_LOW = [1:0, 2:0, 2:1]
- H_HIGH = [3:0, 3:1, 3:2]
- A_LOW = [0:1, 0:2, 1:2]
- A_HIGH = [0:3, 1:3, 2:3]
- DRAW_LOW = [0:0, 1:1, 2:2]

These **are experimental bookmaker-style proxy groups, not verified 1xBet markets**. Unmapped scores abstain and count within the original K denominator. Never choose a group based on the actual result.

## Calendar / metrics
Primary: 2026-01-01 through 2026-09-30 inclusive, **273 days**; 273 Top-1 selection slots and 546 Top-2 selection slots. Supplemental: 2026-10-01 to 2026-10-24 inclusive, **24 days**, never represented as a complete October or 2026 year. Historical source cutoff remains 2026-10-24.

For each K in (1,2,3,5,10,20): exact-score hits and win rate per original K slots, grouped hits and rate per original K slots and separately per covered slot, days >=1 grouped hit, days >=2 group hits where K permits, days >=3 where K permits, abstentions and covered slots, breakdown by group, 1X2 ceiling sanity check and theoretical break-even uniform decimal odds (NOT actual market ROI). Compare Top 1 vs Top 2 vs Top 3 vs Top 5 on **both per-selection precision and daily at-least-one probability**. A grouped market covering three scores mechanically increases the hit rate relative to exact-score alone; never imply model accuracy or betting profitability is improved from this arithmetic fact.

Top-1 and Top-2 MUST be computed simultaneously after a single match replay per month. All group definitions, model weights, and ranking rules fixed before results. Historical chronological replay is not externally archived real-time prematch proof. No odds, no verified bookmaker offerings, no ROI, no production deployment.
