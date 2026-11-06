"""Validated BTTS YES quality gate for BSD V3.

The gate is intentionally a veto, not a probability booster. It requires:
1) both teams to have >=70% independently estimated chance to score; and
2) the competition's pre-match BTTS rate to be >=58%.

Thresholds were selected on Jul-Sep 2026 after a Jan-Jun stability check and
evaluated separately on October 2026. The test is retrospective, so the gate
still requires prospective confirmation before any public claim.
"""
from __future__ import annotations
from dataclasses import dataclass
from .legacy import fixture_datetime,outcome_scores
from bsd_v2_btts import btts_features
from bsd_v2_btts_team import fit_team_scoring_model,team_scoring_probabilities

MIN_SIDE_SCORE=.70
MIN_LEAGUE_BTTS=.58

@dataclass(frozen=True)
class BTTSQualityGate:
    team_model: object
    training_matches: int
    min_side_score: float=MIN_SIDE_SCORE
    min_league_btts: float=MIN_LEAGUE_BTTS

    def metadata(self):
        return {"version":"btts-v3-side-league-gate-1",
                "training_period":"2024-01 through 2024-08",
                "training_matches":self.training_matches,
                "min_side_score":self.min_side_score,
                "min_league_btts":self.min_league_btts,
                "role":"selection_veto_only"}

def fit_btts_quality_gate(index,*,max_training=3600):
    fixtures=[]
    for _,event in index.global_games:
        dt=fixture_datetime(event)
        if dt.year==2024 and dt.month<=8 and outcome_scores(event) is not None:
            fixtures.append(event)
    fixtures.sort(key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    model=fit_team_scoring_model(index,fixtures,max_training=max_training)
    trained=getattr(model,"trained_games",0) if model is not None else 0
    return BTTSQualityGate(model,trained)

def evaluate_btts_yes_quality(event,index,gate):
    if gate is None or gate.team_model is None:
        return False,{"reason":"btts_v3_team_model_missing"}
    side=team_scoring_probabilities(event,index,model=gate.team_model)
    feat=btts_features(event,index)
    if side is None or feat is None:
        return False,{"reason":"btts_v3_quality_features_missing"}
    home=float(side["home_scores"])
    away=float(side["away_scores"])
    minimum=min(home,away)
    league=float(feat[9]+.5)
    passed=(minimum>=gate.min_side_score and league>=gate.min_league_btts)
    return passed,{
        "reason":"pass" if passed else (
            "btts_v3_side_score_below_70" if minimum<gate.min_side_score
            else "btts_v3_league_btts_below_58"),
        "home_score_probability":round(home,6),
        "away_score_probability":round(away,6),
        "minimum_side_score_probability":round(minimum,6),
        "league_btts_probability":round(league,6),
        "min_side_score_required":gate.min_side_score,
        "min_league_btts_required":gate.min_league_btts,
    }
