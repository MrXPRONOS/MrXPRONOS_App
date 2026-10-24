"""Optional ML benchmark candidates. Libraries are NEVER silently substituted."""
from sklearn.ensemble import HistGradientBoostingRegressor

def candidate(name, *, seed=20261024):
    if name=="histgb":
        return HistGradientBoostingRegressor(loss="poisson",learning_rate=.055,
                 max_iter=95,max_leaf_nodes=18,l2_regularization=5,random_state=seed)
    if name=="lightgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(objective="poisson",n_estimators=120,learning_rate=.045,
                 num_leaves=12,reg_lambda=5,min_child_samples=30,random_state=seed,
                 verbosity=-1)
    if name=="catboost":
        from catboost import CatBoostRegressor
        # Poisson labels must be nonnegative.
        return CatBoostRegressor(loss_function="Poisson",iterations=120,depth=5,
                 learning_rate=.045,l2_leaf_reg=5,random_seed=seed,verbose=False,
                 thread_count=1)
    raise ValueError("Unknown candidate: "+str(name))

def fit_pair(candidate_name, rows, minimum=350):
    if len(rows)<minimum:return None
    import numpy as np
    X=np.array([r[0] for r in rows],float)
    yh=np.array([r[1] for r in rows],float)
    ya=np.array([r[2] for r in rows],float)
    fitted=[]
    for y in (yh,ya):
        model=candidate(candidate_name)
        model.fit(X,y)
        fitted.append(model)
    return fitted
