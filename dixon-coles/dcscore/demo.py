"""Synthetic-only opt-in test dataset. Never mistake for real football results."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import numpy as np

from .domain import Match
from .store import Store


def load_demo(store: Store) -> dict:
    rng=np.random.default_rng(20261105)
    league="demo:SIM"
    teams=[f"Club Fictif {chr(65+i)}" for i in range(10)]
    attack=np.asarray([1.32,1.16,1.11,1.04,0.99,0.98,0.93,0.90,0.84,0.75])
    defense=np.asarray([0.76,0.83,0.90,0.96,1.04,1.01,1.12,1.06,1.20,1.27])
    now=datetime.now(timezone.utc)
    start=(now-timedelta(days=580)).replace(hour=15,minute=0,second=0,microsecond=0)
    rows=[]
    k=0
    # Round-robin repeated over a historical period, all before today's date.
    for cycle in range(3):
        for hi in range(10):
            for ai in range(10):
                if hi==ai:continue
                date=start+timedelta(days=k*1.9)
                k+=1
                if date>=now-timedelta(days=5):
                    continue
                h=int(rng.poisson(attack[hi]*defense[ai]*1.18))
                a=int(rng.poisson(attack[ai]*defense[hi]))
                rows.append(Match(id=f"demo:{cycle}:{hi}:{ai}",competition=league,kickoff=date,
                                  home_id=f"demo:{hi}",away_id=f"demo:{ai}",
                                  home_name=teams[hi],away_name=teams[ai],
                                  status="FINISHED",home_goals=h,away_goals=a,
                                  season="SIM",source="demo"))
    fixture=Match(id="demo:tomorrow",competition=league,
                  kickoff=now.replace(hour=18,minute=0,second=0,microsecond=0)+timedelta(days=1),
                  home_id="demo:0",away_id="demo:1",home_name=teams[0],away_name=teams[1],
                  status="SCHEDULED",season="SIM",source="demo")
    store.upsert_matches(rows+[fixture])
    return {"synthetic":True,"competition":league,"finished_games":len(rows),
            "example_match_id":fixture.id,"note":"Toutes les équipes et tous les résultats sont fictifs."}
