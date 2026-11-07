"""BSD V3 Over 2.5 quality veto.

A 70% central / 68% conservative threshold alone is not enough. Historical
2026 research found a stable improvement when the competition's point-in-time
Over 2.5 rate is at least 58%.

Selection evidence (threshold not chosen on October):
- Jan-Jun 2026: 219/307 = 71.34%
- Jul-Sep 2026: 270/379 = 71.24%
- Oct 2026: 108/153 = 70.59%

This is a selection gate, never a probability booster.
"""
from __future__ import annotations
from bsd_v2_over_under import features as total_features

MIN_LEAGUE_OVER25=.58

def evaluate_over25_quality(event,index):
    feat=total_features(event,index)
    if feat is None:
        return False,{"reason":"over25_v3_total_features_missing"}
    league=float(feat["league_over_rates"][2.5])
    passed=league>=MIN_LEAGUE_OVER25
    return passed,{
        "reason":"pass" if passed else "over25_v3_league_rate_below_58",
        "league_over25_probability":round(league,6),
        "min_league_over25_required":MIN_LEAGUE_OVER25,
        "form_samples":int(feat.get("form_samples",0)),
        "venue_samples":int(feat.get("venue_samples",0)),
        "league_samples":int(feat.get("league_samples",0)),
    }
