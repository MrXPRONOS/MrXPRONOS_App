#!/usr/bin/env python3
"""BSD V2 -> data.json du site : uniquement marchés buts/résultat, sans SportData.

Invariant: un pronostic déjà exposé ne change jamais de sélection.
On préserve l'historique BSD (14 jours), met à jour scores et validations.
Le site est servi par GitHub Pages depuis data.json à la racine.
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE, _read_json
from bsd_h2h import _utc, _valid_score
from bsd_markets import candidates_from_goals, realized
from bsd_v2_core import V2History, fit_rho_2024, predict_v2, fixture_datetime
from bsd_v2_policies import fit_policy
from bsd_v2_odds import fetch_event_odds

SITE_FILE = Path("data.json")
HISTORY_DAYS = 14
FUTURE_DAYS = 2
MIN_BSD_ODDS = 1.20
EXCLUDED_SELECTIONS = frozenset({'UNDER_45'})

def team_name(item, side):
    value=item.get(side+"_team")
    if isinstance(value,dict): return str(value.get("name") or "Equipe")
    return str(value or "Equipe")


def team_logo(item, side):
    for attr in (side+"_logo",side+"_team_logo",side+"_logo_url"):
        val=item.get(attr)
        if isinstance(val,str) and val.startswith(("https://","http://")):return val
    team=item.get(side+"_team")
    if isinstance(team,dict):
        for attr in ("logo","image"):
            val=team.get(attr)
            if isinstance(val,str) and val.startswith(("https://","http://")):return val
    return ""


def to_site(p, fixture):
    pred=p["prediction"]
    kick=fixture_datetime(fixture)
    prob=round(pred["probability"]*100,1)
    result={
        "id":"bsd:"+str(fixture["id"]), "source":"bsd",
        "source_event_id":fixture["id"],"date":kick.date().isoformat(),
        "event_date":kick.isoformat(),
        "home_team":team_name(fixture,"home"),"away_team":team_name(fixture,"away"),
        "home_team_id":p["home_team_id"],"away_team_id":p["away_team_id"],
        "home_logo":team_logo(fixture,"home"),"away_logo":team_logo(fixture,"away"),
        "league":str(p.get("league") or fixture.get("league_name") or "Football"),
        "league_id":p.get("league_id"),
        "category":p["category"],"badge":"BSD V2",
        "status":"notstarted","is_finished":False,"home_score":None,"away_score":None,
        "verified_prediction":False,"verified_double":False,
        "prediction":{
            "type":pred["name"],"label":pred["name"],"market":pred["market"],
            "selection_key":pred["key"],"market_code":pred["internal_market_code"],
            "outcome":pred["outcome"],"line":pred["line"],
            "confidence":prob,"double_chance":pred["outcome"] if pred["market"]=="double_chance" else None,
            "fair_odds":pred["fair_odds"],"odds":pred["bookmaker_odds"],
            "model_version":p["model_version"],
            "odds_source":pred.get("odds_source"),
            "odds_updated_at":pred.get("odds_updated_at"),
        },
        "model_version":p["model_version"], "final_score":prob,"xpronos_score":prob,
        "generated_at":p.get("prediction_generated_at") or datetime.now(timezone.utc).isoformat(),
    }
    return result


def eligible_previous(data,now):
    if not isinstance(data,dict):return {}
    earliest=now-timedelta(days=HISTORY_DAYS)
    result={}
    for m in data.get("matches",[]):
        if not isinstance(m,dict) or str(m.get("source","")).lower()!="bsd":
            continue
        if not m.get("prediction",{}).get("selection_key"):continue
        try: dt=_utc(m["event_date"])
        except (ValueError,TypeError,KeyError):continue
        if dt<earliest or dt>now+timedelta(days=3):continue
        # Preserve immutable market choices and stable match ids.
        result[str(m.get("source_event_id",str(m.get("id","")).removeprefix("bsd:")))]=m
    return result


def update_settlement(row,event):
    if str(event.get("status","")).lower()!="finished":return row
    h,a=_valid_score(event.get("home_score")),_valid_score(event.get("away_score"))
    if h is None or a is None:return row
    if _utc(event["event_date"])!=_utc(row["event_date"]):return row
    key=row["prediction"].get("selection_key")
    candidates={x.key:x for x in candidates_from_goals(1.3,1.1)}
    if key not in candidates:return row
    correct=bool(realized(candidates[key],h,a))
    row=dict(row)
    row.update({"status":"finished","is_finished":True,"home_score":h,
                "away_score":a,"verified_prediction":correct,
                "verified_double":correct})
    return row


def assemble(existing, fixtures, history, *, now, calibration, policy, rho,
             odds_fetcher=None, max_odds_requests=25):
    saved=eligible_previous(existing,now)
    # Conserver uniquement les anciens événements TERMINÉS pour le bilan :
    # les anciens pronostics à venir sans cote ou Under 4,5 sont retirés.
    saved={key:row for key,row in saved.items()
           if str(row.get("status","")).lower()=="finished"
           and row.get("prediction",{}).get("selection_key") not in EXCLUDED_SELECTIONS}
    index=V2History(history)
    stats=Counter()
    by_id={str(f["id"]):f for f in fixtures if isinstance(f,dict) and f.get("id") is not None}
    result=[]
    for event_id,row in saved.items():
        event=by_id.get(event_id)
        result.append(update_settlement(row,event) if event else row)
    known=set(saved)
    for f in fixtures:
        if not isinstance(f,dict) or f.get("id") is None:continue
        eid=str(f["id"])
        if eid in known:continue
        try: kickoff=fixture_datetime(f)
        except (ValueError,TypeError):continue
        if kickoff<=now or kickoff>now+timedelta(days=FUTURE_DAYS):continue
        if str(f.get("status") or "").lower() not in ("notstarted","upcoming"):continue
        if not odds_fetcher:
            stats["no_odds_provider"] += 1
            continue
        if stats["odds_attempts"] >= max_odds_requests:
            stats["odds_budget_exhausted"] += 1
            continue
        stats["odds_attempts"] += 1
        try:
            quotes, diagnostics = odds_fetcher(f, now)
        except Exception as exc:
            stats["odds_errors"] += 1
            print("BSD_ODDS_UNAVAILABLE", f["id"], type(exc).__name__)
            continue
        valid_quotes = {
            code: quote for code,quote in quotes.items()
            if isinstance(quote,dict) and code != "OU_4.5_UNDER_FT"
            and quote.get("origin") in ("bsd_consensus","bsd_bookmaker")
            and isinstance(quote.get("odds"), (int,float))
            and not isinstance(quote.get("odds"),bool)
            and MIN_BSD_ODDS <= quote["odds"] <= 100
        }
        if not valid_quotes:
            stats["no_qualified_bsd_odds"] += 1
            continue
        prediction,reason=predict_v2(
            f,index,calibration=calibration,quality_policy=policy,
            rho=rho,clock=now,mode="reliability",
            odds_by_market={code: quote["odds"] for code,quote in valid_quotes.items()},
            require_odds=True,min_odds=MIN_BSD_ODDS,excluded_keys=EXCLUDED_SELECTIONS,
        )
        if prediction is None:
            stats[reason]+=1
            continue
        selected_code = prediction["prediction"]["internal_market_code"]
        quote = valid_quotes.get(selected_code)
        if quote is None:
            stats["selection_without_verified_odds"] += 1
            continue
        prediction["prediction"]["bookmaker_odds"] = quote["odds"]
        prediction["prediction"]["odds_source"] = quote["origin"]
        prediction["prediction"]["odds_updated_at"] = quote["updated_at"]
        prediction["prediction_generated_at"]=now.isoformat()
        stats["odds_verified"] += 1
        result.append(to_site(prediction,f))
        known.add(eid)
        stats["created"]+=1
    result.sort(key=lambda r:(str(r.get("event_date","")),str(r.get("id",""))))
    # Un flux BSD vide est préférable au maintien de pronostics SportData périmés.
    output={
        "source":"bsd","model_version":"bsd-v2-isolated",
        "generated_at":now.isoformat(),"matches":result,
        "bookmakers":existing.get("bookmakers",[]) if isinstance(existing,dict) else [],
        "diagnostics":{"total":len(result),"rejections":dict(stats)},
    }
    return output


def fetch_date_range(client,start,end):
    seen={}
    day=start
    while day<=end:
        page=client.list_events(day,day,max_pages=12,ttl=0)
        if not page.complete:
            raise RuntimeError("BSD incomplete for %s (%s/%s)"%(day,len(page.events),page.total_reported))
        for e in page.events:
            if isinstance(e,dict) and e.get("id") is not None:seen[str(e["id"])]=e
        day+=timedelta(days=1)
    return list(seen.values())


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default=str(SITE_FILE))
    p.add_argument("--max-requests",type=int,default=140)
    p.add_argument("--max-odds-events",type=int,default=350)
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    historic=_read_json(MATCHES_FILE,None)
    if not isinstance(historic,list) or not historic:
        p.error("Archive BSD absente ou invalide")
    existing=_read_json(Path(args.output),{})
    client=BSDClient(max_requests=args.max_requests)
    fixtures=fetch_date_range(client,(now-timedelta(days=HISTORY_DAYS)).date(),
                              (now+timedelta(days=FUTURE_DAYS)).date())
    index=V2History(historic)
    rho,_=fit_rho_2024(index)
    cal,policy,diag=fit_policy(index,rho=rho)
    def odds_fetcher(event, captured):
        return fetch_event_odds(client,int(event["id"]),kickoff=fixture_datetime(event),
                                captured_at=captured,bookmaker_slug="consensus")
    output=assemble(existing,fixtures,historic,now=now,calibration=cal,policy=policy,
                    rho=rho,odds_fetcher=odds_fetcher,max_odds_requests=args.max_odds_events)
    output["diagnostics"].update({"api_calls":client.requests_made,
                                  "quality_validation":diag,"rho":rho})
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".tmp")
    temp.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(dest)
    print("BSD_V2_SITE:",json.dumps({"matches":len(output["matches"]),
         "new":output["diagnostics"]["rejections"].get("created",0),
         "http_calls":client.requests_made,"output":str(dest)}))


if __name__=="__main__":
    main()
