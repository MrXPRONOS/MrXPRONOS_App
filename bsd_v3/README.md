# BSD V3 - isolated experimental engine (free only)

STATUS: DEVELOPMENT/SHADOW. BSD V2 is unchanged and remains the only public engine.

## Components
- legacy.py: read-only bridge to the existing BSD history and models.
- policy.py: fixture quality, 79 percent public prequalification, conservative risk controls.
- probabilities.py: coherent joint goals matrix for 1X2, totals, BTTS, double chance.
- calibration.py: train Jan-Aug 2025, gate Sep-Dec 2025. Reverts to baseline if not validated.
- quotes.py: dated and verified quotes; free consensus is a NON-EXECUTABLE benchmark.
- selection.py: multi-family candidates and joint-matrix correlation gate.
- engine.py: all candidate market diagnostics, never publishes.
- evaluation.py: retrospective analysis without fake historical odds/ROI.
- cli.py: existing free BSD API and encrypted historical archive.
- test_v3.py: offline tests with no API keys.

## Commands (repository root)
    python -m pip install requests cryptography
    python bsd/bsd_archive.py restore
    python -m bsd_v3.cli --mode shadow --days 1 --max-odds-events 15
    python -m bsd_v3.cli --mode evaluate --output bsd_v3/artifacts/evaluation.json
    python -m unittest discover -s bsd_v3 -p 'test_*.py' -v

On GitHub Actions, use BSD_HISTORY_KEY and BSD_API_KEY already configured.
Never commit the decrypted BSD history or upload it as an artifact.
Delete bsd/all_matches_bsd.json and bsd/backfill_state.json after each run.

## Safety
No access to data.json, V2 publishing ledger, site deployment, or Telegram.
Shadow classifications are NOT permission to publish or evidence of guaranteed returns.
Only a verified named bookmaker quote could qualify for actionable Value Shadow;
BSD free consensus is for research and cannot prove a realizable betting price.
All generated output must live under bsd_v3/artifacts/.

## Remaining work
Independent prospective validation, proof of better forecasting performance,
reliable freely available named bookmaker odds, operational integration,
all 140-item feature acceptance checks, and public activation are NOT complete.
