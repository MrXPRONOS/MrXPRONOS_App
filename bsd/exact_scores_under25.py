"""BSD V2 Under 2.5 specialist and coherent exact-score probability fusion."""
from dataclasses import dataclass
from bsd_v2_over_under import features as total_features, fit_total_model, total_distribution

def probability_under25(matrix):
    return sum(p for (h,a),p in matrix.items() if h+a<=2)

def specialist_under25(feat,variance_scale=1.):
    if feat is None:return None
    dist=total_distribution(feat["mean"],max(feat["mean"],feat["variance"]*variance_scale))
    return max(.000001,min(.999999,1-(.8*sum(dist[3:])+.2*feat["empirical_over"][2.5])))

def fused_probability(base,special,blend):
    if special is None:return base
    return max(.000001,min(.999999,(1-blend)*base+blend*special))

def reweight_scores(matrix,target):
    old=probability_under25(matrix)
    if not (0<old<1):raise ValueError("Invalid probability mass")
    target=max(.001,min(.999,target))
    return {(h,a):p*(target/old if h+a<=2 else (1-target)/(1-old))
            for (h,a),p in matrix.items()}

@dataclass(frozen=True)
class Under25Model:
    blend:float
    variance_scale:float
    threshold:float=.62
    def predict(self,event,index,matrix):
        f=total_features(event,index)
        b=probability_under25(matrix)
        s=specialist_under25(f,self.variance_scale)
        p=fused_probability(b,s,self.blend)
        return {"probability":p,"baseline":b,"specialist":s,
                "priority":p>=self.threshold,"feature_available":f is not None}

def train_under25(index,params,max_2025=1600):
    """Existing BSD model fitted on 2024; blend selected using 2025 only."""
    from bsd_v2_core import estimate_goals, outcome_scores
    from exact_scores import matrix_for,year_sample
    bsd_model,info=fit_total_model(index,rho=params["rho"],max_training=650,max_validation=200)
    rows=[]
    for event in year_sample(index,2025,max_2025):
        f,_=estimate_goals(event,index)
        if f is None:continue
        tf=total_features(event,index)
        if tf is None:continue
        matrix=matrix_for(f["home"]*params["scale_home"],
                          f["away"]*params["scale_away"],rho=params["rho"])
        rows.append((probability_under25(matrix),
                     specialist_under25(tf,bsd_model.variance_scale),
                     int(sum(outcome_scores(event))<=2)))
    split=int(len(rows)*.7)
    train,valid=rows[:split],rows[split:]
    def brier(data,w):
        return sum((fused_probability(a,b,w)-y)**2 for a,b,y in data)/len(data)
    weights=(0.,.25,.5,.75,1.)
    blend=0.
    if len(train)>=100 and len(valid)>=50:
        candidate=min(weights,key=lambda w:(brier(train,w),w))
        if brier(valid,0.)-brier(valid,candidate)>=.0004:blend=candidate
    return Under25Model(blend,bsd_model.variance_scale),{
        "bsd_training":info,"2025_train":len(train),"2025_validation":len(valid),
        "blend":blend,"validation_baseline_brier":round(brier(valid,0.),6) if valid else None,
        "validation_specialist_brier":round(brier(valid,blend),6) if valid else None}
