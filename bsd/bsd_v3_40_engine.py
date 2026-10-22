"""BSD V3 shadow evaluator: clone the LIVE BSD V2 maths without changing production.

Uses V2History point-in-time protection, estimated goals, Dixon-Coles matrix,
and already present Elo timeline. No H2H-only or balanced-match exclusion.
All results are UNPUBLISHED analysis artifacts, never sent to Telegram.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json, math

from bsd_h2h import _team_id
from bsd_v2_core import V2History, estimate_goals, score_matrix, fixture_datetime, outcome_scores
from bsd_v2_double_chance import _rating
from bsd_v3_40_markets import probabilities

FORMAT="bsd-v3-40-shadow-v1"

def form_features(index, event):
    """As-of features: never look at games after fixture kickoff."""
    at=fixture_datetime(event)
    def side_features(side,venue):
        team=_team_id(event,side)
        rows=index.team(team,at,limit=10) if team else []
        def aggregate(seq):
            w=d=l=gf=ga=0
            for e in seq:
                scores=outcome_scores(e)
                if scores is None:continue
                first = _team_id(e,"home")==team
                scored,conceded = scores if first else scores[::-1]
                gf+=scored;ga+=conceded
                w+=scored>conceded;l+=scored<conceded;d+=scored==conceded
            n=len(seq)
            return {"samples":n,"wins":w,"draws":d,"losses":l,
                    "goals_for_per_match":round(gf/n,4) if n else None,
                    "goals_against_per_match":round(ga/n,4) if n else None}
        return {"last_5":aggregate(rows[:5]),"last_10":aggregate(rows),
                "venue":aggregate(index.team(team,at,venue=venue,limit=10) if team else []),
                "elo_asof":round(_rating(index,team,at),2) if team else None}
    return {"home":side_features("home","home"),"away":side_features("away","away"),
            "as_of":at.isoformat()}

def _utc(value):
    if isinstance(value,datetime):
        d=value
    else:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("Use timezone aware UTC timestamps")
    return d.astimezone(timezone.utc)

def quoted_value(row, quote, *, now):
    """Reject stale/unverified/theoretical prices; DNB push-aware EV."""
    if not isinstance(quote,dict) or quote.get("verified") is not True:
        return None
    if quote.get("estimated") or quote.get("source") not in ("bsd_consensus","verified_bookmaker"):
        return None
    try:
        odds=float(quote["odds"])
        captured=_utc(quote["captured_at"])
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
    if not math.isfinite(odds) or odds<=1.0 or captured>now or (now-captured).total_seconds()>7200:
        return None
    p=row["probability"]; q=row["lose_probability"]
    ev=p*(odds-1)-q
    return {"odds":odds,"source":quote["source"],"captured_at":captured.isoformat(),
            "expected_return_per_unit":round(ev,6)}

def rank_markets(markets, quotes, *, now, validation=None, min_edge=0.04):
    """Shadow-only recommendations: REAL quote AND adequate out-of-time evaluation."""
    validation=validation or {}
    ranked=[]
    for raw in markets:
        row=dict(raw)
        q=quoted_value(row,(quotes or {}).get(row["key"]),now=now)
        check=validation.get(row["key"],{})
        # A test set is mandatory: no odds or no independent validation => observation.
        vetted=(check.get("samples",0)>=100 and check.get("test_brier") is not None
                and check.get("baseline_brier") is not None
                and check["test_brier"]<=check["baseline_brier"]
                and check.get("chronological_holdout") is True)
        row["quote"]=q
        row["evaluation_passed"]=bool(vetted)
        row["recommendation_eligible"]=bool(q and vetted and q["expected_return_per_unit"]>=min_edge)
        if row["recommendation_eligible"]:ranked.append(row)
    # Do not recommend multiple correlated positions on the same game by default.
    ranked.sort(key=lambda x:(-x["quote"]["expected_return_per_unit"],x["key"]))
    return ranked[:1]

def generate_shadow(events, history, *, now, rho=0.,quotes=None,validation=None):
    now=_utc(now)
    if not -.13<=rho<=.13:raise ValueError("Unvalidated rho")
    index=V2History(history)
    data=[]
    rejected={}
    for event in events:
        try:
            if event.get("id") is None:
                reason="missing_event_id"
            elif str(event.get("status","")).lower() not in ("upcoming","notstarted"):
                reason="not_upcoming"
            elif fixture_datetime(event)<=now:
                reason="already_started"
            else:
                estimate, reason=estimate_goals(event,index)
                if estimate is not None:
                    matrix=score_matrix(estimate["home"],estimate["away"],rho=rho)
                    market_rows=probabilities(matrix)
                    event_id=str(event["id"])
                    recommended=rank_markets(market_rows,(quotes or {}).get(event_id,{}),
                                             now=now,validation=validation)
                    data.append({
                        "id":"bsd:"+event_id,"source_event_id":event["id"],
                        "event_date":fixture_datetime(event).isoformat(),
                        "teams":{"home_id":_team_id(event,"home"),"away_id":_team_id(event,"away"),
                                 "home":event.get("home_team"),"away":event.get("away_team")},
                        "expected_goals":estimate,"rho":rho,
                        "score_model":"Dixon-Coles" if rho else "Poisson",
                        "features_asof":form_features(index,event),
                        "markets":market_rows,"recommended_shadow_only":recommended,
                        "experimental":True,"published":False,
                        "do_not_send_to_telegram":True
                    })
                    continue
        except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as exc:
            reason="invalid_data_"+type(exc).__name__
        rejected[reason]=rejected.get(reason,0)+1
    # No full historical data in the output: licensed archive remains private.
    artifact={"format":FORMAT,"experimental":True,"published":False,
              "do_not_send_to_telegram":True,"generated_at_utc":now.isoformat(),
              "model":"bsd-v2-clone-plus-v3-market-library",
              "matches":data,"diagnostics":{"received":len(events),"analysed":len(data),
                                             "rejected":rejected,"markets_per_match":40}}
    artifact["fingerprint_sha256"]=sha256(json.dumps(artifact,sort_keys=True,
                                    ensure_ascii=False).encode("utf-8")).hexdigest()
    return artifact
