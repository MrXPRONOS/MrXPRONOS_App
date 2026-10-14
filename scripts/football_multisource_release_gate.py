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


def assess(v2: dict, calendar: dict, fixtures: dict, sportscore: dict) -> dict:
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

    checks = {
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
        "source_metrics": {
            "discovered_fixtures": total,
            "calendar_confirmed": checked,
            "external_history_eligible": eligible,
            "unpriced_v2_research_candidates": candidates,
            "native_bookmaker_ids_verified": native_ids,
            "external_bookmaker_links_verified": external_priced,
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
    verdict = assess(*inputs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MULTISOURCE_PRODUCTION_READINESS", json.dumps(verdict, ensure_ascii=False))


if __name__ == "__main__":
    main()
