#!/usr/bin/env python3
"""Two-day scheduled fixtures import from API-Football.
Never fabricates statistics. One bounded request per day, no client-side secret.
Run on GitHub Actions every 6 hours, only if API_FOOTBALL_KEY is configured.
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

BASE="https://v3.football.api-sports.io"
def request_json(url,headers):
    with urlopen(Request(url,headers=headers),timeout=20) as r:
        return json.load(r)

def main():
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    db=os.getenv("SUPABASE_URL","").rstrip("/")
    token=os.getenv("SUPABASE_SERVICE_ROLE_KEY","").strip()
    if not key:
        print("API_FOOTBALL_SCHEDULE_SKIPPED: API_FOOTBALL_KEY not configured")
        return 0
    if not db.startswith("https://") or not token:
        print("::error::Supabase endpoint/secret not configured")
        return 1
    now=datetime.now(timezone.utc)
    imported=[]
    for delta in (0,1):
        date=(now+timedelta(days=delta)).date().isoformat()
        query=urlencode({"date":date,"timezone":"UTC"})
        try:
            data=request_json(BASE+"/fixtures?"+query,{"x-apisports-key":key,"Accept":"application/json"})
        except (HTTPError,URLError) as e:
            print("API_FOOTBALL_SCHEDULE_PROVIDER_ERROR",type(e).__name__)
            continue
        if data.get("errors"):
            print("API_FOOTBALL_SCHEDULE_UNAVAILABLE",list(data["errors"])[:5] if isinstance(data["errors"],dict) else "provider error")
            continue
        for event in data.get("response",[]):
            fixture=event.get("fixture") or {}
            teams=event.get("teams") or {}
            home=teams.get("home") or {}
            away=teams.get("away") or {}
            league=event.get("league") or {}
            ts=fixture.get("date")
            status=(fixture.get("status") or {}).get("short","")
            if status not in ("NS","TBD") or not ts or not home.get("name") or not away.get("name"):
                continue
            try:
                date_obj=datetime.fromisoformat(ts.replace("Z","+00:00"))
            except ValueError:
                continue
            if date_obj<now-timedelta(minutes=10):
                continue
            fid="api_football:"+str(fixture.get("id"))
            match={
                "id":fid, "source_match_id":str(fixture.get("id")),
                "home_team":home["name"],"away_team":away["name"],
                "home_logo":home.get("logo"),"away_logo":away.get("logo"),
                "league_name":league.get("name"),
                "league":{"name":league.get("name"),"logo":league.get("logo")},
                "event_date":ts,"status":status,"is_live":False,
                "is_finished":False,"source":"api_football",
                "source_names":["api_football"],
                "live_stats":{"home":{},"away":{}},
            }
            imported.append({
                "fixture_id":fid,"event_date":ts,"home_team":home["name"],
                "away_team":away["name"],"source_names":["api_football"],
                "fixture":match,"updated_at":now.isoformat()
            })
    if imported:
        url=db+"/rest/v1/live_scheduled_fixtures?on_conflict=fixture_id"
        payload=json.dumps(imported[:500]).encode()
        req=Request(url,data=payload,method="POST",headers={
            "apikey":token,"Authorization":"Bearer "+token,
            "Content-Type":"application/json","Prefer":"resolution=merge-duplicates,return=minimal"
        })
        try:
            with urlopen(req,timeout=25) as r:
                print("API_FOOTBALL_SCHEDULE_IMPORTED",len(imported),r.status)
        except (HTTPError,URLError) as e:
            print("::error::Supabase scheduled fixture write failed",type(e).__name__)
            return 1
    else:
        print("API_FOOTBALL_SCHEDULE_NO_FIXTURES_OR_NO_ACCESS")
    return 0

if __name__=="__main__":
    sys.exit(main())
