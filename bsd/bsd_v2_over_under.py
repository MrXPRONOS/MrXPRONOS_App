"""Independent goal-total frequency model. All inputs are pre-kickoff BSD history."""
from dataclasses import dataclass, replace
from math import exp, factorial, log, isfinite
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, outcome_scores, estimate_goals, score_matrix, markets_from_matrix

LINES=(1.5,2.5,3.5,4.5)

def _rate(rows,at,team=None,venue=None):
    weighted=0.;total=0.;sq=0.
    for event in rows:
        score=outcome_scores(event)
        if score is None:continue
        age=max(0,(at-fixture_datetime(event)).total_seconds()/86400)
        w=exp(-log(2)*age/100.)
        goals=sum(score)
        total+=w;weighted+=w*goals;sq+=w*goals*goals
    avg=(weighted+8*2.6)/(total+8)
    variance=max(.2,(sq+8*(2.6**2+2.6))/(total+8)-avg*avg)
    return avg,variance,total

def features(event,index):
    at=fixture_datetime(event)
    home=_team_id(event,"home");away=_team_id(event,"away")
    if not home or not away:return None
    hg=index.team(home,at,limit=15)
    ag=index.team(away,at,limit=15)
    if min(len(hg),len(ag))<5:return None
    hv=index.team(home,at,limit=12,venue="home")
    av=index.team(away,at,limit=12,venue="away")
    league_key_value=__import__("bsd_v2_core").league_key(event)
    lg=index.league(league_key_value,at,limit=300)
    hm,hvar,_=_rate(hg,at)
    am,avar,_=_rate(ag,at)
    lmean,lvar,ln=_rate(lg,at)
    hvenue,_,hn=_rate(hv,at)
    avenue,_,an=_rate(av,at)
    # Moderate venue correction; league prior dominates sparse samples.
    venue_mean=(hn/(hn+8)*hvenue+8/(hn+8)*hm+
                an/(an+8)*avenue+8/(an+8)*am)/2
    baseline=(hm+am)/2
    result_mean=.55*baseline+.25*venue_mean+.20*lmean
    dispersion=max(.4,min(12.,.5*(hvar+avar)))
    return {"mean":result_mean,"variance":dispersion,"league_mean":lmean,
            "league_variance":lvar,"home_mean":hm,"away_mean":am,
            "league_samples":len(lg),"form_samples":min(len(hg),len(ag)),
            "venue_samples":min(len(hv),len(av))}

def total_distribution(mean,variance,max_goals=24):
    if mean<=0 or not isfinite(mean):raise ValueError("Invalid expected total")
    # Poisson / overdispersed negative binomial (Gamma Poisson).
    if variance<=mean*1.02:
        probs=[exp(-mean)*mean**n/factorial(n) for n in range(max_goals+1)]
    else:
        shape=mean*mean/(variance-mean)
        p=shape/(shape+mean)
        probs=[p**shape]
        for n in range(1,max_goals+1):
            probs.append(probs[-1]*(n-1+shape)/n*(1-p))
    total=sum(probs)
    return [v/total for v in probs]

@dataclass(frozen=True)
class TotalGoalsModel:
    blend:float=0.0
    variance_scale:float=1.0
    trained:int=0
    validated:int=0
    def predict_over(self,event,index):
        feat=features(event,index)
        if feat is None:return None
        distribution=total_distribution(feat["mean"],max(feat["mean"],feat["variance"]*self.variance_scale))
        return {line:sum(distribution[int(line)+1:]) for line in LINES}
    def to_dict(self):
        return {"model":"bsd-over-under-1","blend":self.blend,
                "variance_scale":self.variance_scale,
                "trained":self.trained,"validated":self.validated}

def adjust_candidates(event,index,candidates,model):
    if model is None or model.blend<=0:return candidates
    probabilities=model.predict_over(event,index)
    if probabilities is None:return candidates
    out=[]
    for item in candidates:
        if item.family!="goals" or item.line not in probabilities:
            out.append(item);continue
        before=item.probability
        estimate=probabilities[item.line]
        if item.outcome=="under":estimate=1-estimate
        p=max(.00001,min(.99999,(1-model.blend)*before+model.blend*estimate))
        out.append(replace(item,probability=p))
    return out

def fit_total_model(index,rho=0.,max_training=1800,max_validation=450):
    # Hyperparameter selection on 2024 only, never optimize using 2025/26 outcomes.
    train=[];valid=[]
    for _,event in index.global_games:
        try:
            at=fixture_datetime(event)
            if at.year!=2024:continue
            feat=features(event,index)
            expected,_=estimate_goals(event,index)
            if feat is None or expected is None:continue
            scores=outcome_scores(event);goals=sum(scores)
            poisson=markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))
            baseline={c.line:c.probability for c in poisson if c.family=="goals" and c.outcome=="over"}
            item=(feat,goals,baseline)
            (train if at.month<=8 else valid).append(item)
        except (ValueError,TypeError,OverflowError):continue
    def thin(seq,n):
        return seq if len(seq)<=n else [seq[int(i*len(seq)/n)] for i in range(n)]
    train=thin(train,max_training);valid=thin(valid,max_validation)
    candidates=[]
    if len(train)>=100 and len(valid)>=50:
        for scale in (.85,1.0,1.2):
            for weight in (0.,.25,.50,.75,1.):
                loss=0.
                for feat,goals,baseline in valid:
                    dist=total_distribution(feat["mean"],max(feat["mean"],feat["variance"]*scale))
                    for line in LINES:
                        p=(1-weight)*baseline[line]+weight*sum(dist[int(line)+1:])
                        actual=int(goals>line)
                        loss+=(p-actual)**2
                candidates.append((loss/(len(valid)*len(LINES)),scale,weight))
    if candidates:
        best=min(candidates)
        baseline=min((item for item in candidates if item[2]==0.),key=lambda x:x[0])
        chosen=best if best[0]<baseline[0]-.001 else baseline
        return TotalGoalsModel(chosen[2],chosen[1],len(train),len(valid)),{
            "trained":len(train),"validated":len(valid),
            "baseline_brier":round(baseline[0],6),
            "selected_brier":round(chosen[0],6),
            "blend":chosen[2],"variance_scale":chosen[1],
            "train_period":"2024-01 through 2024-08",
            "validation_period":"2024-09 through 2024-12"}
    return TotalGoalsModel(0.,1.,len(train),len(valid)),{
        "trained":len(train),"validated":len(valid),"blend":0.,
        "reason":"insufficient_2024_data"}
