"""Predictions and indicative prices for ALL 25 historical BSD V2 markets.

16 existing FT outcomes + 9 experimental outcomes (seven new families).
This is an observation catalogue, never a bet recommendation or publication.
For research, compute indicative odds only for 0.10 <= p <= 0.99, regardless
of publication eligibility. Outside this probability range, retain a marked
observation without an indicative price.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import isfinite

from bsd_markets import candidates_from_goals
from bsd_v2_core import estimate_goals,score_matrix,markets_from_matrix,fixture_datetime
from bsd_v2_over_under import adjust_candidates as adjust_totals
from bsd_v2_btts import btts_candidates
from bsd_v2_double_chance import adjust_candidates as adjust_dc
from bsd_v2_estimated_odds import estimated_quote, DEFAULT_OVERROUND
from bsd_v2_market_expansion import candidates as new_candidates, ALL_KEYS,half_time_share,first_half_scores,outcome

OLD_KEYS=tuple(c.key for c in candidates_from_goals(1.4,1.2))
CATALOG_KEYS=OLD_KEYS+ALL_KEYS
MIN_RESEARCH_PROBABILITY=0.10
MAX_RESEARCH_PROBABILITY=0.99
assert len(OLD_KEYS)==16 and len(ALL_KEYS)==9 and len(set(CATALOG_KEYS))==25

class ExperimentalCalibrator:
    """Simple 2025 pre-holdout shrinkage used by research backtests."""
    def __init__(self,strength=75):
        self.strength=strength
        self.data=defaultdict(lambda:[0,0])
    @staticmethod
    def bucket(p):return min(19,int(p*20))
    def observe(self,key,p,y):
        if p is None or y not in (0,1) or key.startswith("DNB_"):return
        row=self.data[(key,self.bucket(p))]
        row[0]+=1;row[1]+=y
    def score(self,key,p):
        if p is None or key.startswith("DNB_"):return p
        n,w=self.data.get((key,self.bucket(p)),(0,0))
        return (self.strength*p+w)/(self.strength+n)

def fit_new_market_calibration(index,rho,*,max_training=2200):
    historical=[e for _,e in index.global_games
                if fixture_datetime(e).year==2025 and fixture_datetime(e).month<=8]
    historical.sort(key=lambda e:(str(e.get("event_date")),str(e.get("id"))))
    if len(historical)>max_training:
        historical=[historical[int(i*len(historical)/max_training)] for i in range(max_training)]
    ht_ratio,ht_diagnostics=half_time_share(
        [e for _,e in index.global_games if fixture_datetime(e).year==2024])
    fitted=ExperimentalCalibrator()
    trained=0
    for fixture in historical:
        feat,reason=estimate_goals(fixture,index)
        if feat is None:continue
        mat=score_matrix(feat['home'],feat['away'],rho)
        h,a=fixture['home_score'],fixture['away_score']
        for c in new_candidates(mat,home_xg=feat['home'],away_xg=feat['away'],
                                halftime_share=ht_ratio):
            y=outcome(c.key,h,a,half_time=first_half_scores(fixture))
            fitted.observe(c.key,c.probability,y)
        trained+=1
    return fitted,ht_ratio,{'new_market_training_2025':trained,'halftime_training_2024':ht_diagnostics}

def _model_price(key,code,p,conservative,*,now=None):
    """Use site estimated_quote first; audit extension uses the SAME fair/6% formula.

    A native estimate may be missing because publication would be disallowed
    (p<70%, odds<1.20, unsupported market). That MUST NOT remove a market from
    a price-quality study. Such price is clearly tagged research_only.
    """
    if p is None or type(p) not in (int,float) or not isfinite(p):
        return None,'probability_unavailable'
    p=float(p)
    if not MIN_RESEARCH_PROBABILITY <= p <= MAX_RESEARCH_PROBABILITY:
        return None,'outside_research_probability_range'
    if conservative is not None and 0<conservative<=p:
        native=estimated_quote({'key':key,'market_code':code,'probability':p,
              'conservative_probability':conservative},{},now=now)
        if native:
            return {'odds':native['odds'],'fair_odds':native['fair_odds'],
                'odds_method':'native_site_estimated_quote',
                'overround':native['overround_assumption'],
                'reference':native['overround_reference'],
                'publishable_as_indicative_price':True},'ok'
    # The site's default 6% overround is preserved, without its publishability
    # min price or confidence gate; this is NOT exactly the production quote.
    margin=min(DEFAULT_OVERROUND,max(0.,1/(1.20*p)-1))
    diag=1/(p*(1+margin))
    if not isfinite(diag) or not 1.01<=diag<=100:
        return None,'diagnostic_price_outside_range'
    return {'odds':round(diag,3),'fair_odds':round(1/p,4),
            'odds_method':'research_same_formula_without_publication_gates',
            'overround':round(margin,5),'reference':'hypothese_6pct',
            'publishable_as_indicative_price':False},'research_only'

def all_markets_for_fixture(event,index,*,rho,calibration,totals,btts,dc,
                            new_calibration,ht_ratio,now):
    feat,reason=estimate_goals(event,index)
    if feat is None:
        return [{'key':key,'status':'features_unavailable','reason':reason,
                 'probability':None,'indicative_odds':None} for key in CATALOG_KEYS]
    mat=score_matrix(feat['home'],feat['away'],rho)
    old=markets_from_matrix(mat)
    old=adjust_totals(event,index,old,totals)
    old=btts_candidates(event,index,old,btts)
    old=adjust_dc(event,index,old,dc,getattr(calibration,'outcome_calibration',None))
    out=[]
    probs={}
    by_key={c.key:c for c in old}
    for c in old:
        if c.family in ('result','double_chance') and getattr(calibration,'outcome_calibration',None) is not None:
            p=float(c.probability)
        else:
            p=float(calibration.score(c)[1])
        probs[c.key]=p
        price,st=_model_price(c.key,c.market_code,p,max(0.,p-.02),now=now)
        out.append({'key':c.key,'family':c.family,'market_code':c.market_code,
                    'probability':round(p,6),
                    'indicative_odds':price['odds'] if price else None,
                    'pricing_status':st,
                    'odds_method':price['odds_method'] if price else None,
                    'native_site_price_allowed':bool(price and price['publishable_as_indicative_price']),
                    'overround':price['overround'] if price else None,
                    'price_source':'mrxpronos_model_calculated' if price else None,
                    'model_status':'legacy_v2_calibrated'})
    exp=new_candidates(mat,home_xg=feat['home'],away_xg=feat['away'],halftime_share=ht_ratio)
    for c in exp:
        refund=float(c.refund_probability)
        if c.family=='dnb':
            # Draw refunds principal; fair odds depend on P(win | no draw).
            den=1-probs.get('X',refund)
            side='1' if c.key=='DNB_HOME' else '2'
            p=probs[side]/den if den>1e-10 else None
            model_status='experimental_refund_conditional_not_calibrated'
        else:
            p=new_calibration.score(c.key,c.probability) if c.probability is not None else None
            model_status='experimental_2025_calibrated' if p is not None else 'missing_halftime_model'
        price,st=_model_price(c.key,c.market_code,p,max(0.,p-.02) if p is not None else None,now=now)
        out.append({'key':c.key,'family':c.family,'market_code':c.market_code,
                    'probability':round(p,6) if p is not None else None,
                    'raw_probability':round(c.probability,6) if c.probability is not None else None,
                    'refund_probability':round(refund,6) if c.family=='dnb' else None,
                    'indicative_odds':price['odds'] if price else None,'pricing_status':st,
                    'odds_method':price['odds_method'] if price else None,
                    'native_site_price_allowed':bool(price and price['publishable_as_indicative_price']),
                    'overround':price['overround'] if price else None,
                    'price_source':'mrxpronos_model_calculated' if price else None,
                    'model_status':model_status})
    assert len(out)==25 and set(x['key'] for x in out)==set(CATALOG_KEYS)
    return out
