"""Research alternatives only; baseline score engine remains unchanged."""
from math import exp, factorial, lgamma, log
from exact_scores import matrix_for

def normalize(d):
    total=sum(d.values())
    if total<=0:raise ValueError("invalid score matrix")
    return {k:v/total for k,v in d.items()}

def poisson(k,mean):return exp(-mean)*mean**k/factorial(k)

def bivariate(home,away,shared=.12,max_goals=12):
    if shared<0 or shared>=min(home,away):raise ValueError("invalid shared intensity")
    return normalize({(h,a):sum(poisson(h-k,home-shared)*poisson(a-k,away-shared)*
                  poisson(k,shared) for k in range(min(h,a)+1))
                  for h in range(max_goals+1) for a in range(max_goals+1)})

def negative_binomial(home,away,dispersion=2.5,max_goals=12):
    if min(home,away,dispersion)<=0:raise ValueError("invalid dispersion")
    def pmf(k,mu):
        p=dispersion/(dispersion+mu)
        return exp(lgamma(k+dispersion)-lgamma(dispersion)-lgamma(k+1)
                   +dispersion*log(p)+k*log(1-p))
    return normalize({(h,a):pmf(h,home)*pmf(a,away) for h in range(max_goals+1)
                      for a in range(max_goals+1)})

def candidates(home,away):
    h=max(.1,min(5.,home*1.10));a=max(.1,min(5.,away))
    return {"poisson":matrix_for(home,away,scale_home=1.10),
            "dixon_coles_rho_neg_008":matrix_for(home,away,scale_home=1.10,rho=-.08),
            "bivariate_shared_012":bivariate(h,a,shared=min(.12,h*.5,a*.5)),
            "negative_binomial_dispersion_25":negative_binomial(h,a)}
