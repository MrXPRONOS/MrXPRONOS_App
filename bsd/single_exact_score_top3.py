"""Immutable, encrypted prospective ONE-score × THREE-match research baskets.

Never confuse one exact score on each of three DIFFERENT fixtures with three
alternative exact scores on the SAME fixture. This research ledger is separate
from the immutable per-match archive. Only first-issue selections are scored.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,json,math
from bsd_archive import cipher
from single_exact_score_research import RANK_VERSION

PATH=Path("bsd/single_exact_score_top3.enc.json")
FORMAT="mrx-single-exact-top3-prospective-v1"
RESULT_FIELDS=frozenset(("status","settled_at","matched","hits","winning",
                         "void_reason","voided_at","digest"))

def empty():
    return {"format":FORMAT,"selection_rule":RANK_VERSION,"records":{}}

def _sha(row):
    payload={k:v for k,v in row.items() if k not in RESULT_FIELDS}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,
        ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()

def _utc(value):
    when=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if when.tzinfo is None:raise ValueError("Naive UTC timestamp")
    return when.astimezone(timezone.utc)

def read(path=PATH,secret=None):
    path=Path(path)
    if not path.exists():return empty()
    env=json.loads(path.read_text(encoding="utf-8"))
    if env.get("format")!=FORMAT or not isinstance(env.get("encrypted"),str):
        raise ValueError("Top3 must remain encrypted")
    out=json.loads((secret or cipher()).decrypt(env["encrypted"].encode("ascii")))
    if out.get("format")!=FORMAT or not isinstance(out.get("records"),dict):
        raise ValueError("Top3 schema mismatch")
    for record in out["records"].values():
        if record.get("digest")!=_sha(record) or len(record.get("picks",[]))!=3:
            raise ValueError("Top3 prediction snapshot tampered")
    return out

def save(data,path=PATH,secret=None):
    if data.get("format")!=FORMAT or not isinstance(data.get("records"),dict):
        raise ValueError("Top3 schema mismatch")
    for record in data["records"].values():
        if record.get("digest")!=_sha(record) or len(record.get("picks",[]))!=3:
            raise ValueError("Top3 prediction snapshot tampered")
    path=Path(path)
    token=(secret or cipher()).encrypt(json.dumps(data,sort_keys=True,
           ensure_ascii=False,separators=(",",":")).encode()).decode("ascii")
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps({"format":FORMAT,"encrypted":token}),encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)

def _candidate(rec,now,minimum_lead_minutes=30):
    if rec.get("status")!="pending" or not isinstance(rec.get("score"),list):
        return None
    try:
        at=_utc(rec["kickoff"])
        captured=_utc(rec["captured_at"])
        if (captured>now or at<=now+timedelta(minutes=minimum_lead_minutes)
            or captured>at-timedelta(minutes=minimum_lead_minutes)
            or len(rec["score"])!=2 or any(type(n)!=int or n<0 for n in rec["score"])):
            return None
        # Re-evaluate rank on the SAME comparable feature scale,
        # regardless of the historic rank-version persisted in each record.
        # Never change the original immutable record or score.
        p=rec.get("estimated_probability")
        margin=rec.get("score_margin")
        if (type(p) not in (int,float) or not math.isfinite(p)
                or p<=0 or p>=1 or type(margin) not in (int,float)
                or not math.isfinite(margin) or margin<0):
            return None
        rank=float(p)+.08*min(.20,float(margin))
        rank_rule=RANK_VERSION
    except (TypeError,ValueError,OverflowError,KeyError):
        return None
    return {"id":str(rec["id"]),"kickoff":rec["kickoff"],
            "score":list(rec["score"]),"captured_at":rec["captured_at"],
            "selection_rank":round(rank,9),
            "rank_provenance":rank_rule,
            "probability":rec.get("estimated_probability"),
            "forecast_digest":rec.get("forecast_sha256"),
            "advanced_model_fingerprint_sha256":(rec.get("advanced_research") or {}).get(
                "model_fingerprint_sha256")}

def select_groups(archive,match_ledger,now,*,max_groups=3,minimum_lead_minutes=30,
                  enforce_cutoff=False,cutoff_hour=12,cutoff_minute=13):
    """Freeze at first seen slate; no result/label influences rank or inclusion."""
    if now.tzinfo is None:raise ValueError("UTC timestamp required")
    candidates={}
    for rec in match_ledger["records"].values():
        item=_candidate(rec,now,minimum_lead_minutes)
        if item is not None:
            date=_utc(item["kickoff"]).date().isoformat()
            candidates.setdefault(date,[]).append(item)
    stats={"created":0,"days_short":0,"already_seen":0,"before_cutoff":0}
    for day,items in sorted(candidates.items()):
        if enforce_cutoff:
            cutoff=datetime.fromisoformat(day).replace(
                hour=cutoff_hour,minute=cutoff_minute,tzinfo=timezone.utc)
            if now.astimezone(timezone.utc)<cutoff:
                stats["before_cutoff"]+=1
                continue
        if day in archive["records"]:
            stats["already_seen"]+=1
            continue
        if len(items)<3:
            stats["days_short"]+=1
            continue
        if stats["created"]>=max_groups:break
        chosen=sorted(items,key=lambda r:(-r["selection_rank"],r["kickoff"],r["id"]))[:3]
        rec={"date_utc":day,"issued_at_utc":now.isoformat(),
             "rule_version":RANK_VERSION,"picks":chosen,"status":"pending"}
        rec["digest"]=_sha(rec)
        archive["records"][day]=rec
        stats["created"]+=1
    return stats

def settle_groups(archive,match_ledger,now):
    stats={"settled":0,"pending":0,"incomplete":0,"void":0}
    for rec in archive["records"].values():
        if rec["status"] in ("settled","void"):continue
        labels=[]
        void_reason=None
        for pick in rec["picks"]:
            match=match_ledger["records"].get(str(pick["id"]))
            if not match or match.get("forecast_sha256")!=pick["forecast_digest"] or match.get("score")!=pick["score"]:
                break
            if match.get("status")=="void":
                void_reason="fixture_void:"+str(match.get("void_reason") or "unknown")
                break
            if match.get("status")!="settled" or not isinstance(match.get("actual_score"),list):
                break
            labels.append(int(match["actual_score"]==pick["score"]))
        if void_reason is not None:
            rec["status"]="void"
            rec["void_reason"]=void_reason
            rec["voided_at"]=now.isoformat()
            stats["void"]+=1
            continue
        if len(labels)<3:
            stats["incomplete"]+=1
            stats["pending"]+=1
            continue
        rec["status"]="settled"
        rec["settled_at"]=now.isoformat()
        rec["matched"]=3
        rec["hits"]=sum(labels)
        rec["winning"]=int(any(labels))
        stats["settled"]+=1
    return stats

def verify(archive, match_ledger, now):
    """Fail closed if any frozen Top3 contains a late/changed prediction.

    This uses scores and hashes saved at issuance, never outcome labels to
    determine which three matches would have been chosen.
    """
    if now.tzinfo is None:
        raise ValueError("UTC-aware audit clock required")
    verified=0
    for day,record in archive["records"].items():
        picks=record.get("picks")
        if not isinstance(picks,list) or len(picks)!=3:
            raise ValueError("A basket must contain three distinct match snapshots")
        if day!=record.get("date_utc") or record.get("digest")!=_sha(record):
            raise ValueError("Frozen basket identity/digest mismatch")
        if record.get("status") not in ("pending","settled","void"):
            raise ValueError("Unexpected basket status")
        issued=_utc(record["issued_at_utc"])
        if issued>now+timedelta(minutes=1):
            raise ValueError("Basket issued in the future")
        ids=set()
        for pick in picks:
            key=str(pick.get("id"))
            if key in ids:raise ValueError("Duplicate fixture in Top3")
            ids.add(key)
            kickoff=_utc(pick["kickoff"])
            captured=_utc(pick["captured_at"])
            if (kickoff.date().isoformat()!=day or
                issued>kickoff-timedelta(minutes=30) or
                captured>issued or captured>kickoff-timedelta(minutes=30)):
                raise ValueError("Late or wrong-day basket selection")
            record_original=match_ledger["records"].get(key)
            if (not record_original or
                record_original.get("forecast_sha256")!=pick.get("forecast_digest") or
                record_original.get("score")!=pick.get("score") or
                record_original.get("captured_at")!=pick.get("captured_at")):
                raise ValueError("First-seen match forecast and frozen Top3 disagree")
        if record["status"]=="settled":
            expected_hits=0
            for pick in picks:
                source=match_ledger["records"][str(pick["id"])]
                if source.get("status")!="settled" or not isinstance(source.get("actual_score"),list):
                    raise ValueError("Settled basket without three final results")
                expected_hits+=int(source["actual_score"]==pick["score"])
            hits=record.get("hits")
            if (record.get("matched")!=3 or type(hits)!=int or hits!=expected_hits or not 0<=hits<=3 or
                record.get("winning")!=int(hits>0) or
                _utc(record["settled_at"])<issued):
                raise ValueError("Impossible settled Top3 result")
        if record["status"]=="void":
            if (not record.get("void_reason") or
                not any(match_ledger["records"][str(p["id"])].get("status")=="void"
                        for p in picks)):
                raise ValueError("Basket marked void without void fixture")
        verified+=1
    return {"verified_baskets":verified,"structural_errors":0}


def report(archive,now=None):
    values=list(archive["records"].values())
    done=[r for r in values if r.get("status")=="settled"]
    pending=[r for r in values if r.get("status")=="pending"]
    void=[r for r in values if r.get("status")=="void"]
    wins=sum(r["winning"] for r in done)
    histogram={str(i):sum(r.get("hits")==i for r in done) for i in range(4)}
    overdue=0
    if now is not None:
        if now.tzinfo is None:raise ValueError("UTC-aware reporting clock required")
        for record in pending:
            last=max(_utc(p["kickoff"]) for p in record["picks"])
            if last+timedelta(hours=4)<now:
                overdue+=1
    return {"format":"mrx-top3-prospective-summary-v1","research_only":True,
            "published":False,"baskets_created":len(values),
            "pending_baskets":len(pending),"void_baskets":len(void),
            "overdue_unsettled_baskets":overdue,
            "settled_baskets":len(done),"baskets_with_at_least_one_hit":wins,
            "winning_basket_rate":round(wins/len(done),6) if done else None,
            "selected_match_count":3*len(values),
            "settled_selected_match_hits":sum(r["hits"] for r in done),
            "settled_hit_distribution":histogram,
            "no_guarantee":True}
