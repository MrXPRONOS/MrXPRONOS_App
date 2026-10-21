"""Isolated ESPN-only benchmark for exactly 100 real football fixtures on Render.
Read only. No Supabase modifications, no other football providers.
"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/all"
MAX_WORKERS = min(16, max(1, int(os.getenv("MAX_WORKERS", "12"))))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
TARGET = 100
FIELDS = (
    "corner_kicks", "total_shots", "shots_on_target", "fouls",
    "yellow_cards", "red_cards", "ball_possession",
)
ALIASES = {
    "corners":"corner_kicks", "cornerkicks":"corner_kicks", "woncorners":"corner_kicks",
    "totalshots":"total_shots", "shots":"total_shots", "shotstotal":"total_shots",
    "shotsontarget":"shots_on_target", "shotsongoal":"shots_on_target",
    "shotsontargettotal":"shots_on_target",
    "fouls":"fouls", "foulscommitted":"fouls",
    "yellowcards":"yellow_cards", "redcards":"red_cards",
    "possession":"ball_possession", "possessionpct":"ball_possession",
    "possessionpercentage":"ball_possession", "ballpossession":"ball_possession",
}
run_lock = threading.Lock()
quota_blocked = threading.Event()
cache = {"last": None}

def fetch_json(url):
    start = time.monotonic()
    if quota_blocked.is_set():
        return None, "skipped after HTTP 429", 0
    try:
        req = Request(url, headers={"User-Agent":"MrXPRONOS-ESPN-Only-Test/1.0",
                                     "Accept":"application/json"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as res:
            return json.load(res), None, round(time.monotonic()-start,3)
    except HTTPError as ex:
        if ex.code == 429:
            quota_blocked.set()
        return None, "HTTP " + str(ex.code), round(time.monotonic()-start,3)
    except Exception as ex:
        return None, (type(ex).__name__ + ": " + str(ex))[:170], round(time.monotonic()-start,3)

def parse_stat_list(rows):
    parsed = {}
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):
            continue
        raw = row.get("name") or row.get("label") or row.get("type") or row.get("abbreviation") or ""
        key = ALIASES.get(re.sub(r"[^a-z0-9]", "", str(raw).lower()))
        if not key:
            continue
        value = row.get("displayValue", row.get("value"))
        try:
            number = float(str(value).replace("%","").replace(",","").strip())
            if number >= 0:
                parsed[key] = number
        except (TypeError, ValueError):
            pass
    return parsed

def parse_espn_stats(body):
    teams = (body.get("boxscore") or {}).get("teams") if isinstance(body,dict) else []
    if not isinstance(teams,list) or len(teams)!=2:
        return {}
    # Both teams must independently report each statistic.
    a = parse_stat_list(teams[0].get("statistics",[]))
    b = parse_stat_list(teams[1].get("statistics",[]))
    return {key:[a[key],b[key]] for key in FIELDS if key in a and key in b}

def game_state(game):
    typ = ((game.get("status") or {}).get("type") or {})
    return str(typ.get("state") or "").lower()

def fetch_fixture_detail(game):
    mid = str(game.get("id") or "")
    url = ESPN + "/summary?" + urlencode({"event":mid})
    body, error, latency = fetch_json(url)
    pairs = parse_espn_stats(body) if body else {}
    return {"id":mid, "state":game_state(game), "http_error":error,
            "fields":list(pairs), "complete":len(pairs)==len(FIELDS),
            "has_stats":bool(pairs), "latency":latency}

def run_probe():
    with run_lock:
        started = time.monotonic()
        quota_blocked.clear()
        now = datetime.now(timezone.utc)
        observed = {}
        dates = []
        for days_before in range(0, 9):
            day = (now-timedelta(days=days_before)).strftime("%Y%m%d")
            payload, error, latency = fetch_json(
                ESPN+"/scoreboard?"+urlencode({"dates":day,"limit":500}))
            matches = payload.get("events",[]) if isinstance(payload,dict) else []
            dates.append({"date":day,"events":len(matches),"error":error,
                          "latency_seconds":latency})
            for game in matches:
                mid = str(game.get("id") or "")
                if mid and game_state(game) in ("in","post"):
                    observed[mid]=game
            if len(observed)>=TARGET or quota_blocked.is_set():
                break
        live = [e for e in observed.values() if game_state(e)=="in"]
        finished = [e for e in observed.values() if game_state(e)=="post"]
        selected = (live+finished)[:TARGET]
        print("ESPN_ONLY_100_SELECTED "+json.dumps({
            "selected":len(selected),"live":min(TARGET,len(live)),
            "finished":max(0,len(selected)-len(live)),
            "scoreboards":dates},ensure_ascii=False),flush=True)
        details=[]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(fetch_fixture_detail,game) for game in selected]
            for future in as_completed(futures):
                try:
                    details.append(future.result())
                except Exception as ex:
                    details.append({"id":"unknown","state":"unknown",
                                    "http_error":str(ex),"fields":[],
                                    "has_stats":False,"complete":False})
        actual_live = [d for d in details if d["state"]=="in"]
        field_counts = {field:sum(field in d["fields"] for d in details)
                        for field in FIELDS}
        elapsed = round(time.monotonic()-started,2)
        report = {
            "at_utc":datetime.now(timezone.utc).isoformat(),
            "provider":"ESPN ONLY",
            "target":TARGET,"matches_selected":len(selected),
            "live_matches":len(actual_live),
            "finished_matches":len(selected)-len(actual_live),
            "scoreboard_days":dates,
            "detail_requests":len(details),
            "http_success":sum(d.get("http_error") is None for d in details),
            "http_failures":sum(d.get("http_error") is not None for d in details),
            "with_at_least_one_stat_pair":sum(d["has_stats"] for d in details),
            "with_all_seven_stat_pairs":sum(d["complete"] for d in details),
            "stats_by_field":field_counts,
            "live_with_at_least_one_stat_pair":sum(d["has_stats"] for d in actual_live),
            "live_with_all_seven_stat_pairs":sum(d["complete"] for d in actual_live),
            "workers":MAX_WORKERS,
            "duration_seconds":elapsed,
            "under_60_seconds":elapsed<60,
            "hit_http_429":quota_blocked.is_set(),
            "failed_match_ids":[{"id":d["id"],"error":d.get("http_error")}
                for d in details if d.get("http_error")][:12],
        }
        cache["last"]=report
        print("ESPN_ONLY_100_RESULT "+json.dumps(report,ensure_ascii=False),flush=True)
        return report

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path=="/health":
            self.reply({"ok":True,"provider":"ESPN ONLY"})
        elif path=="/last":
            self.reply(cache["last"] or {"status":"ESPN-only benchmark not finished"})
        elif path=="/probe":
            self.reply(run_probe())
        else:
            self.reply({"available":["/health","/last","/probe"]},404)
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def reply(self,body,status=200):
        data=json.dumps(body,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__=="__main__":
    print("ESPN_ONLY_100_BOOT "+datetime.now(timezone.utc).isoformat(),flush=True)
    if os.getenv("RUN_PROBE_ON_STARTUP","1")=="1":
        threading.Thread(target=run_probe,daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",int(os.getenv("PORT","10000"))),Handler).serve_forever()
