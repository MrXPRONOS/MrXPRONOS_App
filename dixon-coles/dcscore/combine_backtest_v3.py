"""Merge five disjoint October Popularity V3 GitHub Action segments."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

from .backtest_top10_v3 import statistics


def combine(folder: Path, destination: Path):
    paths=sorted(folder.glob("**/backtest_oct2026_v3.json"))
    if len(paths)!=5:
        raise ValueError(f"Expected exactly 5 segment JSONs, got {len(paths)}")
    reports=[json.loads(path.read_text(encoding="utf-8")) for path in paths]
    days=sorted([day for report in reports for day in report["days"]],key=lambda x:x["date"])
    matches=sorted([match for report in reports for match in report["matches"]],
                   key=lambda x:(x["date"],x["kickoff_utc"],x["id"]))
    dates=[(date(2026,10,1)+timedelta(days=i)).isoformat() for i in range(31)]
    if [day["date"] for day in days]!=dates:
        raise ValueError("31 dates not accounted for exactly once")
    ids=[(m["date"],m["id"]) for m in matches]
    if len(set(ids))!=len(ids):
        raise ValueError("Repeated selected fixture across segments")
    if sum(day["selected"] for day in days)!=len(matches):
        raise ValueError("Selected match counts mismatch")
    result=reports[0]
    result["period"]={"start":"2026-10-01","end":"2026-10-31"}
    result["stats"]=statistics(matches,days)
    result["days"]=days
    result["matches"]=matches
    result["data_quality"]["source_warnings_count"]=sum(
        r["data_quality"]["source_warnings_count"] for r in reports)
    result["data_quality"]["source_warnings_examples"]=sorted(set(
        warning for r in reports for warning in r["data_quality"]["source_warnings_examples"]
    ))[:20]
    result["status"]=("NO_VERIFIABLE_BACKTEST_SAMPLE" if not result["stats"]["results_observed"]
                      else "PARTIAL_SOURCE_COVERAGE" if result["data_quality"]["source_warnings_count"]
                      else "COMPLETED_WITH_RETROSPECTIVE_FIXTURE_LIMITATION")
    destination.mkdir(parents=True,exist_ok=True)
    (destination/"backtest_oct2026_v3_complet.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if matches:
        cols=["date","competition","home","away","competition_code","stage",
              "popularity_class","popularity_tier","home_team_category","away_team_category",
              "importance","importance_reasons","predicted_exact",
              "predicted_exact_probability","real_exact","top1_hit","top3_hit",
              "top5_hit","predicted_1x2","real_1x2","one_x_two_hit",
              "naive_1_1_hit","training_matches","last_known_result","history_days_old"]
        with (destination/"backtest_oct2026_v3_matchs.csv").open("w",encoding="utf-8",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=cols,extrasaction="ignore")
            writer.writeheader();writer.writerows(matches)
    stats=result["stats"]
    summary=[
        "# Mr XPRONOS – Backtest Popularité V3, octobre 2026",
        "",
        "Rejeu rétroactif au cutoff 20 h UTC la veille. Sélection réelle V3,",
        "Compétitions activées après audit, jusqu'à 10 matchs/jour et filtres de production.",
        "",
        f"- Matchs disponibles : {stats['total_candidates']}",
        f"- Matchs retenus : {stats['total_selected']}",
        f"- Matchs évaluables : {stats['results_observed']}",
        f"- Score exact (Top 1) : {stats['top1_exact_hits']}/{stats['results_observed']} "
        f"({stats['top1_exact_hit_rate_percent']} %)",
        f"- Top 3 : {stats['top3_exact_hits']} ({stats['top3_exact_hit_rate_percent']} %)",
        f"- Top 5 : {stats['top5_exact_hits']} ({stats['top5_exact_hit_rate_percent']} %)",
        f"- Résultat 1N2 : {stats['one_x_two_hits']} ({stats['one_x_two_hit_rate_percent']} %)",
        f"- Journées avec vidéo stricte complète possible : {stats['video_ready_days']}/31",
        f"- Journées avec vidéo flexible théorique possible : {stats['days_with_flexible_possible']}/31",
        "",
        "## Compétitions",
        "| Compétition | Matchs | Scores exacts | %",
        "|---|---:|---:|---:|",
    ]
    for comp,values in sorted(stats["by_competition"].items(),
                              key=lambda pair:-pair[1]["predictions"]):
        summary.append(f"| {comp} | {values['predictions']} | "
                       f"{values['exact_hits']} | {values['exact_rate_percent']} |")
    summary += [
        "",
        "## Limites",
        "- Les calendriers sont reconstruits à partir d'ESPN aujourd'hui, "
        "pas de captures certifiées avant chaque match.",
        "- Les résultats postérieurs au cutoff sont exclus de l'entraînement et "
        "de la notation de popularité.",
        "- La comparaison avec la V2 à 131 matchs n'isole pas l'effet "
        "du classement : les compétitions et les effectifs analysés peuvent avoir changé.",
        "- Pas de cotes, donc pas de ROI calculable.",
        "",
    ]
    (destination/"synthese_backtest_popularite_v3.md").write_text(
        "\n".join(summary),encoding="utf-8")
    print("BACKTEST_V3_FULL_REPORT",json.dumps(
        {"status":result["status"],"stats":stats,
         "date_count":len(days),"match_count":len(matches),
         "source_warnings":result["data_quality"]["source_warnings_examples"][:5]},
        ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--parts",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();combine(a.parts,a.out)


if __name__=="__main__":
    main()
