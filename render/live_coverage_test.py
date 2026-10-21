"""Render free diagnostic for Mr XPRONOS. Read-only, no betting signals, no DB writes."""
import os, time, threading, logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
LOCK = threading.Lock()
STATE = {"status": "not_started", "match_count": 0, "last_run": None}
API = "https://site.api.espn.com/apis/site/v2/sports/soccer/all"
MAX_WORKERS = max(1, min(20, int(os.getenv("LIVE_WORKERS", "10"))))
POLL_SECONDS = max(60, int(os.getenv("LIVE_POLL_SECONDS", "60")))
HTTP_TIMEOUT = 12
STAT_KEYS = ("cornerKicks", "totalShots", "shotsOnTarget", "fouls", "yellowCards", "redCards", "possessionPct")

def fetch_json(url, params=None):
    response = requests.get(url, params=params, timeout=HTTP_TIMEOUT, headers={"User-Agent": "MrXPRONOS-coverage-test/1.0"})
    response.raise_for_status()
    return response.json()

def extract_live_events(payload):
    result = {}
    for event in payload.get("events", []):
        status = ((event.get("status") or {}).get("type") or {}).get("state")
        if status != "in":
            continue
        event_id = str(event.get("id", ""))
        if event_id:
            result[event_id] = event
    return result

def extract_stats(summary):
    rows = ((summary.get("boxscore") or {}).get("players") or [])
    teams = ((summary.get("boxscore") or {}).get("teams") or [])
    result = {}
    for item in teams:
        name = (item.get("team") or {}).get("displayName") or "unknown"
        vals = {}
        for stat in item.get("statistics") or []:
            key = stat.get("name") or stat.get("abbreviation") or stat.get("label")
            if key:
                vals[str(key)] = stat.get("displayValue") or stat.get("value")
        result[name] = vals
    return result

def enrich(event):
    eid = str(event.get("id"))
    try:
        summary = fetch_json(API + "/summary", {"event": eid})
        return {"id": eid, "name": event.get("name"), "ok": True, "stats": extract_stats(summary)}
    except Exception as exc:
        return {"id": eid, "name": event.get("name"), "ok": False, "error": str(exc)[:170], "stats": {}}

def run_cycle():
    if not LOCK.acquire(blocking=False):
        return {"status": "busy", "message": "Existing cycle still running"}
    started = time.monotonic()
    try:
        now = datetime.now(timezone.utc)
        # Three scoreboard days accommodate matches crossing UTC midnight.
        days = [datetime.fromtimestamp(now.timestamp() + delta * 86400, timezone.utc).strftime("%Y%m%d") for delta in (-1, 0, 1)]
        collected = {}
        errors = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(fetch_json, API + "/scoreboard", {"dates": day, "limit": 500}): day for day in days}
            for future in as_completed(futures):
                try:
                    collected.update(extract_live_events(future.result()))
                except Exception as exc:
                    errors.append(f"{futures[future]}: {str(exc)[:160]}")
        items = list(collected.values())
        matched = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(enrich, event) for event in items]
            for future in as_completed(futures):
                matched.append(future.result())
        ok = sum(1 for item in matched if item["ok"])
        with_stats = sum(1 for item in matched if item["stats"] and any(item["stats"].values()))
        state = {
            "status": "complete" if not errors else "partial",
            "last_run": now.isoformat(),
            "match_count": len(items),
            "attempted": len(matched),
            "success_details": ok,
            "matches_with_stats": with_stats,
            "missing_stats": len(items) - with_stats,
            "errors": errors,
            "duration_seconds": round(time.monotonic() - started, 2),
            "within_60_seconds": time.monotonic() - started <= 60,
            "provider": "ESPN public (diagnostic only)",
            "matches": sorted(matched, key=lambda x: x["id"]),
        }
        STATE.clear()
        STATE.update(state)
        app.logger.info("COVERAGE count=%s attempted=%s stats=%s duration=%s", len(items), len(matched), with_stats, state["duration_seconds"])
        return state
    except Exception as exc:
        STATE.update(status="failed", error=str(exc)[:240], last_run=datetime.now(timezone.utc).isoformat())
        return STATE.copy()
    finally:
        LOCK.release()

@app.get("/")
@app.get("/health")
def health():
    return jsonify({k: v for k, v in STATE.items() if k != "matches"})

@app.get("/coverage")
def coverage():
    return jsonify(STATE)

@app.route("/run", methods=["GET", "POST"])
def run_now():
    return jsonify(run_cycle())

def polling_loop():
    # Free Render may sleep/restart; this is a best-effort test, not guaranteed scheduling.
    while True:
        run_cycle()
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    threading.Thread(target=polling_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")), threaded=True)
