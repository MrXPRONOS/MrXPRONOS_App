"""Read-only diagnostics for the BSD V2.1 VIP selection funnel.

The data is observational: this module never changes a market, a price,
a probability, a publication decision, or existing category assignments.
"""
from collections import Counter

VIP_THRESHOLDS = {
    "minimum_conservative_probability": 0.83,
    "minimum_league_samples": 80,
    "minimum_recent_matches_per_team": 12,
    "minimum_home_away_matches_per_team": 5,
}


def summarize_vip_funnel(fixture_details, published_matches):
    """Summarize newly evaluated fixtures, excluding previously known picks.

    'preprice' exists only after a football market has passed phase 1.
    Failed predictions without a qualified market have NO VIP grade. This
    deliberate distinction avoids counting incomplete evaluations as VIP.
    """
    details = [x for x in (fixture_details or ()) if isinstance(x, dict)]
    rows = [x for x in (published_matches or ()) if isinstance(x, dict)]
    candidates = [x for x in details if isinstance(x.get("preprice"), dict)]
    tiers = ("simple", "pro", "vip")
    preprice_counts = Counter(x["preprice"].get("category") for x in candidates)
    published_counts = Counter(x.get("category") for x in rows)
    published_new_counts = Counter(
        x["preprice"].get("category")
        for x in candidates if x.get("status") == "published"
    )

    # Progressive tests let us see which VIP criterion is most restrictive.
    # All counts have the same denominator: evaluated football selections.
    steps = [
        ("football_market_qualified", lambda r: True),
        ("conservative_probability_at_least_83pct", lambda r: float(r.get("conservative_probability") or 0) >= .83),
        ("plus_league_history_at_least_80", lambda r: int(r.get("league_samples") or 0) >= 80),
        ("plus_recent_history_at_least_12_each", lambda r: min(int(r.get("home_recent_matches") or 0), int(r.get("away_recent_matches") or 0)) >= 12),
        ("plus_home_away_history_at_least_5_each", lambda r: min(int(r.get("home_venue_matches") or 0), int(r.get("away_venue_matches") or 0)) >= 5),
    ]
    surviving = candidates
    step_counts = {}
    for name, predicate in steps:
        surviving = [x for x in surviving if predicate(x["preprice"])]
        step_counts[name] = len(surviving)

    vip_candidates = [x for x in candidates if x["preprice"].get("category") == "vip"]
    rejected_vips = [x for x in vip_candidates if x.get("status") != "published"]
    before_selection = Counter(
        str(x.get("reason") or "unknown")
        for x in details if not isinstance(x.get("preprice"), dict)
    )
    return {
        "scope": "fixtures_not_previously_published_in_this_generation",
        "examined_fixture_count": len(details),
        "without_football_qualified_market_or_out_of_scope": len(details) - len(candidates),
        "preprice_classified_total": len(candidates),
        "preprice_category_counts": {key: preprice_counts[key] for key in tiers},
        "vip_thresholds": dict(VIP_THRESHOLDS),
        "progressive_vip_threshold_counts": step_counts,
        "vip_before_price_and_v21": len(vip_candidates),
        "vip_rejected_after_football_selection": len(rejected_vips),
        "vip_rejection_reasons": dict(sorted(Counter(str(x.get("reason") or "unknown") for x in rejected_vips).items())),
        "newly_published_by_category": {key: published_new_counts[key] for key in tiers},
        "all_published_by_category_including_history": {key: published_counts[key] for key in tiers},
        "not_classified_reason_counts": dict(sorted(before_selection.items())),
        "vip_candidates": [
            {
                "event_id": x.get("event_id"),
                "event_date": x.get("event_date"),
                "home_team": x.get("home_team"),
                "away_team": x.get("away_team"),
                "selection_key": x["preprice"].get("selection_key"),
                "conservative_probability": x["preprice"].get("conservative_probability"),
                "odds_source": (x.get("pricing") or {}).get("odds_source"),
                "status": x.get("status"),
                "reason": x.get("reason"),
            }
            for x in vip_candidates
        ],
    }
