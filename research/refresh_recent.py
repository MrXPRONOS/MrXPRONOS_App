#!/usr/bin/env python3
"""Research-only SportData history refresh. Never overwrites production cache."""
import argparse
import json
import shutil
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from sportdata_api import fetch_games, get_api_keys
from allmatches import extract_game_info


def as_date(value):
    from datetime import datetime, timezone
    if not value:
        return None
    try:
        s=str(value)
        return (date.fromisoformat(s) if len(s)==10 else
                datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc).date())
    except (ValueError, TypeError):
        return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source", default="cache/all_matches.json")
    parser.add_argument("--output", default="/tmp/mrx_all_matches_research.json")
    parser.add_argument("--audit", default="/tmp/mrx_refresh_audit.json")
    parser.add_argument("--end", default="2026-10-19")
    args=parser.parse_args()
    end=date.fromisoformat(args.end)
    source=Path(args.source)
    output=Path(args.output)
    raw=json.loads(source.read_text(encoding="utf8"))
    if not isinstance(raw,list):
        raw=raw.get("matches",raw.get("games",[]))
    maximum=max((d for r in raw if isinstance(r,dict)
                 if (d:=as_date(r.get("start_time") or r.get("event_date") or r.get("startTime") or r.get("date")))), default=None)
    start=max(date(2026,1,1), (maximum+timedelta(days=1)) if maximum else date(2026,1,1))
    summary={"source_max_date":str(maximum),"target_end":str(end),
             "missing_days_to_attempt":max(0,(end-start).days+1),
             "api_configured":bool(get_api_keys()),
             "calls":0,"failed_calls":0,"received_matches":0,"accepted_finished":0}
    if start<=end and get_api_keys():
        by_id={str(x.get("id")):x for x in raw if isinstance(x,dict) and x.get("id") is not None}
        original_count=len(by_id)
        now=start
        while now<=end:
            until=min(end,now+timedelta(days=2))
            response=fetch_games(now,until,timeout=35,show_odds=False)
            summary["calls"]+=1
            if not response.ok:
                summary["failed_calls"]+=1
                print("REFRESH_FAILED",now,until,str(response.reason)[:300],flush=True)
            else:
                summary["received_matches"]+=len(response.games)
                for game in response.games:
                    item=extract_game_info(game)
                    if item["is_finished"] and item["id"] is not None:
                        day=as_date(item.get("start_time"))
                        if day is not None and day<=end:
                            by_id[str(item["id"])]=item
                print("REFRESH_RANGE",now,until,len(response.games),flush=True)
            now=until+timedelta(days=1)
        summary["accepted_finished"]=len(by_id)-original_count
        # Preserve id-less original rows without counting duplicates.
        no_id=[x for x in raw if isinstance(x,dict) and x.get("id") is None]
        output.write_text(json.dumps(list(by_id.values())+no_id,ensure_ascii=False),encoding="utf8")
    else:
        shutil.copyfile(source,output)
    Path(args.audit).write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf8")
    print("REFRESH_AUDIT",json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
