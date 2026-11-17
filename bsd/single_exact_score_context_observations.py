"""First-seen encrypted BSD pre-match lineup observations, separate from picks.

A lineup may be observed AFTER the original score forecast, but only BEFORE
kickoff. It is NEVER used to change that previously archived immutable pick.
Once results settle, this independent prospective observation can train the
future-only experimental absence learner if chronologically validated.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,json
from bsd_archive import cipher
from bsd_v2_core import fixture_datetime
from bsd_h2h import _team_id
from single_exact_score_context import enrich_lineups
from single_exact_score_research import prematch_context
from single_exact_score_context_model import source_features,utc

FORMAT="mrx-single-verified-lineup-snapshots-v1"
PATH=Path("bsd/single_exact_score_context_observations.enc.json")
MIN_LEAD=timedelta(minutes=30)

def empty():
    return {"format":FORMAT,"records":{}}

def digest(record):
    data={k:v for k,v in record.items() if k!="digest"}
    return hashlib.sha256(json.dumps(data,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()

def valid(row):
    try:
        if not isinstance(row,dict) or not row.get("forecast_digest"):
            return False
        observed=utc(row["observed_at_utc"])
        kickoff=utc(row["kickoff_utc"])
        captured=utc(row["forecast_captured_at_utc"])
        if observed>kickoff-MIN_LEAD or captured>kickoff-MIN_LEAD:
            return False
        if row.get("context",{}).get("observed_at_utc")!=row["observed_at_utc"]:
            return False
        if source_features(row["context"]) is None:return False
        return row.get("digest")==digest(row)
    except (TypeError,ValueError,KeyError,OverflowError):
        return False

def read(path=PATH,secret=None):
    path=Path(path)
    if not path.exists():return empty()
    envelope=json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("format")!=FORMAT or not isinstance(envelope.get("encrypted"),str):
        raise ValueError("Context observations must be encrypted")
    data=json.loads((secret or cipher()).decrypt(envelope["encrypted"].encode("ascii")))
    if data.get("format")!=FORMAT or not isinstance(data.get("records"),dict):
        raise ValueError("Encrypted lineup archive schema mismatch")
    if any(not valid(record) for record in data["records"].values()):
        raise ValueError("Corrupted pre-match lineup observation")
    return data

def save(data,path=PATH,secret=None):
    if data.get("format")!=FORMAT or not isinstance(data.get("records"),dict):
        raise ValueError("Unexpected lineup archive")
    if any(not valid(record) for record in data["records"].values()):
        raise ValueError("Refusing to save invalid lineup evidence")
    path=Path(path)
    token=(secret or cipher()).encrypt(json.dumps(data,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).decode("ascii")
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps({"format":FORMAT,"encrypted":token}),encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)

def capture(archive,fixtures,match_ledger,client,now,*,max_lookups=12,clock=None):
    """Gather pre-match evidence from pending archived scores, not only new games."""
    if now.tzinfo is None:raise ValueError("UTC-aware now required")
    clock=clock or (lambda:datetime.now(timezone.utc))
    candidates=[]
    for event in fixtures:
        key=str(event.get("id"))
        row=match_ledger["records"].get(key)
        if key in archive["records"] or not row or row.get("status")!="pending":
            continue
        try:
            kickoff=fixture_datetime(event)
            if (kickoff<=now+MIN_LEAD or utc(row["kickoff"])!=kickoff
                or utc(row["captured_at"])>now or
                row.get("home_id")!=_team_id(event,"home") or
                row.get("away_id")!=_team_id(event,"away")):
                continue
        except (TypeError,ValueError,OverflowError,KeyError):
            continue
        candidates.append((kickoff,key,event,row))
    candidates.sort(key=lambda r:(r[0],r[1]))
    result={"eligible":len(candidates),"attempted":0,"captured":0,
            "no_usable_absence_counts":0,"errors":0,"skipped_late":0}
    for kickoff,key,event,row in candidates:
        if result["attempted"]>=max_lookups or client.requests_made>=client.max_requests:
            break
        result["attempted"]+=1
        # Reuse only an observation actually fetched before kickoff.
        stamp=event.get("prematch_context")
        source=stamp.get("source") if isinstance(stamp,dict) else None
        if source!="bsd-v2-events-lineups":
            fetched=enrich_lineups([event],client,now,max_lookups=1,clock=clock)
            result["errors"]+=fetched.get("errors",0)
        observed=clock()
        if observed.tzinfo is None:raise ValueError("Timezone-aware observation required")
        if kickoff<=observed+MIN_LEAD:
            result["skipped_late"]+=1
            continue
        normalized=prematch_context(event,observed,kickoff)
        if source_features(normalized) is None:
            result["no_usable_absence_counts"]+=1
            continue
        data={"match_id":key,
              "forecast_digest":row.get("forecast_sha256"),
              "forecast_captured_at_utc":row["captured_at"],
              "kickoff_utc":kickoff.isoformat(),
              "observed_at_utc":normalized["observed_at_utc"],
              "context":normalized}
        data["digest"]=digest(data)
        if not valid(data):
            result["errors"]+=1
            continue
        archive["records"][key]=data
        result["captured"]+=1
    return result
