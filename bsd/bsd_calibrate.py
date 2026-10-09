"""Calibration chronologique 2025 seulement, validation 2026 séparée."""
import argparse
import json
from datetime import timedelta
from bsd_archive import MATCHES_FILE, _read_json
from bsd_predict import HistoryIndex, team_form, _estimated_goals, BASE_GOALS_HOME, BASE_GOALS_AWAY
from bsd_h2h import _team_id, _valid_score, _utc
from bsd_markets import MarketCalibrator, candidates_from_goals, realized


def historical_candidates(match, index):
    hid, aid = _team_id(match, "home"), _team_id(match, "away")
    if not hid or not aid or hid == aid: return []
    kickoff = str(match.get("event_date") or "")
    h, a = index.recent(hid, kickoff), index.recent(aid, kickoff)
    if min(len(h), len(a)) < 3: return []
    hf, af = team_form(hid, h), team_form(aid, a)
    hv = team_form(hid, index.recent(hid, kickoff, venue="home"))
    av = team_form(aid, index.recent(aid, kickoff, venue="away"))
    xh = _estimated_goals(hf, hv, af, BASE_GOALS_HOME)
    xa = _estimated_goals(af, av, hf, BASE_GOALS_AWAY)
    return candidates_from_goals(xh, xa)


def fit_calibration(history, *, year=2025, max_fixtures=3000):
    index = HistoryIndex(history)
    games = []
    for m in history:
        if not isinstance(m, dict) or str(m.get("status")) != "finished": continue
        try: dt = _utc(str(m.get("event_date") or ""))
        except (ValueError, TypeError): continue
        if dt.year == year and _valid_score(m.get("home_score")) is not None and _valid_score(m.get("away_score")) is not None:
            games.append((dt, m))
    games.sort(key=lambda x: (x[0], str(x[1].get("id"))))
    if len(games) > max_fixtures:
        step = len(games) / max_fixtures
        games = [games[int(i * step)] for i in range(max_fixtures)]
    cal = MarketCalibrator()
    scored = 0
    for dt, m in games:
        candidates = historical_candidates(m, index)
        if not candidates: continue
        scored += 1
        hs, aws = _valid_score(m["home_score"]), _valid_score(m["away_score"])
        for candidate in candidates:
            cal.observe(candidate, realized(candidate, hs, aws))
    return cal, {"training_year": year, "fixtures": len(games), "fixtures_with_form": scored,
                 "candidate_observations": sum(n for n, _ in cal.counts.values())}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, choices=[2024, 2025], default=2025)
    p.add_argument("--max-fixtures", type=int, default=3000)
    p.add_argument("--output", default="bsd/calibration_bsd.json")
    args = p.parse_args()
    matches = _read_json(MATCHES_FILE, None)
    if not isinstance(matches, list) or not matches:
        p.error("Historique absent")
    cal, summary = fit_calibration(matches, year=args.year, max_fixtures=args.max_fixtures)
    from pathlib import Path
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(cal.to_dict(), separators=(",", ":")), encoding="utf-8")
    print("BSD_CALIBRATION:", json.dumps(summary))
