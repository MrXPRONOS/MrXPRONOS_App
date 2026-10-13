# Football data providers — Mr XPRONOS

## Quality / reliability order

| Provider | Quality | Reliability | Cost mode | Primary role |
|---|---:|---:|---|---|
| BSD | 96 | 95 | quota | bookmaker odds, final fallback, BSD model compatibility |
| ESPN | 94 | 89 | free public endpoints | rich match data, live events, summary validation |
| SportScore | 86 | 84 | free + attribution | live scores, match detail, lineups, timeline, stats |
| TheSportsDB | 78 | 82 | free limited | fallback event detail, stats, lineups, timeline |
| OpenLigaDB | 72 | 76 | free/open community | schedules and result corroboration where covered |

Quality is not the same as request priority. Mr XPRONOS uses a **free-first**
request policy where data overlaps:

1. ESPN
2. SportScore
3. TheSportsDB
4. OpenLigaDB
5. BSD only for unresolved gaps and bookmaker odds

## Where BSD is intentionally retained

BSD is not removed from:
- real bookmaker/consensus odds;
- BSD V2 historical model/backtest datasets;
- BSD-specific IDs, H2H and calibration workflows where changing provider
  would alter model semantics.

SportScore exposes predictive model probabilities, but its public data API does
not expose a bookmaker market-odds feed. Those predictions must never be
presented as real betting prices.

## Production reduction strategy

- Actu Foot calendar: free aggregate first; BSD only if too few fixtures.
- Live list: ESPN + SportScore + TheSportsDB first; BSD live endpoint only when
  free coverage is below the configured ratio.
- Live statistics: SportScore/TheSportsDB fill missing stats before BSD /stats/.
- Prediction settlement: ESPN + free providers before BSD final event/stats.
- Daily result validation: free providers before BSD.
- Daily odds: BSD retained because provider-specific BSD event IDs are required
  to fetch real double-chance prices.

## Attribution

Public pages using SportScore data must display a visible dofollow
"Powered by SportScore" link to https://sportscore.com/.
