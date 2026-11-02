"""Comparaison prospective des cotes BSD V2 : calcul indicatif vs fournisseurs indépendants.

Ce diagnostic est strictement en lecture seule : aucune publication, aucun
remplacement de pronostic et aucune modification de data.json / Telegram.

Le modèle choisit d'abord une option. La cote indicative est calculée exactement
avec le module du site et une marge par défaut de 6 % (sans prix extérieur).
Ensuite seulement, les fournisseurs sont interrogés pour le MÊME code marché FT.
Les prix externes doivent être frais, horodatés et antérieurs au coup d'envoi.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median

from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE, _read_json
from bsd_odds_fallback import OddsRouter, ORDER, MAX_COMPARABLE_QUOTE_AGE_SECONDS, utc
from bsd_v2_odds import fetch_event_odds
from bsd_v2_core import V2History, fit_rho_2024, fixture_datetime, predict_v2
from bsd_v2_policies import fit_policy
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model
from bsd_v2_publication_policy import eligible_model_choice
from bsd_v2_estimated_odds import (
    ESTIMATED_SOURCE, DEFAULT_OVERROUND, estimated_quote, price_selected_market,
)
from bsd_v2_guardrails import (
    v21_accept_priced, post_price_value_guard, V21_MIN_OVER15_CONSERVATIVE,
)

SOURCE_NAMES = tuple(ORDER)
ALLOWED_ORIGINS = frozenset(SOURCE_NAMES) | frozenset(("bsd_consensus", "bsd_bookmaker"))


def pure_model_price(prediction, *, now):
    """Reproduit la fonction de cotation du site, SANS l'info fournisseur.

    Ne jamais appeler price_selected_market avec les cotes réelles ici :
    cette fonction afficherait alors leur prix au lieu du prix modèle.
    """
    model = prediction.get("prediction") or {}
    code = model.get("internal_market_code")
    if not code:
        return None, "no_market_code"
    result = price_selected_market(model, {}, now=now)
    if result is None:
        return None, "indicative_price_unavailable_or_below_120"
    if result.get("odds_source") != ESTIMATED_SOURCE or result.get("estimated_odds") is not True:
        return None, "indicative_price_not_model"
    ok, reason = v21_accept_priced(result)
    if not ok:
        return None, reason
    value_guard = post_price_value_guard(result)
    if not value_guard.get("passed"):
        return None, str(value_guard.get("reason") or "value_guard_rejected")
    if result["bookmaker_odds"] < 1.20:
        return None, "site_minimum_odds_120"
    return result, "ok_model_indicative"


def valid_independent_quote(row, *, code, now, kickoff):
    """Last independent validation after the native router's checks."""
    if not isinstance(row, dict) or row.get("origin") not in ALLOWED_ORIGINS:
        return False, "unsupported_origin"
    if not isinstance(code, str) or not code:
        return False, "missing_exact_market_code"
    try:
        price = float(row["odds"])
        updated = utc(row["updated_at"])
        captured = utc(row.get("captured_at"))
    except (KeyError, TypeError, ValueError):
        return False, "incomplete_quote"
    if not (math.isfinite(price) and 1.01 <= price <= 100):
        return False, "invalid_decimal_odds"
    if row.get("quote_timestamp_verified") is False:
        return False, "timestamp_unverified"
    if updated is None or captured is None or now.tzinfo is None or kickoff.tzinfo is None:
        return False, "missing_utc_timestamps"
    if not (updated <= captured < kickoff and
            abs((now - captured).total_seconds()) <= 60 and
            0 <= (captured - updated).total_seconds() <= MAX_COMPARABLE_QUOTE_AGE_SECONDS):
        return False, "stale_or_post_kickoff"
    return True, "ok"


def comparison(model_odds, external_quote, *, code, now, kickoff):
    valid, reason = valid_independent_quote(external_quote, code=code, now=now, kickoff=kickoff)
    if not valid:
        return None, reason
    model_price = float(model_odds)
    real_price = float(external_quote["odds"])
    if not (1.20 <= model_price <= 100 and math.isfinite(model_price)):
        return None, "model_price_not_publishable"
    return {
        "model_odds": round(model_price, 4),
        "provider_odds": round(real_price, 4),
        "absolute_difference": round(real_price - model_price, 4),
        "relative_difference_pct": round(100 * (real_price / model_price - 1), 3),
        "absolute_relative_difference_pct": round(100 * abs(real_price / model_price - 1), 3),
        "provider_implied_probability_pct": round(100 / real_price, 3),
        "model_implied_probability_pct": round(100 / model_price, 3),
        "provider_implied_minus_model_pct_points": round(100 / real_price - 100 / model_price, 3),
        "bookmaker": external_quote.get("bookmaker"),
        "provider_source": external_quote.get("origin"),
        "quote_updated_at": external_quote.get("updated_at"),
        "quote_capture_at": external_quote.get("captured_at"),
        "timestamp_kind": external_quote.get("quote_timestamp_type") or "market_update",
    }, "ok"


def summarize(rows):
    if not rows:
        return {"comparisons": 0, "mean_signed_difference": None, "mean_absolute_difference": None,
                "median_absolute_difference": None, "median_absolute_relative_pct": None,
                "pct_provider_above_model": None, "pct_within_5pct": None,
                "pct_within_10pct": None}
    diffs=[r["absolute_difference"] for r in rows]
    rel=[r["absolute_relative_difference_pct"] for r in rows]
    return {
        "comparisons":len(rows),
        "mean_signed_difference":round(mean(diffs),4),
        "mean_absolute_difference":round(mean(abs(x) for x in diffs),4),
        "median_absolute_difference":round(median(abs(x) for x in diffs),4),
        "median_absolute_relative_pct":round(median(rel),3),
        "pct_provider_above_model":round(100 * sum(x>0 for x in diffs) / len(rows),2),
        "pct_within_5pct":round(100 * sum(x<=5 for x in rel) / len(rows),2),
        "pct_within_10pct":round(100 * sum(x<=10 for x in rel) / len(rows),2),
    }


def choose_upcoming(fixtures, now, horizon_hours, max_fixtures):
    unique={}
    for event in fixtures:
        if not isinstance(event,dict) or event.get("id") is None:
            continue
        try: kickoff=fixture_datetime(event)
        except (ValueError,TypeError,OverflowError):continue
        if (str(event.get("status") or "").lower() not in ("notstarted","upcoming")
                or kickoff <= now + timedelta(minutes=15)
                or kickoff > now + timedelta(hours=horizon_hours)):
            continue
        unique[str(event["id"])]=event
    ordered=sorted(unique.values(),key=lambda e:(str(e.get("event_date")),str(e.get("id"))))
    return ordered[:max_fixtures],len(ordered)


def run(*, client, index, fixtures, now, horizon_hours, max_fixtures, max_model_picks,
        provider_order=SOURCE_NAMES):
    rho, rho_diag=fit_rho_2024(index)
    total_model, _=fit_total_model(index,rho=rho)
    btts_model, _=fit_btts_model(index,rho=rho)
    dc_model, _=fit_model(index,rho=rho)
    cal,policy,fit_diag=fit_policy(index,rho=rho,total_model=total_model,
                                    btts_model=btts_model,dc_model=dc_model)
    selected,available=choose_upcoming(fixtures,now,horizon_hours,max_fixtures)
    stats=Counter()
    status=defaultdict(Counter)
    rows=[]
    unpaired=[]
    # One router per provider so each feed is consulted even if another is available.
    # The production router deliberately stops at the first valid provider;
    # this diagnostic does NOT change that production behavior.
    def bsd_fetch(event, captured):
        quotes, diagnostics = fetch_event_odds(
            client,int(event["id"]),kickoff=fixture_datetime(event),
            captured_at=captured,bookmaker_slug="consensus")
        # The BSD parser already verified the authentic per-market updated_at
        # against this precise fetch timestamp, but does not serialize capture.
        # Preserve capture provenance before the common provider validator.
        for item in quotes.values():
            item["captured_at"]=captured.isoformat()
            item["quote_timestamp_verified"]=True
            item["quote_timestamp_type"]="market_update"
        return quotes, diagnostics
    routers={
        provider:OddsRouter(bsd_fetch,order=(provider,),
                            clock=lambda: datetime.now(timezone.utc))
        for provider in provider_order
    }
    compared_games=0
    for event in selected:
        stats["fixtures_checked"]+=1
        clock=datetime.now(timezone.utc)
        if fixture_datetime(event) <= clock + timedelta(minutes=2):
            stats["skipped_near_kickoff"]+=1
            continue
        selection,reason=predict_v2(event,index,calibration=cal,rho=rho,clock=clock,
                  quality_policy=policy, btts_model=btts_model,
                  total_model=total_model,dc_model=dc_model,
                  excluded_keys={"12","UNDER_45"},
                  selection_conservative_minimums={
                      "OVER_15": V21_MIN_OVER15_CONSERVATIVE})
        if selection is None:
            stats["no_model_choice"]+=1
            status["model_rejections"][str(reason)]+=1
            continue
        if not eligible_model_choice(selection):
            stats["below_publication_confidence_or_category"]+=1
            continue
        stats["pro_vip_79_football_eligible"]+=1
        model_price,price_reason=pure_model_price(selection,now=clock)
        if model_price is None:
            stats["not_publishable_on_model_price"]+=1
            status["price_rejections"][price_reason]+=1
            continue
        stats["publishable_model_indicative_choices"]+=1
        compared_games+=1
        fixture_id=str(event["id"])
        code=selection["prediction"]["internal_market_code"]
        model_key=selection["prediction"]["key"]
        fixture_summary={
            "event_id":fixture_id,
            "home_team":event.get("home_team"),
            "away_team":event.get("away_team"),
            "league_name":event.get("league_name") or event.get("league"),
            "kickoff":fixture_datetime(event).isoformat(),
            "selection_key":model_key,
            "market_code":code,
            "category":selection["category"],
            "model_probability":model_price["probability"],
            "model_conservative_probability":model_price["conservative_probability"],
            "model_indicative_odds":model_price["odds"],
            "model_odds_source":ESTIMATED_SOURCE,
            "model_odds_method":model_price.get("odds_method"),
            "model_overround_assumption":model_price.get("overround_assumption"),
        }
        for provider,router in routers.items():
            stats["provider_attempts"]+=1
            captured=datetime.now(timezone.utc)
            if captured>=fixture_datetime(event):
                status["quote_rejections"][provider+":after_kickoff"]+=1
                continue
            # One exact market, one original event identity; no price-based switching.
            try:
                quotes,diagnostic=router.fetch(event,captured,market_code=code)
            except (ValueError,TypeError) as exc:
                status["quote_rejections"][provider+":"+type(exc).__name__]+=1
                continue
            row=quotes.get(code) if isinstance(quotes,dict) else None
            if row is None:
                status["quote_rejections"][provider+":unavailable_or_not_comparable"]+=1
                continue
            value,reason=comparison(model_price["odds"],row,code=code,
                                    now=captured,kickoff=fixture_datetime(event))
            if value is None:
                status["quote_rejections"][provider+":"+reason]+=1
                continue
            stats["pairs_comparable"]+=1
            status["provider_counts"][provider]+=1
            rows.append({**fixture_summary,**value,"provider":provider,
                         "provider_priority_rank":list(SOURCE_NAMES).index(provider)+1})
        if not any(r["event_id"]==fixture_id for r in rows):
            unpaired.append({**fixture_summary,"reason":"no_eligible_independent_quote"})
        if compared_games>=max_model_picks:break
    by_source={}
    for provider in provider_order:
        source_rows=[r for r in rows if r["provider"]==provider]
        by_source[provider]=summarize(source_rows)
        by_source[provider]["network_requests"]=routers[provider].usage.get(provider,0)
        by_source[provider]["disabled_due_to_network_or_quota"]=provider in routers[provider].disabled
    matching_matches=len({r["event_id"] for r in rows})
    return {
       "schema":"bsd-v2-indicative-vs-independent-odds-1",
       "captured_at":now.isoformat(),
       "market_selection_policy":"choose one football market before querying any provider",
       "model_quote_policy":"price_selected_market(selection, {}, now=...) from BSD V2 production",
       "model_quote_origin":ESTIMATED_SOURCE,
       "model_default_overround":DEFAULT_OVERROUND,
       "providers_attempted":list(provider_order),
       "provider_priority_order_unmodified":list(SOURCE_NAMES),
       "comparison_method":"same_fixture_same_market_full_time_current_prematch",
       "history": {"used_for_training": True, "no_historical_quote_backfill":True},
       "coverage":{
            "upcoming_in_horizon":available,"fixtures_checked":stats["fixtures_checked"],
            "football_eligible_pro_vip_79":stats["pro_vip_79_football_eligible"],
            "model_indicative_publishable":stats["publishable_model_indicative_choices"],
            "distinct_fixtures_with_pairs":matching_matches,
            "source_pairs_total":stats["pairs_comparable"],
            "no_independent_quote":len(unpaired),
       },
       "reasons":{
           "model":dict(status["model_rejections"]),
           "pricing":dict(status["price_rejections"]),
           "quotes":dict(status["quote_rejections"]),
           "other":dict(stats),
       },
       "overall":summarize(rows),
       "by_provider":by_source,
       "pairs":rows,
       "unpaired_model_selections":unpaired,
       "audit":{
           "uses_genuine_provider_quotes_only":True,
           "excludes_pinnwire_demo_by_default":True,
           "provider_quotas_or_coverage_may_return_zero_pairs":True,
           "model_price_not_a_real_bookmaker_offer":True,
           "bsd_consensus_is_a_provider_aggregate_not_an_individual_bookmaker":True,
           "oddslink_public_may_choose_best_price_among_listed_sportsbooks":True,
           "does_not_change_production_picks":True,
           "market_not_changed_to_find_provider_quote":True,
           "requires_quote_timestamp_not_older_than_seconds":MAX_COMPARABLE_QUOTE_AGE_SECONDS,
           "odds_quotes_only_valid_before_kickoff":True,
           "future_results_not_yet_known":True,
           "only_native_markets_supported_by_existing_provider_adapters":True,
       },
       "model_fit":{"rho":rho_diag,"validation":fit_diag},
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="bsd/odds_indicative_vs_external_report.json")
    p.add_argument("--horizon-hours",type=int,default=48)
    p.add_argument("--max-fixtures",type=int,default=240)
    p.add_argument("--max-model-picks",type=int,default=20)
    args=p.parse_args()
    if not 1<=args.horizon_hours<=120:p.error("horizon-hours must be 1..120")
    if not 1<=args.max_fixtures<=500:p.error("max-fixtures must be 1..500")
    if not 1<=args.max_model_picks<=100:p.error("max-model-picks must be 1..100")
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history:p.error("Restore encrypted BSD archive")
    now=datetime.now(timezone.utc)
    client=BSDClient(max_requests=max(100,args.max_model_picks*12+30))
    end=now+timedelta(hours=args.horizon_hours)
    page=client.list_events(now.date(),end.date(),max_pages=30,ttl=0)
    if not page.complete:
        p.error("BSD incomplete fixture pagination: cannot produce a reliable coverage report")
    report=run(client=client,index=V2History(history),fixtures=page.events,now=now,
               horizon_hours=args.horizon_hours,max_fixtures=args.max_fixtures,
               max_model_picks=args.max_model_picks)
    report["data_collection"]={"bsd_fixture_total":page.total_reported,
                               "bsd_fixture_retrieved":len(page.events),
                               "bsd_api_requests":client.requests_made,
                               "bsd_remaining_quota":client.rate_limit_remaining}
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BSD_ODDS_INDICATIVE_VS_EXTERNAL",json.dumps({
        "coverage":report["coverage"],
        "overall":report["overall"],
        "by_provider":report["by_provider"],
        "data_collection":report["data_collection"],
    },ensure_ascii=False))
    # Zero quotes is an informative coverage outcome, not a false success claim.

if __name__=="__main__":main()
