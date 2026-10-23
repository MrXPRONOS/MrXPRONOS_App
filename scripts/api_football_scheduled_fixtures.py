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


def save_neon(fixtures):
    """Upsert unchanged fixture payloads in private Neon PostgreSQL."""
    import psycopg
    from psycopg.types.json import Jsonb
    connection = os.getenv("NEON_DATABASE_URL", "").strip()
    if not connection:
        raise RuntimeError("NEON_DATABASE_URL missing; no fallback to Supabase")
    sql = """INSERT INTO public.live_scheduled_fixtures
        (fixture_id,event_date,home_team,away_team,source_names,fixture,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (fixture_id) DO UPDATE SET
        event_date=EXCLUDED.event_date,home_team=EXCLUDED.home_team,
        away_team=EXCLUDED.away_team,source_names=EXCLUDED.source_names,
        fixture=EXCLUDED.fixture,updated_at=EXCLUDED.updated_at"""
    with psycopg.connect(connection, connect_timeout=12) as db:
        with db.cursor() as cursor:
            for row in fixtures[:500]:
                cursor.execute(sql,(row["fixture_id"],row["event_date"],row["home_team"],
                    row["away_team"],row["source_names"],Jsonb(row["fixture"]),row["updated_at"]))


BASE="https://v3.football.api-sports.io"
def request_json(url,headers):
    with urlopen(Request(url,headers=headers),timeout=20) as r:
        return json.load(r)

def main():
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    if not key:
        print("API_FOOTBALL_SCHEDULE_SKIPPED: API_FOOTBALL_KEY not configured")
        return 0
    if not os.getenv("NEON_DATABASE_URL", "").strip():
        print("::error::NEON_DATABASE_URL not configured")
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
        try:
            save_neon(imported)
            print("API_FOOTBALL_SCHEDULE_IMPORTED",len(imported),"NEON")
        except Exception as exc:
            print("::error::Neon scheduled fixture write failed",type(exc).__name__)
            return 1
    else:
        print("API_FOOTBALL_SCHEDULE_NO_FIXTURES_OR_NO_ACCESS")
    return 0

if __name__=="__main__":
    sys.exit(main())
