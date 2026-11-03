"""Independent out-of-sample BTTS audit; NO other-market ranking needed.

Train exactly the production BTTS model (2024), market calibration and
quality (2025), then evaluate each completed 2026 fixture. The observed
final score is used ONLY after the pre-kickoff probability was computed.
"""
import csv,json,math
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime

from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import V2History,fit_rho_2024,fixture_datetime,outcome_scores,estimate_goals,score_matrix,markets_from_matrix,choose_market,classify_quality_category
from bsd_v2_btts import fit_btts_model,btts_candidates
from bsd_v2_policies import fit_policy
from bsd_v2_guardrails import MIN_CONSERVATIVE_BY_FAMILY
from bsd_v2_publication_policy import eligible_model_choice

THRESHOLDS=(.50,.55,.60,.65,.70,.75,.79,.80,.85,.90)
KEYS=("BTTS_YES","BTTS_NO")

def summarize(rows):
    n=len(rows)
    if n==0:return {'n':0,'wins':0,'hit_rate':None,'average_p':None,'calibration_gap_pp':None,'brier':None,'wilson95':None}
    wins=sum(y for p,y,other in rows)
    pbar=sum(p for p,y,_ in rows)/n
    rate=wins/n
    z=1.96
    d=1+z*z/n
    c=(rate+z*z/(2*n))/d
    h=z*math.sqrt((rate*(1-rate)+z*z/(4*n))/n)/d
    return {'n':n,'wins':wins,'losses':n-wins,'hit_rate':round(rate,4),
            'average_p':round(pbar,4),'calibration_gap_pp':round(100*(pbar-rate),2),
            'brier':round(sum((p-y)**2 for p,y,_ in rows)/n,5),
            'wilson95':[round(max(0,c-h),4),round(min(1,c+h),4)]}

def run():
    hist=_read_json(MATCHES_FILE,None)
    if not isinstance(hist,list) or not hist:raise ValueError('Restored BSD historical archive required')
    index=V2History(hist)
    rho,rho_diag=fit_rho_2024(index)
    btts,btts_diag=fit_btts_model(index,rho=rho)
    cal,policy,policy_diag=fit_policy(index,rho=rho,btts_model=btts)
    family_adj=policy.family_uncertainty_adjustments().get('btts',0.)
    games=sorted([e for _,e in index.global_games
                   if '2026-01-01'<=fixture_datetime(e).date().isoformat()<='2026-11-03'],
                   key=lambda e:(e.get('event_date') or '',str(e.get('id'))))
    stats=Counter()
    rows=defaultdict(list)
    for e in games:
        stats['2026_finished_events']+=1
        feat,reason=estimate_goals(e,index)
        if feat is None:
            stats['no_features_'+str(reason)]+=1
            continue
        actual=outcome_scores(e)
        if actual is None:continue
        matrix=score_matrix(feat['home'],feat['away'],rho)
        cs=[c for c in btts_candidates(e,index,markets_from_matrix(matrix),btts)
            if c.key in KEYS]
        _,ranked=choose_market(cs,calibration=cal,min_probability=0.0,
                    league_samples=feat['league_samples'],
                    form_samples=min(feat['home_recent_matches'],feat['away_recent_matches']),
                    family_adjustments={'btts':family_adj},
                    family_minimums=MIN_CONSERVATIVE_BY_FAMILY)
        if len(ranked)!=2:
            stats['ranked_incomplete']+=1
            continue
        fixture_good=policy.check_fixture(feat) is None
        for rec in ranked:
            key=rec['candidate'].key
            p=rec['calibrated_probability']
            conservative=rec['ranking_confidence']
            category=classify_quality_category(conservative,feat)
            market_good=policy.check_market(rec) is None
            qualified=fixture_good and market_good
            good79=qualified and eligible_model_choice({
                'category':category,'prediction':{'probability':p}})
            win=int((actual[0]>0 and actual[1]>0)==(key=='BTTS_YES'))
            rows[key].append((p,win,{
                'quality':qualified,'eligible79':good79,
                'conservative':conservative,'category':category,
                'estimated_odds_no_floor':round(1/(p*1.06),3)}))
        stats['modeled_fixtures']+=1
    out={'schema':'btts-independent-fast-holdout-2026',
         'period':'2026-01-01 to 2026-11-03',
         'leakage_control':'2024 fit, 2025 chronological calibration/validation, 2026 evaluation only',
         'training':{'btts':btts_diag,'market_calibration':policy_diag,'rho':rho_diag},
         'coverage':dict(stats),'by_market':{},
         'limitations':['Not historical published picks; both sides evaluated independently.',
          'No historical bookmaker prices available and no historical ROI claimed.',
          '2026 results never train the model.',
          'Below-79% sensitivity rows are research only, not site recommendations.',
          'No same-fixture cross-market ranking in this fast statistical pass.']}
    for key in KEYS:
        data=rows[key]
        q=[x for x in data if x[2]['quality']]
        e=[x for x in q if x[2]['eligible79']]
        out['by_market'][key]={
          'all':summarize(data),
          'quality':summarize(q),
          'qualified79':summarize(e),
          'qualified79_model_odds_at_least120':summarize(
              [x for x in e if x[2]['estimated_odds_no_floor']>=1.20]),
          'thresholds':{
            str(int(t*100)):{
             'all':summarize([x for x in data if x[0]>=t]),
             'quality':summarize([x for x in q if x[0]>=t]),
            } for t in THRESHOLDS},
          'qualified79_conservative_avg':round(sum(x[2]['conservative'] for x in e)/len(e),4) if e else None,
          'qualified79_model_price_no_floor_median':round(
              sorted(x[2]['estimated_odds_no_floor'] for x in e)[len(e)//2],3) if e else None,
        }
    return out

def main():
    r=run()
    p=Path('bsd/btts_statistical_holdout_2026')
    p.with_suffix('.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    lines=['# BTTS Oui et Non — Backtest historique indépendant (2026)','',
      '**Période :** '+r['period']+'. Entraînement 2024, calibration 2025, test 2026.','',
      '| Indicateur | BTTS Oui | BTTS Non |','|---|---:|---:|']
    yes=r['by_market']['BTTS_YES'];no=r['by_market']['BTTS_NO']
    for label,key in [('Matchs prédits','all'),('Qualité fixture/marché','quality'),('Éligibles Pro/VIP ≥79 %','qualified79')]:
        lines.append(f"| {label} | {yes[key]['n']} | {no[key]['n']} |")
    for label,key in [('Succès sur tous les matchs','all'),('Succès après qualité','quality'),('Succès ≥79 %','qualified79')]:
        a=yes[key];b=no[key]
        fmt=lambda d:'—' if d['hit_rate'] is None else f"{d['wins']}/{d['n']} ({100*d['hit_rate']:.2f} %)"
        lines.append(f"| {label} | {fmt(a)} | {fmt(b)} |")
    lines+=['','## Analyse des seuils (après contrôle qualité)','',
      '| Seuil | Oui : sélectionnés | Oui : réussite | Non : sélectionnés | Non : réussite |',
      '|---|---:|---:|---:|---:|']
    for t in THRESHOLDS:
        a=yes['thresholds'][str(int(t*100))]['quality']
        b=no['thresholds'][str(int(t*100))]['quality']
        fmt=lambda x:'—' if x['hit_rate'] is None else f"{100*x['hit_rate']:.2f} %"
        lines.append(f"| {int(100*t)} % | {a['n']} | {fmt(a)} | {b['n']} | {fmt(b)} |")
    lines+=['','**Aucune cote historique des bookmakers disponible.** La rentabilité',
      'ne peut pas être calculée à partir des probabilités modèle seules.',
      'Les seuils inférieurs à 79 % sont exclusivement des scénarios de recherche.',
      'Les autres marchés ne sont pas reclassés dans ce test rapide.','']
    p.with_suffix('.md').write_text('\n'.join(lines),encoding='utf8')
    with p.with_suffix('.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.writer(f)
        w.writerow(['market','threshold','scope','n','wins','hit_rate','brier','calibration_gap_pp'])
        for m,data in r['by_market'].items():
            for t,entry in data['thresholds'].items():
                for scope,q in entry.items():
                    w.writerow([m,t,scope,q['n'],q['wins'],q['hit_rate'],q['brier'],q['calibration_gap_pp']])
    print('BSD_BTTS_FAST_RESULT',json.dumps({'coverage':r['coverage'],'by_market':r['by_market']},ensure_ascii=False))
if __name__=='__main__':main()
