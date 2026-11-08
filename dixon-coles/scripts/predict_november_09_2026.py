"""One-off independent Dixon-Coles forecasts for verified Monday 2026-11-09 fixtures.
Source: open-matchday (noncommercial, attribution required); upstream feeds may lag.
No data from Mr XPRONOS legacy prediction engines is used.
This is an exploratory out-of-league extension, NOT a calibrated betting signal.
"""
from __future__ import annotations
import csv
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import requests
from dcscore.domain import Match
from dcscore.model import fit, forecast, ModelError

AS_OF = datetime(2026, 11, 8, 17, 25, tzinfo=timezone.utc)
BASE = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data"
SCHEDULE = [
    # League folder, displayed home, displayed away, data-name home, data-name away
    ("MEX_1_liga-mx", "León", "Chivas Guadalajara", "León", "Guadalajara"),
    ("MEX_1_liga-mx", "Querétaro", "Puebla", "Querétaro", "Puebla"),
    ("NOR_1_eliteserien", "Kristiansund", "Vålerenga", "Kristiansund", "Valerenga"),
    ("ESP_2_segunda-division", "Sabadell", "Real Sociedad B", "CD Sabadell", "Real Sociedad II"),
    ("ROU_1_liga-1", "FC Botoșani", "Oțelul Galați", "FC Botosani", "Otelul"),
    ("MEX_2_liga-expansion", "Piratas", "Cancún FC", "Piratas", "Cancún FC"),
    ("ENG_6_national-league-south", "Chelmsford", "Ebbsfleet United", "Chelmsford", "Ebbsfleet"),
]
# Other prominent November 9 fixtures verified with multiple live schedules but with
# insufficient per-league historical data in our permitted sources.
NOT_PREDICTED = [
    ("Atlético de Madrid (F)", "FC Badalona (F)", "Liga F", "No validated women's league match history"),
    ("AZ Picerno", "Bari", "Serie C", "No validated Serie C historical match data"),
    ("Universitario", "Deportivo Moquegua", "Peruvian Liga 1", "No verified historical league match data"),
]

def download(folder: str):
    url = f"{BASE}/{folder}/results_2627.csv"
    response = requests.get(url, timeout=35, headers={"User-Agent":"Dixon-Coles independent one-off evaluation"})
    response.raise_for_status()
    if len(response.content)>800_000:
        raise ValueError("Unexpected results data size")
    content = response.content.decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(content))
    if not {"date","home","away","ft_home","ft_away"}.issubset(reader.fieldnames or []):
        raise ValueError(f"Missing data headers for {folder}")
    games=[]
    teams=set()
    for i,row in enumerate(reader):
        date=row.get("date","").strip()
        name1=row.get("home","").strip()
        name2=row.get("away","").strip()
        h=row.get("ft_home","").strip()
        a=row.get("ft_away","").strip()
        if not h or not a or not name1 or not name2:
            continue
        hg,ag=int(h),int(a)
        if min(hg,ag)<0:
            raise ValueError("Invalid score")
        day=datetime.fromisoformat(date+"T12:00:00+00:00")
        if day>=AS_OF:
            continue
        if name1==name2:
            raise ValueError("Identical teams")
        game=Match(
            id=f"private:{folder}:{date}:{i}",competition=f"private:{folder}",
            kickoff=day,home_id=name1,away_id=name2,
            home_name=name1,away_name=name2,status="FINISHED",
            home_goals=hg,away_goals=ag,season="2026-27",
            source="open-matchday",result_provenance="csv_import")
        games.append(game);teams.update([name1,name2])
    return games,url,sorted(teams)

def main():
    output={"as_of_utc":AS_OF.isoformat(),"forecast_day":"2026-11-09",
            "engine":"MrXPRONOS independent dixon-coles/dcscore/model.py",
            "source":"open-matchday; original feeds credited by its maintainers",
            "source_rights":"Informational personal noncommercial analysis; not for commercial redistribution",
            "xi":0.0065,"regularization":0.15,
            "cross_league_calibration":False,
            "no_single_score_recommendation_without_per_league_validation":True,
            "matches":[],"unavailable":[]}
    cache={}
    for folder,home,away,home_id,away_id in SCHEDULE:
        if folder not in cache:
            cache[folder]=download(folder)
        games,url,teams=cache[folder]
        record={"home":home,"away":away,"league":folder,
                "training_matches":len(games),"last_result_date":max(m.kickoff.date().isoformat() for m in games),
                "data_url":url}
        if home_id not in teams or away_id not in teams:
            record["error"]="At least one team not in the available historical league results."
            output["unavailable"].append(record)
            continue
        counts={x:sum(m.home_id==x or m.away_id==x for m in games) for x in [home_id,away_id]}
        record["team_history"]=counts
        if len(games)<80 or min(counts.values())<5:
            record["error"]="Insufficient independent history (need 80 games and 5 for each team)."
            output["unavailable"].append(record)
            continue
        try:
            dc=fit(games,as_of=AS_OF,xi=0.0065,min_games=80,regularization=0.15,maxiter=650)
            poisson=fit(games,as_of=AS_OF,xi=0.0065,min_games=80,regularization=0.15,maxiter=650,rho_fixed=0.0)
            preds={}
            for model_name,model in [("dixon_coles",dc),("poisson_independent",poisson)]:
                data=forecast(model,home_id,away_id,top_n=5)
                preds[model_name]={
                    "top_5":data["top_scores"],
                    "goals_expected_home":round(data["expected_home_goals"],4) if "expected_home_goals" in data else None,
                    "goals_expected_away":round(data["expected_away_goals"],4) if "expected_away_goals" in data else None,
                    "p_1x2":data.get("one_x_two",data.get("p_1x2")),
                    "rho":round(model.rho,5),"gamma":round(model.gamma,5),
                }
            record["predictions"]=preds
            record["status"]="calculated_unvalidated_league"
            record["note"]="Top score is not an evidence-based standalone betting recommendation."
            output["matches"].append(record)
            print(f"PREDICTION {home} vs {away} | DC {preds['dixon_coles']['top_5'][0]['score']} ({preds['dixon_coles']['top_5'][0]['probability']:.2%}) | Poisson {preds['poisson_independent']['top_5'][0]['score']} ({preds['poisson_independent']['top_5'][0]['probability']:.2%}) | history {len(games)}")
        except (ModelError,ValueError) as e:
            record["error"]=f"Model cannot validly fit: {e}"
            output["unavailable"].append(record)
            print(f"NOT_CALCULATED {home} vs {away} | {e}")
    for home,away,league,reason in NOT_PREDICTED:
        output["unavailable"].append({"home":home,"away":away,"league":league,"error":reason})
    path=Path("results/forecast_2026_11_09_exploratory.json")
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY",json.dumps({"calculated":len(output["matches"]),"not_calculated":len(output["unavailable"]),"file":str(path)}))
    if len(output["matches"])<5:
        raise SystemExit("Insufficient valid calculations. Check data provider, no result should be presented as confirmed.")
if __name__=="__main__":
    main()
