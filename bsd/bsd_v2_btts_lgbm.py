"""LightGBM BTTS classifier with strictly point-in-time historical features.

Machine learning adds nonlinear interactions between attack/defence, venue,
zero-goal propensity and time since last appearance. No shots/xG/injuries
are fabricated. Only matches from Jan-Aug 2024 are fitted; all later
evaluations are out of sample. LightGBM is installed in the BSD workflows.
"""
from __future__ import annotations
from dataclasses import dataclass
from bsd_v2_core import fixture_datetime, estimate_goals, score_matrix, markets_from_matrix, outcome_scores
from bsd_v2_btts_zero import zero_goal_features
from bsd_v2_btts import btts_features


def ml_features(event,index,expected=None):
    if expected is None:
        expected,_=estimate_goals(event,index)
        if expected is None:return None
    btts=btts_features(event,index)
    blank=zero_goal_features(event,index,expected)
    if btts is None or blank is None:return None
    baseline=1-__import__("math").exp(-expected["home"])
    second=1-__import__("math").exp(-expected["away"])
    v=[
       expected["home"],expected["away"],expected["home"]-expected["away"],
       expected["home"]+expected["away"],
       baseline,second,baseline*second,
       min(expected["home_recent_matches"],expected["away_recent_matches"])/14.,
       min(expected["home_venue_matches"],expected["away_venue_matches"])/10.,
       min(300,expected["league_samples"])/300.,
       min(240,expected["max_last_match_age_days"])/240.,
    ]
    v.extend(btts[1:])  # exclude constant intercept
    # Side-specific zero-goal and clean-sheet context, distinct from avg goals.
    for _prior,vector in blank:
        v.extend(vector[1:])
    return tuple(float(x) for x in v)


@dataclass(frozen=True)
class LightGBMBTTS:
    model: object
    feature_count: int
    training_matches: int

    def predict(self,event,index,expected=None):
        features=ml_features(event,index,expected)
        if features is None:return None
        if len(features)!=self.feature_count:
            raise ValueError("LightGBM feature schema has changed")
        p=float(self.model.predict_proba([features])[0][1])
        return max(.01,min(.99,p))

    def to_dict(self):
        return {"family":"lightgbm_classifier",
                "training_matches":self.training_matches,
                "features":self.feature_count,
                "rounds":self.model.n_estimators,
                "training_year":2024}


def fit_lightgbm(index,fixtures,*,max_training=3500,min_training=350):
    try:
        from lightgbm import LGBMClassifier
    except ImportError:
        return None
    games=sorted(fixtures,key=lambda e:(e["event_date"],str(e["id"])))
    if len(games)>max_training:
        games=[games[int(i*len(games)/max_training)] for i in range(max_training)]
    xs,ys=[],[]
    for event in games:
        dt=fixture_datetime(event)
        if dt.year!=2024 or dt.month>8:
            raise ValueError("LightGBM training must be Jan-Aug 2024")
        scores=outcome_scores(event)
        if scores is None:continue
        features=ml_features(event,index)
        if features is None:continue
        xs.append(features)
        ys.append(int(scores[0]>0 and scores[1]>0))
    if len(xs)<min_training or len(set(ys))<2:
        return None
    estimator=LGBMClassifier(
        objective="binary",n_estimators=100,learning_rate=.045,
        num_leaves=11,max_depth=5,min_child_samples=40,
        colsample_bytree=.85,reg_lambda=4.,reg_alpha=.1,
        subsample=1.,random_state=2024,n_jobs=1,verbosity=-1,
    )
    estimator.fit(xs,ys)
    return LightGBMBTTS(estimator,len(xs[0]),len(xs))
