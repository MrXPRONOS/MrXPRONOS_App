"""Evaluate 1xBet grouped-score forecasts on a historical UTC day from current
BSD provider results, even if the production encrypted archive is lagging.
No publication, no ledger mutation, no fabricated bookmaker quotes.
"""
from __future__ import annotations
import argparse,json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from bsd_api import BSDClient
from bsd_v2_core import outcome_scores, fixture_datetime
from grouped_correct_score_prospective import read
from grouped_day_replay_audit import run as run_day

def evaluate(archived,provider_events,day,ledger):
    lookup={}
    for item in archived:
        if not isinstance(item,dict) or item.get("id") is None:continue
        lookup[str(item["id"])]=item
    status=Counter()
    for item in provider_events:
        if not isinstance(item,dict) or item.get("id") is None:
            status["missing_id"]+=1;continue
        try:
            kickoff=fixture_datetime(item)
        except (TypeError,ValueError,KeyError):
            status["invalid_fixture_date"]+=1;continue
        if kickoff.date()!=day:
            status["outside_target_utc_day"]+=1;continue
        status[str(item.get("status") or "unknown").lower()]+=1
        key=str(item["id"])
        if outcome_scores(item) is not None or key not in lookup:
            lookup[key]=item
    answer=run_day(list(lookup.values()),day,ledger)
    answer["source_details"]={
        "result_source":"BSD API current match results, merged onto original private historical BSD archive",
        "live_source_statuses":dict(status),
        "provider_events":len(provider_events),
        "provider_finished":sum(1 for e in provider_events if isinstance(e,dict) and outcome_scores(e) is not None),
        "archive_lag_warning": "Live results may be incomplete or delayed; this report is a dated snapshot.",
        "comparison_warning": "Only forecasts previously captured before kickoff are prospective. Replayed picks are reconstructions after seeing final scores.",
    }
    return answer

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True)
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--out",default="tmp/grouped-correct-score/day-2026-10-20-provider-results.json")
    args=parser.parse_args()
    day=date.fromisoformat(args.date)
    archive=json.loads(Path(args.history).read_text(encoding="utf-8"))
    client=BSDClient(max_requests=50)
    page=client.list_events(day,day,page_size=200,max_pages=20,ttl=0)
    if not page.complete:
        raise RuntimeError("Refusing partial BSD results pagination: "+str(page.total_reported))
    report=evaluate(archive,page.events,day,read())
    report["source_details"].update({"api_requests":client.requests_made,
                                    "pagination_complete":page.complete,
                                    "total_reported_by_api":page.total_reported,
                                    "observed_utc":datetime.now(timezone.utc).isoformat()})
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("GROUPED_LIVE_DAY_STATUS",json.dumps({
        "day":str(day),"source_details":report["source_details"],
        "archived":report["prematch_archive"]["recorded_for_date"],
        "archived_status":report["prematch_archive"]["status"],
        "replay_finished":report["finished_with_score"],
        "replay_eligible":report["replay_eligible"],
        "prematch_performance":report["prematch_archive"]["metrics"],
        "replay_performance":report["replay_policy_metrics"],
        "group_replay":report["replay_all_nine_groups_on_same_matches"],
        "match_samples":report["replay_all_matches"][:15]
    },ensure_ascii=False))
if __name__=="__main__":
    main()
