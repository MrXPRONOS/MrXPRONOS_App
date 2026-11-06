"""Independent integrity checks of free BSD fixture and historical sources.

No guessed fields, no retroactive availability timestamps and no disclosure of
private history. Failed or conflicting source IDs are rejected, not repaired.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from .legacy import fixture_datetime, outcome_scores
from .policy import utc_datetime
from bsd_v3.legacy import V2History
from bsd_h2h import _team_id

FINISHED = frozenset(("finished",))
UPCOMING = frozenset(("notstarted", "upcoming"))


def audit_event(event, *, now=None, history=False):
    if not isinstance(event, dict):
        return "not_an_object"
    value = event.get("id")
    if value is None or isinstance(value, bool) or not str(value).isdigit():
        return "invalid_event_id"
    h, a = _team_id(event,"home"), _team_id(event,"away")
    if h is None or a is None or h <= 0 or a <= 0 or h == a:
        return "invalid_team_ids"
    try:
        dt = fixture_datetime(event)
        if dt.tzinfo is None:
            return "missing_timezone"
    except (ValueError,TypeError,OverflowError):
        return "invalid_kickoff"
    status = str(event.get("status") or "").lower()
    if history:
        if status not in FINISHED or outcome_scores(event) is None:
            return "unsettled_history"
        if now is not None and dt >= utc_datetime(now):
            return "future_history"
    else:
        if status not in UPCOMING:
            return "not_upcoming"
        if now is not None and dt <= utc_datetime(now):
            return "already_started"
        if event.get("home_score") is not None or event.get("away_score") is not None:
            return "future_score_in_fixture"
    return None


def clean_fixture_batch(fixtures, *, now, max_events=10000):
    if len(fixtures) > max_events:
        raise ValueError("Too many fixtures for one free run")
    by_id={}
    conflicts=set()
    rejected=Counter()
    for raw in fixtures:
        reason=audit_event(raw,now=now)
        if reason:
            rejected[reason]+=1
            continue
        eid=str(raw["id"])
        if eid in conflicts:
            rejected["conflicting_duplicate"]+=1
            continue
        previous=by_id.get(eid)
        if previous is None:
            by_id[eid]=raw
            continue
        # Multiple identical records are harmless. Any kickoff/team conflict
        # is irreconcilable without an authoritative source.
        signature=lambda item:(fixture_datetime(item),_team_id(item,"home"),
                               _team_id(item,"away"),str(item.get("status") or "").lower())
        if signature(raw)==signature(previous):
            rejected["same_fixture_duplicate"]+=1
        else:
            conflicts.add(eid)
            del by_id[eid]
            rejected["conflicting_duplicate"]+=2
    return sorted(by_id.values(),key=lambda x:(fixture_datetime(x),str(x["id"]))),dict(rejected)


def audit_history(history, *, now=None, max_events=250000):
    if not isinstance(history,list) or len(history)>max_events:
        raise ValueError("History not a bounded list")
    reasons=Counter()
    unique={}
    conflict_ids=set()
    for item in history:
        reason=audit_event(item,now=now,history=True)
        if reason:
            reasons[reason]+=1
            continue
        eid=str(item["id"])
        old=unique.get(eid)
        if eid in conflict_ids:
            reasons["duplicate_conflict"]+=1
        elif old is None:
            unique[eid]=item
        elif (fixture_datetime(old)!=fixture_datetime(item) or
              outcome_scores(old)!=outcome_scores(item) or
              _team_id(old,"home")!=_team_id(item,"home") or
              _team_id(old,"away")!=_team_id(item,"away")):
            conflict_ids.add(eid)
            del unique[eid]
            reasons["duplicate_conflict"]+=2
        else:
            reasons["duplicate_exact"]+=1
    items=sorted(unique.values(),key=lambda x:(fixture_datetime(x),str(x["id"])))
    return items,{"received":len(history),"accepted":len(items),
                  "rejected":dict(reasons),
                  "requires_private_historical_timestamps":True,
                  "note":"Original public BSD history has no per-field as-of snapshots. "
                         "Only final scores after their settlement delay are used."}
