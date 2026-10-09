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
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model as fit_dc_model
from bsd_v2_odds import fetch_event_odds
from bsd_v2_estimated_odds import ESTIMATED_SOURCE, valid_standalone_prediction, price_selected_market
from bsd_v2_labels import normalize_match,market_label
from bsd_v2_assets import image_fields

SITE_FILE = Path("data.json")
HISTORY_DAYS = 14
FUTURE_DAYS = 2
MIN_BSD_ODDS = 1.20
MIN_COMBO_ODDS = 1.01
EXCLUDED_SELECTIONS = frozenset({'UNDER_45'})

def league_name(item):
    for key in ("league_name","competition_name","tournament_name"):
        value=item.get(key)
        if isinstance(value,dict):value=value.get("name")
        if isinstance(value,str) and value.strip() and value.strip().casefold() not in ("football","soccer"):
            return value.strip()
    league=item.get("league")
    if isinstance(league,dict):league=league.get("name")
    if isinstance(league,str) and league.strip() and league.strip().casefold() not in ("football","soccer"):
        return league.strip()
    return None


def resolve_league_names(client, fixtures, output, existing):
    """Enrich only missing competitions using authentic BSD names.

    Never invent a competition from team names or an unverified league ID.
    Uses limited paginated league catalog requests; failure is non-blocking.
    """
    names={}
    for item in (existing.get("matches",[]) if isinstance(existing,dict) else []):
        if not isinstance(item,dict):continue
        lid=item.get("league_id")
        name=league_name(item)
        if lid is not None and name:names[str(lid)]=name
    for item in fixtures:
        if not isinstance(item,dict):continue
        lid=item.get("league_id")
        name=league_name(item)
        if lid is not None and name:names[str(lid)]=name
    pending={str(m.get("league_id")) for m in output["matches"]
             if not league_name(m) and m.get("league_id") is not None}
    if pending-set(names):
        try:
            for offset in range(0,800,100):
                payload=client.get_json("/leagues/",{"limit":100,"offset":offset},ttl=3600)
                rows=(payload if isinstance(payload,list) else
                      payload.get("results",[]) if isinstance(payload,dict) else [])
                if not isinstance(rows,list):break
                for row in rows:
                    if not isinstance(row,dict):continue
                    ident=row.get("id")
                    label=league_name(row) or (
                        row.get("name") if isinstance(row.get("name"),str)
                        and row["name"].strip().casefold() not in ("football","soccer")
                        else None)
                    if ident is not None and label:names[str(ident)]=label.strip()
                if pending.issubset(names) or len(rows)<100:break
        except Exception as exc:
            print("BSD_LEAGUE_NAME_FALLBACK",type(exc).__name__)
    # Some BSD catalog pages are incomplete. Fall back to documented
    # /leagues/{id}/ detail endpoint for the remaining IDs only.
    from bsd_v2_assets import valid_id
    for lid in sorted(pending-set(names)):
        number=valid_id(lid)
        if number is None:
            continue
        try:
            detail=client.get_json(f"/leagues/{number}/",ttl=3600)
            if isinstance(detail,dict):
                label=league_name(detail)
                if label is None:
                    name=detail.get("name")
                    if isinstance(name,str) and name.strip().casefold() not in ("football","soccer"):
                        label=name.strip()
                if label:names[lid]=label
        except Exception as exc:
            print("BSD_LEAGUE_DETAIL_UNAVAILABLE",lid,type(exc).__name__)
    fixed=0
    for match in output["matches"]:
        if not league_name(match):
            label=names.get(str(match.get("league_id")))
            if label:
                match["league"]=label
                fixed+=1
    return fixed


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
        "home_logo":image_fields(fixture)["home_logo"],"away_logo":image_fields(fixture)["away_logo"],
        "league_logo":image_fields(fixture)["league_logo"],
        "league":league_name(fixture) or league_name(p),
        "league_id":p.get("league_id"),
        "category":p["category"],"badge":"BSD V2",
        "status":"notstarted","is_finished":False,"home_score":None,"away_score":None,
        "verified_prediction":False,"verified_double":False,
        "prediction":{
            "type":market_label(pred["key"],pred["name"]),"label":market_label(pred["key"],pred["name"]),"market":pred["market"],
            "selection_key":pred["key"],"market_code":pred["internal_market_code"],
            "outcome":pred["outcome"],"line":pred["line"],
            "confidence":prob,"double_chance":pred["outcome"] if pred["market"]=="double_chance" else None,
            "fair_odds":pred["fair_odds"],"odds":pred["bookmaker_odds"],
            "model_version":p["model_version"],
            "odds_source":pred.get("odds_source"),
            "estimated_odds":pred.get("odds_source")==ESTIMATED_SOURCE,
            "odds_method":pred.get("odds_method"),
            "overround_assumption":pred.get("overround_assumption"),
            "odds_updated_at":pred.get("odds_updated_at"),
        },
        "model_version":p["model_version"], "final_score":prob,"xpronos_score":prob,
        "generated_at":p.get("prediction_generated_at") or datetime.now(timezone.utc).isoformat(),
        "combo_only":bool(p.get("combo_only",False)),
    }
    # Optional strictly low-priced market for the combined-coupon engine.
    # This is not an extra standalone prediction or a second team fixture.
    combo=p.get("combo_selection")
    if combo:
        result["combo_prediction"]={
          "type":market_label(combo["key"],combo["name"]),"label":market_label(combo["key"],combo["name"]),
          "market":combo["market"],"outcome":combo["outcome"],
          "line":combo["line"],"selection_key":combo["key"],
          "market_code":combo["market_code"],
          "confidence":round(combo["probability"]*100,1),
          "odds":combo["odds"],"odds_source":combo["odds_source"],
          "odds_updated_at":combo.get("odds_updated_at")}
    extras=p.get("secondary_selections") or []
    if extras:
        result["predictions"]=[result["prediction"]]+[
          {"type":market_label(m["key"],m["name"]),"label":market_label(m["key"],m["name"]),"market":m["market"],
           "selection_key":m["key"],"market_code":m["market_code"],
           "outcome":m["outcome"],"line":m["line"],
           "confidence":round(m["probability"]*100,1),
           "fair_odds":round(1/m["probability"],4),
           "odds":m["odds"],"odds_source":m["odds_source"],
           "estimated_odds":m["odds_source"]==ESTIMATED_SOURCE,
           "odds_method":m.get("odds_method"),
           "overround_assumption":m.get("overround_assumption"),
           "odds_updated_at":m.get("odds_updated_at"),
           "model_version":p["model_version"]}
          for m in extras]
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
             odds_fetcher=None, max_odds_requests=25, btts_model=None, total_model=None, dc_model=None):
    saved=eligible_previous(existing,now)
    # Ne pas perdre les pronostics déjà publiés : une sélection future reste
    # immuable pendant les exécutions quotidiennes (site ET Telegram).
    # On garde aussi les événements passés en attente de score BSD final.
    # Seuls les coupons invalides / marchés bannis sont supprimés.
    saved={key:row for key,row in saved.items()
           if valid_standalone_prediction(row.get("prediction"),row.get("combo_only",False))}
    index=V2History(history)
    stats=Counter()
    by_id={str(f["id"]):f for f in fixtures if isinstance(f,dict) and f.get("id") is not None}
    result=[]
    detailed=[]
    for event_id,row in saved.items():
        event=by_id.get(event_id)
        result.append(update_settlement(row,event) if event else row)
    known=set(saved)
    for f in fixtures:
        if not isinstance(f,dict) or f.get("id") is None:continue
        eid=str(f["id"])
        if eid in known:continue
        entry={"event_id":eid,"home_team":team_name(f,"home"),"away_team":team_name(f,"away"),
               "event_date":f.get("event_date"),"quotes":[],"considered":[],"status":"rejected","reason":None}
        detailed.append(entry)
        try: kickoff=fixture_datetime(f)
        except (ValueError,TypeError):
            entry["reason"]="invalid_kickoff"
            continue
        if kickoff<=now or kickoff>now+timedelta(days=FUTURE_DAYS):
            entry["reason"]="outside_upcoming_window"
            continue
        if str(f.get("status") or "").lower() not in ("notstarted","upcoming"):
            entry["reason"]="not_upcoming"
            continue
        # Phase 1 : choisir les pronostics SANS consulter les cotes.
        # Le choix de l'option dépend des données, de la probabilité calibrée
        # et des contrôles qualité, jamais de la disponibilité BSD.
        market_audit=[]
        entry["considered"]=market_audit
        prediction,reason=predict_v2(
            f,index,calibration=calibration,quality_policy=policy,
            rho=rho,clock=now,mode="reliability",
            odds_by_market={},require_odds=False,
            excluded_keys=EXCLUDED_SELECTIONS,
            btts_model=btts_model,total_model=total_model,dc_model=dc_model,
            market_audit=market_audit)
        if prediction is None:
            entry["reason"]=reason
            stats[reason]+=1
            continue
        # Phase 2 : enrichir les choix figés par une cote BSD ou estimée.
        quotes={}
        if odds_fetcher and stats["odds_attempts"] < max_odds_requests:
            stats["odds_attempts"]+=1
            try:
                quotes,_diagnostics=odds_fetcher(f,now)
                if not isinstance(quotes,dict):
                    quotes={}
            except Exception as exc:
                stats["odds_errors"]+=1
                print("BSD_ODDS_UNAVAILABLE",f["id"],type(exc).__name__)
        else:
            stats["odds_unavailable_or_budget"]+=1
        entry["quotes"]=[{"market":code,"odds":q.get("odds"),"source":q.get("origin")}
                          for code,q in sorted(quotes.items()) if isinstance(q,dict)]
        chosen=price_selected_market(prediction["prediction"],quotes,now=now)
        if chosen is None:
            entry["reason"]="chosen_market_unpriceable"
            stats[entry["reason"]]+=1
            continue
        # Une option à faible cote réelle reste réservée aux combinés.
        combo_only=(chosen["odds_source"]!=ESTIMATED_SOURCE
                    and chosen["bookmaker_odds"]<MIN_BSD_ODDS)
        prediction["prediction"]=chosen
        prediction["combo_only"]=combo_only
        prediction["prediction_generated_at"]=now.isoformat()
        if chosen["odds_source"]==ESTIMATED_SOURCE:
            stats["model_estimated"]+=1
        else:
            stats["bsd_quoted"]+=1
        # Une deuxième option n'est affichée que si elle est déjà qualifiée,
        # d'une autre famille et indépendamment cotable.
        # On ne la substitue jamais à l'option principale.
        additional=[]
        if not combo_only:
            for candidate in prediction.get("ranked_candidates",[]):
                if candidate["key"]==chosen["key"] or candidate["market"]==chosen["market"]:
                    continue
                if candidate.get("passes_quality_policy") is not True:
                    continue
                secondary=price_selected_market(candidate,quotes,now=now)
                if secondary is None or secondary["odds"]<MIN_BSD_ODDS:
                    continue
                additional.append(secondary)
                break
        prediction["secondary_selections"]=additional
        # Les combinés utilisent toujours uniquement des cotes BSD réelles.
        low_quotes={code:q for code,q in quotes.items()
                    if isinstance(q,dict) and q.get("origin") in ("bsd_consensus","bsd_bookmaker")
                    and type(q.get("odds")) in (int,float) and MIN_COMBO_ODDS<=q["odds"]<1.50}
        if low_quotes:
            combo_choice,_combo_reason=predict_v2(
                f,index,calibration=calibration,quality_policy=policy,
                rho=rho,clock=now,mode="reliability",
                odds_by_market={code:q["odds"] for code,q in low_quotes.items()},
                require_odds=True,min_odds=MIN_COMBO_ODDS,
                allow_combo_prices=True,excluded_keys=EXCLUDED_SELECTIONS,
                btts_model=btts_model,total_model=total_model,dc_model=dc_model)
            if combo_choice:
                leg=combo_choice["prediction"]
                verified=low_quotes[leg["internal_market_code"]]
                prediction["combo_selection"]={
                    "name":leg["name"],"market":leg["market"],
                    "outcome":leg["outcome"],"line":leg["line"],
                    "key":leg["key"],"market_code":leg["internal_market_code"],
                    "probability":leg["probability"],"odds":verified["odds"],
                    "odds_source":verified["origin"],
                    "odds_updated_at":verified.get("updated_at")}
        entry["status"]="published"
        entry["reason"]=None
        entry["selections"]=[prediction["prediction"]["key"]]+[v["key"] for v in additional]
        stats["priced_selected"] += 1
        result.append(to_site(prediction,f))
        known.add(eid)
        stats["created"]+=1
    result=[normalize_match(r) for r in result]
    for row in result:
        row.update(image_fields(row))
    result.sort(key=lambda r:(str(r.get("event_date","")),str(r.get("id",""))))
    # Un flux BSD vide est préférable au maintien de pronostics SportData périmés.
    output={
        "source":"bsd","model_version":"bsd-v2-isolated",
        "generated_at":now.isoformat(),"matches":result,
        "bookmakers":existing.get("bookmakers",[]) if isinstance(existing,dict) else [],
        "diagnostics":{"total":len(result),"rejections":dict(stats),
                       "fixture_details":detailed},
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
    btts_model,btts_info=fit_btts_model(index,rho=rho)
    total_model,total_info=fit_total_model(index,rho=rho)
    dc_model,dc_info=fit_dc_model(index,rho=rho)
    cal,policy,diag=fit_policy(index,rho=rho,btts_model=btts_model,total_model=total_model,dc_model=dc_model)
    def odds_fetcher(event, captured):
        return fetch_event_odds(client,int(event["id"]),kickoff=fixture_datetime(event),
                                captured_at=captured,bookmaker_slug="consensus")
    output=assemble(existing,fixtures,historic,now=now,calibration=cal,policy=policy,
                    rho=rho,odds_fetcher=odds_fetcher,max_odds_requests=args.max_odds_events,
                    btts_model=btts_model,total_model=total_model,dc_model=dc_model)
    leagues_resolved=resolve_league_names(client,fixtures,output,existing)
    output["diagnostics"]["leagues_resolved"]=leagues_resolved
    output["diagnostics"].update({"api_calls":client.requests_made,
                                  "quality_validation":diag,"rho":rho,
                                  "btts_training":btts_info,"totals_training":total_info,"double_chance_training":dc_info,
                                  "market_family_penalties":policy.family_uncertainty_adjustments()})
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".tmp")
    temp.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(dest)
    report=dest.parent/"bsd"/"rejections_report.json"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({"generated_at":now.isoformat(),
      "summary":output["diagnostics"]["rejections"],
      "rows":output["diagnostics"]["fixture_details"]},ensure_ascii=False,indent=2),encoding="utf-8")
    print("BSD_V2_SITE:",json.dumps({"matches":len(output["matches"]),
         "new":output["diagnostics"]["rejections"].get("created",0),
         "http_calls":client.requests_made,"output":str(dest)}))


if __name__=="__main__":
    main()
