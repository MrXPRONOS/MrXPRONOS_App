"""BSD v2 pre-match lineup and settled historical measured xG collectors.

Requests are budgeted, strictly time guarded, and never use match results of
the upcoming fixture. Missing stats are never interpreted as zero. No logging
of player identities, access tokens or sensitive data.
"""
from datetime import timedelta
from bsd_api import BSDAPIError, BSDQuotaError, BSDRequestBudgetError
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, outcome_scores

def _extract_unavailable(data):
    raw=data.get("unavailable_players")
    if not isinstance(raw,dict):return {}
    result={}
    for side in ("home","away"):
        players=raw.get(side)
        if isinstance(players,list):
            result[side+"_absences"]=min(30,len(players))
    return result

def lineup_context(payload,now):
    """BSD documented lineup_status and unavailable_players fields only."""
    if not isinstance(payload,dict):
        return None
    status=payload.get("lineup_status")
    if status not in ("confirmed","predicted"):
        return None
    out={"source":"bsd-v2-events-lineups","observed_at_utc":now.isoformat(),
         "lineup_status":status}
    out.update(_extract_unavailable(payload))
    # Do not derive absent starter status from predicted/confirmed XI alone.
    return out

def enrich_lineups(fixtures,client,now,already_seen=(),max_lookups=6):
    seen=set(map(str,already_seen))
    stats={"attempts":0,"found":0,"missing":0,"errors":0,"skipped":0}
    if max_lookups<=0:return stats
    ordered=sorted(fixtures,key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    for event in ordered:
        if str(event.get("id")) in seen:continue
        if fixture_datetime(event)<=now+timedelta(minutes=30):continue
        if str(event.get("status","")).lower() in ("finished","inprogress","live",
                                                     "cancelled","postponed"):
            continue
        if stats["attempts"]>=max_lookups:
            stats["skipped"]+=1;continue
        if client.requests_made>=client.max_requests:
            stats["skipped"]+=1;break
        stats["attempts"]+=1
        try:
            payload=client.get_json("/events/"+str(int(event["id"]))+"/lineups/",ttl=0)
        except (BSDQuotaError,BSDRequestBudgetError):
            stats["errors"]+=1;break
        except (BSDAPIError,ValueError,TypeError):
            stats["errors"]+=1;continue
        info=lineup_context(payload,now)
        if info:
            prior=event.get("prematch_context")
            if not isinstance(prior,dict):prior={}
            # Preserve manually supplied timestamped inputs; never silently
            # replace pre-existing evidence with an API guess.
            event["prematch_context"]={**info,**prior}
            stats["found"]+=1
        else:stats["missing"]+=1
    return stats

def _measured_xg(payload):
    if not isinstance(payload,dict):return None
    allstats=payload.get("stats")
    if not isinstance(allstats,dict):return None
    numbers=[]
    for side in ("home","away"):
        sideobj=allstats.get(side)
        xg=sideobj.get("xg") if isinstance(sideobj,dict) else None
        if not isinstance(xg,dict) or xg.get("estimated") is not False:
            return None
        value=xg.get("actual")
        if type(value) not in (float,int) or not (0<=value<=8):return None
        numbers.append(float(value))
    return tuple(numbers)

def hydrate_history_xg(index,fixtures,client,now,max_lookups=12,capture_into=None):
    """Acquire xG for already settled games, never current/future fixtures."""
    stats={"attempts":0,"measured":0,"not_measured":0,"errors":0}
    target=[]
    visited=set()
    for fixture in sorted(fixtures,key=lambda e:(fixture_datetime(e),str(e.get("id")))):
        if fixture_datetime(fixture)<=now+timedelta(minutes=30):continue
        at=fixture_datetime(fixture)
        for side in ("home","away"):
            team=_team_id(fixture,side)
            if not team:continue
            for old in index.team(team,at,limit=5):
                oid=str(old.get("id"))
                if (oid in visited or outcome_scores(old) is None or
                    fixture_datetime(old)+timedelta(hours=4)>now):
                    continue
                visited.add(oid)
                if old.get("xg_estimated") is False and (
                    type(old.get("home_xg_live")) in (float,int) and
                    type(old.get("away_xg_live")) in (float,int)):
                    continue
                target.append(old)
    for old in target[:max_lookups]:
        if client.requests_made>=client.max_requests:break
        stats["attempts"]+=1
        try:
            payload=client.get_json("/events/"+str(int(old["id"]))+"/stats/",ttl=0)
        except (BSDQuotaError,BSDRequestBudgetError):
            stats["errors"]+=1;break
        except (BSDAPIError,ValueError,TypeError):
            stats["errors"]+=1;continue
        measured=_measured_xg(payload)
        if measured:
            if capture_into is not None:
                capture_into[str(old["id"])]={
                    "home_xg":measured[0],"away_xg":measured[1],
                    "home_team_id":_team_id(old,"home"),
                    "away_team_id":_team_id(old,"away"),
                    "kickoff_utc":fixture_datetime(old).isoformat(),
                    "captured_at_utc":now.isoformat()}
            old["home_xg_live"]=measured[0]
            old["away_xg_live"]=measured[1]
            old["xg_estimated"]=False
            old["xg_available_at_utc"]=now.isoformat()
            stats["measured"]+=1
        else:stats["not_measured"]+=1
    return stats
