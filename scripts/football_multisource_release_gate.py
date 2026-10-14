#!/usr/bin/env python3
"""Evidence-only BSD V2 multisource production-readiness verdict.

Read-only research JSON reports are not a signed authorization to publish.
A green CI research experiment NEVER authorizes an external betting coupon.
This module cannot enable production or change models, odds, fixtures, or LIVE.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def assess(v2: dict, calendar: dict, fixtures: dict, sportscore: dict,
           calibrated:dict|None=None, native_identity:dict|None=None) -> dict:
    if not all(isinstance(x, dict) for x in (v2, calendar, fixtures, sportscore)):
        raise ValueError("Four aggregate research reports are required")
    coverage = calendar.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("Missing calendar verification coverage")
    quote_gate = v2.get("no_bookmaker_quote_gate")
    bridge = v2.get("external_pricing_bridge")
    if not isinstance(quote_gate, dict) or not isinstance(bridge, dict):
        raise ValueError("Missing V2 bookmaker and identity evidence")

    def number(payload, name):
        value = payload.get(name)
        if type(value) is not int or value < 0:
            raise ValueError("Invalid nonnegative counter: " + name)
        return value

    total = number(fixtures, "total_fixtures")
    checked = number(coverage, "schedule_matches_confirmed")
    matched = number(v2, "calendar_corroborated_fixtures")
    eligible = number(v2, "qualified_external_fixtures")
    candidates = number(v2, "raw_v2_candidates")
    historic = number(v2, "historic_matches")
    quotes_checked = number(quote_gate, "fixtures_checked")
    native_ids = number(bridge, "native_bsd_odds_event_ids_verified")
    external_priced = number(bridge, "external_to_bookmaker_event_matches_verified")
    if not (0 <= candidates <= eligible <= matched <= checked <= total):
        raise ValueError("Inconsistent fixture validation funnel")
    if (number(v2, "input_api_fixtures") != total or
            quotes_checked != eligible or
            number(bridge, "inspected_fixtures") != eligible or
            native_ids > eligible or external_priced > eligible):
        raise ValueError("Inconsistent evidence totals")
    if (v2.get("test_only") is not True or v2.get("production_modified") is not False or
            number(v2, "calibrated_production_coupons") != 0 or
            quote_gate.get("accepted_with_no_bookmaker_quotes") != 0 or
            quote_gate.get("publication_enabled") is not False or
            bridge.get("publication_enabled") is not False or
            sportscore.get("new_events_added_to_prediction_pipeline") != 0 or
            sportscore.get("no_production_writes") is not True):
        raise ValueError("Research isolation invariant violated")

    calibrated_proof=False
    replay_2026=None
    if calibrated is not None:
        if not isinstance(calibrated,dict) or calibrated.get("research_only") is not True:
            raise ValueError("Invalid calibrated replay provenance")
        if (calibrated.get("production_publication_authorized") is not False or
                calibrated.get("raw_or_private_events_exported") is not False or
                calibrated.get("telegram_posts") != 0 or
                calibrated.get("all_native_bsd_v2_fit_functions_used") is not True):
            raise ValueError("Calibrated replay violated research isolation")
        audit=calibrated.get("holdout_evaluation") or {}
        if audit.get("strict_pre_day_data_availability_enforced") is not True:
            raise ValueError("Unverified replay chronology")
        if audit.get("not_a_verified_kickoff_or_odds_backtest") is not True:
            raise ValueError("False claim of real kickoff/odds validation")
        total_audit=number(audit,"matches_examined")
        selected=number(audit,"selected_without_market_quotes")
        won=number(audit,"wins_of_selected_unpriced_markets")
        if not (0<=won<=selected<=total_audit<=200):
            raise ValueError("Inconsistent calibrated replay totals")
        calibrated_proof=(calibrated.get("full_calibration_and_specialists_executed") is True and
                          calibrated.get("training_sufficiency_requirements_met") is True and
                          calibrated.get("upcoming_research",{}).get("official_bookmaker_quotes_loaded") is False)
        replay_2026={
            "evaluated_results":total_audit,"unpriced_selections":selected,
            "selected_successes":won,
            "observed_selected_hit_rate":audit.get("hit_rate"),
            "real_kickoff_or_bookmaker_backtest":False,
        }
    native_link_proof=False
    fresh_consensus_proof=False
    official_native_count=0
    official_consensus_market_count=0
    if native_identity is not None:
        if (not isinstance(native_identity,dict)
            or native_identity.get("scope")!="read_only_identity_evidence"
            or native_identity.get("research_only") is not True
            or native_identity.get("native_event_ids_exported") is not False
            or native_identity.get("no_data_json_modified") is not True
            or native_identity.get("original_production_publication_enabled") is not False):
            raise ValueError("Invalid or unsafe native BSD identity evidence")
        confirmed_native=number(native_identity,"external_cc0_verified")
        official_native_count=number(native_identity,"one_to_one_native_event_links")
        meta_requested=number(native_identity,"official_league_metadata_requested")
        meta_verified=number(native_identity,"official_league_metadata_verified")
        if not (0<=official_native_count<=confirmed_native<=number(native_identity,"external_total")
                and 0<=meta_verified<=meta_requested<=8
                and number(native_identity,"bsd_http_calls")<=12):
            raise ValueError("Inconsistent native source proof counters")
        price_proof=native_identity.get("read_only_native_consensus_price_audit")
        if not isinstance(price_proof,dict):
            raise ValueError("Native quote proof is missing")
        quote_attempts=number(price_proof,"official_native_events_quoted_attempts")
        priced_events=number(price_proof,"events_with_fresh_consensus_market_prices")
        official_consensus_market_count=number(price_proof,"fresh_consensus_market_prices")
        if not (0<=priced_events<=quote_attempts<=min(2,official_native_count)
            and official_consensus_market_count>=priced_events
            and price_proof.get("event_ids_selected_only_from_confirmed_native_links") is True
            and price_proof.get("consensus_is_not_executable_bookmaker_offer") is True
            and number(price_proof,"independent_bookmaker_selection_codes_verified")==0
            and price_proof.get("raw_market_prices_or_event_ids_exported") is False
            and price_proof.get("production_market_policy_approved") is False):
            raise ValueError("Incorrectly promoted consensus pricing evidence")
        native_link_proof=official_native_count>0
        fresh_consensus_proof=official_consensus_market_count>0
    checks = {
        "independently_corroborated_native_event_links_observed":native_link_proof,
        "fresh_bsd_consensus_market_prices_observed":fresh_consensus_proof,
        "real_production_tracker_immutability_probed":bool(
            calibrated_proof and calibrated is not None
            and calibrated.get("native_assembler_dry_run",{}).get(
                "existing_publication_tracker_supplied") is True
            and calibrated.get("native_assembler_dry_run",{}).get(
                "existing_production_snapshot_left_untouched") is True),
        "native_research_model_calibration_reproduced":calibrated_proof,
        "historical_sample_loaded": historic > 0,
        "calendar_confirmed_fixtures": checked > 0,
        "unchanged_existing_v2_probe": quote_gate.get("used_original_predict_v2") is True,
        "research_isolated_from_production": True,
        # These checks MUST only become positive after independently
        # documented production-proof procedures, not guessed JSON flags.
        "full_calibration_and_specialist_models_validated": False,
        "complete_v21_publication_policy_validated": False,
        "external_fixture_to_bookmaker_event_identity_verified": False,
        "real_odds_freshness_and_license_verified": False,
        "provider_attribution_and_commercial_rights_approved": False,
        "time_forward_out_of_sample_validation_approved": False,
        "end_to_end_production_and_telegram_regression_approved": False,
    }
    blockers = [
        key for key in (
            "full_calibration_and_specialist_models_validated",
            "complete_v21_publication_policy_validated",
            "external_fixture_to_bookmaker_event_identity_verified",
            "real_odds_freshness_and_license_verified",
            "provider_attribution_and_commercial_rights_approved",
            "time_forward_out_of_sample_validation_approved",
            "end_to_end_production_and_telegram_regression_approved",
        ) if not checks[key]
    ]
    return {
        "decision": "NO_GO",
        "production_publication_authorized": False,
        "research_pipeline_passed": all((
            checks["historical_sample_loaded"],
            checks["calendar_confirmed_fixtures"],
            checks["unchanged_existing_v2_probe"],
            checks["research_isolated_from_production"],
        )),
        "research_branch_fusion_authorized_by_this_report": False,
        "independent_review_before_merging_required": True,
        "calibrated_replay_2026":replay_2026,
        "source_metrics": {
            "discovered_fixtures": total,
            "calendar_confirmed": checked,
            "external_history_eligible": eligible,
            "unpriced_v2_research_candidates": candidates,
            "native_bookmaker_ids_verified": native_ids,
            "external_bookmaker_links_verified": external_priced,
            "authentic_bsd_event_links_from_private_validation":official_native_count,
            "fresh_bsd_consensus_market_prices_from_private_validation":official_consensus_market_count,
            "sportscore_possibly_incomplete": sportscore.get("possible_incomplete_coverage") is True,
        },
        "checks": checks,
        "blocking_requirements": blockers,
        "no_odds_or_fixture_invention": True,
        "no_model_or_live_mutation": True,
        "no_telegram_posting": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--v2", required=True)
    p.add_argument("--calendar", required=True)
    p.add_argument("--fixtures", required=True)
    p.add_argument("--sportscore", required=True)
    p.add_argument("--calibrated", help="Optional full-model research-only replay report")
    p.add_argument("--native-identity", help="Optional safe aggregate from private native event/odds job")
    p.add_argument("--report", required=True)
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    out = Path(args.report).resolve()
    if out == (repo / "data.json").resolve():
        p.error("Production data.json cannot be overwritten")
    inputs = [
        json.loads(Path(getattr(args, x)).read_text(encoding="utf-8"))
        for x in ("v2", "calendar", "fixtures", "sportscore")
    ]
    if args.calibrated:
        inputs.append(json.loads(Path(args.calibrated).read_text(encoding="utf-8")))
    if args.native_identity:
        inputs.append(json.loads(Path(args.native_identity).read_text(encoding="utf-8")))
    verdict = assess(*inputs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MULTISOURCE_PRODUCTION_READINESS", json.dumps(verdict, ensure_ascii=False))


if __name__ == "__main__":
    main()
