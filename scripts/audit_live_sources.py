#!/usr/bin/env python3
"""Read-only, bounded audit of football API contracts; never prints credentials or full payloads."""
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
DAY = NOW.strftime("%Y-%m-%d")
ESPN_DAY = NOW.strftime("%Y%m%d")
RESULTS = {}

def probe(name, url, key=None, auth_type=None, timeout=10):
    headers = {"Accept": "application/json", "User-Agent": "MrXPRONOS-API-Audit/1.0"}
    if key:
        headers["Authorization" if auth_type == "bsd" else "X-API-Key"] = ("Token " + key if auth_type == "bsd" else key)
    started = time.monotonic()
    info = {"endpoint": urllib.parse.urlparse(url).path}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
            info["http"] = response.status
            info["duration_ms"] = int((time.monotonic() - started) * 1000)
            data = response.read(2000001)
            if len(data) > 2000000:
                raise ValueError("response_exceeds_2mb")
            parsed = json.loads(data)
            info["json"] = True
            return info, parsed
    except urllib.error.HTTPError as exc:
        info.update({"http": exc.code, "error": "http_error"})
    except Exception as exc:
        info["error"] = type(exc).__name__
    info["duration_ms"] = int((time.monotonic() - started) * 1000)
    return info, None

def record(name, info, **extra):
    RESULTS[name] = {**info, **extra}
    print(json.dumps({"source": name, **RESULTS[name]}, ensure_ascii=False), flush=True)

def arr(body, *keys):
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    for key in keys:
        if isinstance(body.get(key), list):
            return body[key]
    return []

def pairs(stats, key):
    if not isinstance(stats, dict):
        return False
    home, away = stats.get("home"), stats.get("away")
    return (isinstance(home, dict) and isinstance(away, dict)
            and home.get(key) is not None and away.get(key) is not None)

# 1. SportScore: the documented /fixtures and /match paths.
u = "https://sportscore.com/api/v1/fixtures/?" + urllib.parse.urlencode(
    {"sport": "football", "date": DAY, "status": "live", "limit": 200})
p, d = probe("sportscore_live", u)
fixtures = arr(d, "matches", "fixtures", "results")
record("sportscore_live", p, fixtures=len(fixtures), first_fields=sorted(fixtures[0].keys())[:24] if fixtures else [])
if fixtures:
    f = fixtures[0]
    raw_url = str(f.get("url") or f.get("match_url") or "")
    match = re.search(r"/match/([^/?#]+)/", raw_url)
    slug = str(f.get("slug") or f.get("match_slug") or (match.group(1) if match else ""))
    if slug:
        info, body = probe("sportscore_detail", "https://sportscore.com/api/v1/match/?" +
                           urllib.parse.urlencode({"sport": "football", "slug": slug}))
        root = (body.get("match") or body.get("data") or body) if isinstance(body, dict) else {}
        stat_payload = root.get("stats") or root.get("statistics") or {} if isinstance(root, dict) else {}
        record("sportscore_detail", info, fields=sorted(root.keys())[:30] if isinstance(root, dict) else [],
               has_statistics=bool(stat_payload), corners_pair=pairs(stat_payload, "corner_kicks"),
               stats_type=type(stat_payload).__name__,
               stats_keys=sorted(stat_payload.keys())[:22] if isinstance(stat_payload,dict) else [],
               first_row_keys=(sorted(stat_payload[0].keys())[:22]
                               if isinstance(stat_payload,list) and stat_payload
                               and isinstance(stat_payload[0],dict) else []),
               stat_labels=[str(z.get("label",""))[:45] for z in stat_payload[:22] if isinstance(z,dict)]
               if isinstance(stat_payload,list) else [],
               live_minute_present=root.get("live_minute") is not None)

# 2. ESPN: unofficial but observable scoreboard + optional match summary.
info, board = probe("espn_scoreboard", "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?"+
                    urllib.parse.urlencode({"dates": ESPN_DAY, "limit": 500}))
events = arr(board, "events")
record("espn_scoreboard", info, events=len(events), live=sum(
    1 for e in events if (e.get("status") or {}).get("type", {}).get("state") == "in"))
live_event = next((e for e in events if (e.get("status") or {}).get("type", {}).get("state") == "in"), None)
if live_event and str(live_event.get("id", "")).isdigit():
    info, summary = probe("espn_summary", "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event="+str(live_event["id"]))
    teams = ((summary or {}).get("boxscore") or {}).get("teams") or []
    record("espn_summary", info, teams=len(teams),
           stats_by_side=[len(x.get("statistics") or []) for x in teams[:2]])

# 3. BSD: do not spend the authenticated daily quota unless a key was supplied.
token = os.environ.get("BSD_API_TOKEN", "").strip()
if token:
    info, data = probe("bsd_events_live", "https://sports.bzzoiro.com/api/v2/events/live/", token, "bsd")
    events = arr(data, "results", "events")
    record("bsd_events_live", info, events=len(events))
    if events and events[0].get("id") is not None:
        mid = urllib.parse.quote(str(events[0]["id"]), safe="")
        info, data = probe("bsd_stats", f"https://sports.bzzoiro.com/api/v2/events/{mid}/stats/", token, "bsd")
        stats = (data or {}).get("stats") if isinstance(data, dict) else {}
        record("bsd_stats", info, has_stats=bool(stats),
               corners_pair=pairs(stats, "corner_kicks"), shots_pair=pairs(stats, "total_shots"),
               fouls_pair=pairs(stats, "fouls"))
else:
    record("bsd_events_live", {"status": "not_tested", "reason": "BSD_API_TOKEN not present in GitHub Actions"})

# 4. TheSportsDB: public 123 key, free response capped by the provider.
info, body = probe("thesportsdb_eventsday",
                   "https://www.thesportsdb.com/api/v1/json/123/eventsday.php?"+
                   urllib.parse.urlencode({"d": DAY, "s": "Soccer"}))
record("thesportsdb_eventsday", info, events=len(arr(body, "events")))

# 5. OpenLigaDB: a match schedule service, not detailed live corners.
info, leagues = probe("openligadb_leagues", "https://api.openligadb.de/getavailableleagues")
record("openligadb_leagues", info, leagues=len(arr(leagues)))
info, body = probe("openligadb_next_match", "https://api.openligadb.de/getnextmatchbyleagueshortcut/bl1")
record("openligadb_next_match", info, available=isinstance(body, dict),
       fields=sorted(body.keys())[:22] if isinstance(body, dict) else [])

# 6. MoviOdds: stats are OPT-IN (stats=1), independent of quotes.
movikey = os.environ.get("MOVIODDS_API_KEY", "").strip()
info, body = probe("moviodds_live", "https://moviodds.com/odds?sport=soccer&in_play=1&stats=1", movikey)
matches = arr(body, "matches")
observed = next((m["stats"] for m in matches if isinstance(m.get("stats"), dict) and bool(m["stats"])), {})
movi_home = observed.get("home") if isinstance(observed.get("home"),dict) else {}
movi_away = observed.get("away") if isinstance(observed.get("away"),dict) else {}
record("moviodds_live", info, matches=len(matches),
       first_match_fields=sorted(matches[0].keys())[:45] if matches else [],
       first_clock_keys=sorted(matches[0]["clock"].keys())[:20] if matches
           and isinstance(matches[0].get("clock"),dict) else [],
       first_clock_sample=({k:str(v)[:45] for k,v in matches[0]["clock"].items()
                           if isinstance(v,(str,int,float))}
                           if matches and isinstance(matches[0].get("clock"),dict) else {}),
       first_match_clock_fields={k:str(matches[0][k])[:85] for k in
           ["minute","elapsed","clock","timer","match_time","live_minute","status_text","time","period"]
           if matches and k in matches[0] and isinstance(matches[0][k],(str,int,float))},
       corner_pairs=sum(1 for m in matches if pairs(m.get("stats"), "corners")),
       shots_pairs=sum(1 for m in matches if pairs(m.get("stats"), "shots")),
       attacks_pairs=sum(1 for m in matches if pairs(m.get("stats"), "attacks")),
       dangerous_attacks_pairs=sum(1 for m in matches if pairs(m.get("stats"), "dangerous_attacks")),
       fouls_pairs=sum(1 for m in matches if pairs(m.get("stats"), "fouls")),
       with_stats=sum(1 for m in matches if isinstance(m.get("stats"), dict) and bool(m["stats"])),
       with_quotes=sum(1 for m in matches if m.get("quotes")),
       first_stats_fields=sorted(observed.keys())[:24],
       current_play_type=type(observed.get("current_play")).__name__,
       current_play_keys=(sorted(observed["current_play"].keys())[:24]
                          if isinstance(observed.get("current_play"),dict) else []),
       current_play_sample=({k:str(v)[:60] for k,v in observed["current_play"].items()
                             if isinstance(v,(str,int,float))} if isinstance(observed.get("current_play"),dict) else {}),
       current_play=(str(observed.get("current_play"))[:70]
                     if isinstance(observed.get("current_play"), (str,int,float)) else None),
       home_stats_fields=sorted(movi_home.keys())[:32],
       away_stats_fields=sorted(movi_away.keys())[:32],
       sample_stats_updated_at=bool(observed.get("updated_at")))

# Store the non-secret summary for comparison with later audits.
summary = {"checked_at": NOW.isoformat(), "day": DAY, "providers": RESULTS}
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
base = os.environ.get("SUPABASE_URL", "https://nhwafcpndlufzzxexikh.supabase.co").rstrip("/")
if key:
    body = json.dumps({
        "name": "live_api_audit", "last_run_at": NOW.isoformat(),
        "last_ok": True, "meta": summary,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/rest/v1/cron_runs?on_conflict=name", data=body, method="POST",
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            print("Supabase non-secret audit report stored:", res.status)
    except Exception as e:
        print("Audit report storage unavailable:", type(e).__name__)
else:
    print("Supabase report skipped: service-role secret unavailable in GitHub Actions")
print("API audit completed:", len(RESULTS), "bounded probes")
