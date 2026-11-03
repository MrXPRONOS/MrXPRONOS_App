"""Read-only BSD V2 market analyses with honest INDICATIVE prices 1.40-2.00.

This stream is NOT the Pro/VIP publication feed:
- no relaxed Pro/VIP gates;
- no fake bookmaker price or value claim;
- never passed to Telegram, recommendation feed or immutable pick ledger;
- all model inputs pre-kickoff and calibrated on 2024-2025 only.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from math import isfinite

from bsd_v2_core import (
    estimate_goals,fixture_datetime,markets_from_matrix,score_matrix,league_key,
)
from bsd_v2_btts import btts_candidates
from bsd_v2_estimated_odds import DEFAULT_OVERROUND,ESTIMATED_SOURCE
from bsd_v2_labels import market_label
from bsd_v2_over_under import adjust_candidates as adjust_totals,uncertainty as total_uncertainty
from bsd_v2_double_chance import (
    adjust_candidates as adjust_dc,uncertain as dc_uncertain,score_probs
)

MIN_ANALYSIS_ODDS = 1.40
MAX_ANALYSIS_ODDS = 2.00
MAX_PER_FIXTURE = 2
MAX_PER_DAY = 40
EXCLUDED_KEYS = frozenset(("12","UNDER_45"))

def honest_indicative_price(p,margin=DEFAULT_OVERROUND):
    """A mathematical price only; NEVER raise/lower the margin to hit a floor."""
    if type(p) not in (int,float) or not isfinite(float(p)) or not 0<p<1:
        return None
    if not 0<=margin<=.2:
        return None
    price=round(1/(float(p)*(1+margin)),3)
    return price if MIN_ANALYSIS_ODDS<=price<=MAX_ANALYSIS_ODDS else None

def _considered_candidates(fixture,index,rho,features,calibration,btts_model,
                            total_model,dc_model):
    matrix=score_matrix(features["home"],features["away"],rho)
    candidates=markets_from_matrix(matrix)
    # Match actual production specialist transformations, not the legacy
    # Poisson-only probabilities. Exclude volatile markets as production does.
    if total_model is not None:
        candidates=adjust_totals(fixture,index,candidates,total_model)
        risk=total_uncertainty(fixture,index,total_model,
                               features["home"]+features["away"])
        if risk is not None:
            candidates=[c for c in candidates if c.family!="goals"]
    if btts_model is not None:
        candidates=btts_candidates(fixture,index,candidates,btts_model)
    if dc_model is not None:
        baseline=score_probs(candidates)
        unstable=dc_uncertain(fixture,index,dc_model,baseline)
        candidates=adjust_dc(fixture,index,candidates,dc_model,
                getattr(calibration,"outcome_calibration",None))
        if unstable:
            candidates=[c for c in candidates if c.family!="double_chance"]
    return candidates

def _select_for_fixture(items):
    """Prefer one BTTS and one OTHER family, never both contradictory BTTS sides."""
    ranked=sorted(items,key=lambda r:(-r["conservative_probability"],
                                      -r["model_probability"],r["market_code"]))
    btts=next((r for r in ranked if r["selection_key"] in ("BTTS_YES","BTTS_NO")),None)
    selected=[btts] if btts else []
    for row in ranked:
        if len(selected)>=MAX_PER_FIXTURE:break
        if btts is not None and row["selection_key"]==btts["selection_key"]:
            continue
        if selected and row["market_family"]==selected[0]["market_family"]:
            continue
        selected.append(row)
    return selected

def build_market_range_analyses(fixtures,index,*,now,rho,calibration,quality_policy,
                                btts_model=None,total_model=None,dc_model=None,
                                max_per_day=MAX_PER_DAY):
    if not 1<=max_per_day<=120:raise ValueError("Invalid analyses daily cap")
    stats=Counter()
    by_day=defaultdict(list)
    candidates=sorted(
        (f for f in fixtures if isinstance(f,dict) and f.get("id") is not None),
        key=lambda f:(str(f.get("event_date") or ""),str(f.get("id"))))
    for f in candidates:
        if str(f.get("status") or "").lower() not in ("notstarted","upcoming"):
            continue
        try: kickoff=fixture_datetime(f)
        except (ValueError,TypeError):continue
        if kickoff<=now or kickoff>now+timedelta(days=2):
            continue
        stats["future_fixtures"]+=1
        day=kickoff.date().isoformat()
        if len(by_day[day])>=max_per_day:
            continue
        try:
            feat,why=estimate_goals(f,index)
            if feat is None:
                stats["missing_features"]+=1
                continue
            if quality_policy is not None and quality_policy.check_fixture(feat):
                stats["fixture_quality_rejected"]+=1
                continue
            options=_considered_candidates(f,index,rho,feat,calibration,
                                          btts_model,total_model,dc_model)
            qualified=[]
            for c in options:
                if c.key in EXCLUDED_KEYS:continue
                _lower,p,n=(calibration.score(c) if calibration is not None
                             else (c.probability,c.probability,0))
                price=honest_indicative_price(p)
                if price is None:continue
                # Same independent market-quality validation as production.
                mock={"candidate":c,"calibrated_probability":p,
                      "ranking_confidence":p}
                if quality_policy is not None and quality_policy.check_market(mock):
                    continue
                uncertainty=(.016 if c.family=="btts" else
                             .014 if c.family=="goals" else
                             .010 if c.family=="double_chance" else .012)
                conservative=max(0.,p-uncertainty)
                qualified.append({
                    "id":"bsd-market-analysis:"+str(f["id"])+":"+c.key,
                    "source_event_id":str(f["id"]),
                    "event_date":kickoff.isoformat(),
                    "date":day,
                    "home_team":f.get("home_team") if isinstance(f.get("home_team"),str)
                                else (f.get("home_team") or {}).get("name") if isinstance(f.get("home_team"),dict) else "",
                    "away_team":f.get("away_team") if isinstance(f.get("away_team"),str)
                                else (f.get("away_team") or {}).get("name") if isinstance(f.get("away_team"),dict) else "",
                    "league":f.get("league_name") or f.get("competition_name"),
                    "market_family":c.family,
                    "selection_key":c.key,
                    "market_code":c.market_code,
                    "market_label":market_label(c.key,c.label),
                    "model_probability":round(p,6),
                    "conservative_probability":round(conservative,6),
                    "calibration_samples":n,
                    "fair_odds":round(1/p,4),
                    "odds":price,
                    "odds_source":ESTIMATED_SOURCE,
                    "estimated_odds":True,
                    "overround_assumption":DEFAULT_OVERROUND,
                    "price_method":"probability_calibrated_plus_fixed_6pct",
                    "not_an_executable_bookmaker_quote":True,
                    "analysis_only":True,
                    "category":"market_analysis",
                    "recommendation_eligible":False,
                    "prediction_eligible":False,
                    "do_not_send_to_telegram":True,
                    "status":"upcoming",
                })
            chosen=_select_for_fixture(qualified)
            if chosen:
                by_day[day].extend(chosen[:max(0,max_per_day-len(by_day[day]))])
                stats["fixtures_with_analyses"]+=1
        except (ValueError,TypeError,OverflowError,KeyError) as exc:
            stats["invalid_fixture_or_model"]+=1
            continue
    rows=[r for day in sorted(by_day) for r in by_day[day]]
    stats["analyses_count"]=len(rows)
    stats["btts_analyses_count"]=sum(r["selection_key"].startswith("BTTS_") for r in rows)
    return rows,dict(stats)
