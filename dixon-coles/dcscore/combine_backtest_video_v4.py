"""Aggregate five October 2026 video-ready V4 backtest shards.

Full audit: exact 31 dates, V3/V4 matched fixture timelines, no duplicate
fixtures, stage-specific URL-gate exclusions, observed denominator and
uncertainty of retrospectively reconstructed ESPN fixtures.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

from .backtest_video_v4 import statistics


def merge(parts: Path, destination: Path) -> dict:
    paths=sorted(parts.glob("**/backtest_oct2026_v4.json"))
    if len(paths)!=5:
        raise ValueError(f"Expected exactly 5 V4 sharded JSON reports, got {len(paths)}")
    reports=[json.loads(path.read_text(encoding="utf-8")) for path in paths]
    days=sorted((d for r in reports for d in r["days"]),key=lambda x:x["date"])
    v3days=sorted((d for r in reports for d in r["paired_v3_days"]),key=lambda x:x["date"])
    matches=sorted((m for r in reports for m in r["matches"]),
                   key=lambda x:(x["date"],x["kickoff_utc"],x["id"]))
    v3matches=sorted((m for r in reports for m in r["paired_v3_matches"]),
                     key=lambda x:(x["date"],x["kickoff_utc"],x["id"]))
    required=[(date(2026,10,1)+timedelta(days=i)).isoformat() for i in range(31)]
    if [d["date"] for d in days]!=required:
        raise ValueError("V4 dates missing or duplicated")
    if [d["date"] for d in v3days]!=required:
        raise ValueError("V3 paired dates missing or duplicated")
    for version,day_rows,match_rows in (("V3",v3days,v3matches),("V4",days,matches)):
        ids=[(m["date"],m["id"]) for m in match_rows]
        if len(ids)!=len(set(ids)):
            raise ValueError(f"{version}: duplicate fixture ID")
        if sum(d["selected"] for d in day_rows)!=len(match_rows):
            raise ValueError(f"{version}: selected/day mismatch")
        for d in day_rows:
            if d["selected"]<0 or d["selected"]>10:
                raise ValueError(f"{version}: outside 0–10 validated cap")
        if any(m["date"] not in required for m in match_rows):
            raise ValueError(f"{version}: fixture date outside October")
    result=reports[0]
    result["period"]={"start":"2026-10-01","end":"2026-10-31"}
    result["days"]=days
    result["matches"]=matches
    result["paired_v3_days"]=v3days
    result["paired_v3_matches"]=v3matches
    v4stats=statistics(matches,days)
    v3stats=statistics(v3matches,v3days)
    v4stats.update({
        "days_with_1_to_9_flexible":sum(1<=d["selected"]<=9 and d["flexible_video_possible"]
                                        for d in days),
        "days_without_flexible":sum(not d["flexible_video_possible"] for d in days),
        "selection_changed_days":sum(d["selection_changed"] for d in days),
        "video_unsafe_rejected":sum(d["v4_renderable_rejections"] for d in days),
    })
    result["stats"]=v4stats
    result["paired_v3_stats"]=v3stats
    warnings=[msg for report in reports for day in report["days"]
              for msg in day.get("source_warnings",[])]
    result["data_quality"]["source_warnings_count"]=sum(
        report["data_quality"]["source_warnings_count"] for report in reports)
    result["data_quality"]["source_warnings_examples"]=sorted(set(warnings))[:20]
    result["status"]=(
        "NO_VERIFIABLE_BACKTEST_SAMPLE" if not v4stats["results_observed"]
        else "PARTIAL_SOURCE_COVERAGE" if result["data_quality"]["source_warnings_count"]
        else "COMPLETED_WITH_RETROSPECTIVE_FIXTURE_LIMITATION"
    )
    comparison={
        "matched_calendar_days":31,
        "same_data_source_and_cutoff":True,
        "v3":{"selected":v3stats["total_selected"],
              "strict_10_days":v3stats["video_ready_days"],
              "exact_hits":v3stats["top1_exact_hits"],
              "exact_percent":v3stats["top1_exact_hit_rate_percent"],
              "one_x_two_percent":v3stats["one_x_two_hit_rate_percent"]},
        "v4":{"selected":v4stats["total_selected"],
              "strict_10_days":v4stats["video_ready_days"],
              "flexible_days":v4stats["days_with_flexible_possible"],
              "partial_1_to_9_days":v4stats["days_with_1_to_9_flexible"],
              "zero_days":v4stats["days_without_flexible"],
              "exact_hits":v4stats["top1_exact_hits"],
              "exact_percent":v4stats["top1_exact_hit_rate_percent"],
              "one_x_two_percent":v4stats["one_x_two_hit_rate_percent"],
              "url_only_rejections":v4stats["video_unsafe_rejected"]},
        "changed_days":v4stats["selection_changed_days"],
        "limitations":[
            "Current ESPN scoreboard reconstruction; not immutable historical daily fixture snapshots.",
            "Valid crest URL strings only; no historical downloads/encoding/audio or provider publication success verified.",
            "No bookmaker odds: payout, ROI and profitability cannot be calculated.",
            "Changes in selected sample mean accuracy rates are descriptive, not causal proof.",
        ],
    }
    result["comparison"]=comparison
    destination.mkdir(parents=True,exist_ok=True)
    (destination/"backtest_v4_octobre_2026_complet.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for label,rows in (("v4",matches),("v3_paired",v3matches)):
        if rows:
            columns=["date","id","competition","competition_code","home","away",
                     "stage","importance","popularity_class","popularity_tier",
                     "predicted_exact","predicted_exact_probability","real_exact",
                     "top1_hit","top3_hit","top5_hit","predicted_1x2","real_1x2",
                     "one_x_two_hit","naive_1_1_hit","training_matches",
                     "last_known_result","history_days_old"]
            with (destination/f"backtest_{label}_octobre_2026_matchs.csv").open(
                    "w",encoding="utf-8",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=columns,extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
    with (destination/"backtest_v4_octobre_2026_jours.csv").open(
            "w",encoding="utf-8",newline="") as stream:
        fields=["date","discovered","eligible","selected","ready_for_video",
                "flexible_video_possible","v3_selected","v3_strict_video_ready",
                "selection_changed","v4_renderable_rejections"]
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(days)
    md=[
        "# Mr XPRONOS – Backtest V4 vidéo flexible, octobre 2026",
        "",
        "31 jours, replay V3 et V4 sur les mêmes flux ESPN et cutoffs (20:00 UTC la veille).",
        "Les vrais scores sont utilisés **uniquement après la prévision** pour l'évaluation.",
        "",
        "| Mesure | V3 appariée | V4 vidéo |",
        "|---|---:|---:|",
        f"| Pronostics sélectionnés | {v3stats['total_selected']} | {v4stats['total_selected']} |",
        f"| Journées strictes (10 matchs) | {v3stats['video_ready_days']}/31 | {v4stats['video_ready_days']}/31 |",
        f"| Journées flexibles (1 à 10) | non évalué | {v4stats['days_with_flexible_possible']}/31 |",
        f"| Journées V4 à 1–9 matchs | — | {v4stats['days_with_1_to_9_flexible']}/31 |",
        f"| Scores exacts | {v3stats['top1_exact_hits']}/{v3stats['results_observed']} | {v4stats['top1_exact_hits']}/{v4stats['results_observed']} |",
        f"| Taux de scores exacts | {v3stats['top1_exact_hit_rate_percent']} % | {v4stats['top1_exact_hit_rate_percent']} % |",
        f"| Taux 1N2 | {v3stats['one_x_two_hit_rate_percent']} % | {v4stats['one_x_two_hit_rate_percent']} % |",
        "",
        f"- Journées avec une sélection changée : **{v4stats['selection_changed_days']}**.",
        f"- Matchs écartés par les vérifications pré-vidéo : **{v4stats['video_unsafe_rejected']}**.",
        f"- Journées sans vidéo flexible admissible : **{v4stats['days_without_flexible']}**.",
        "",
        "## Résultat par championnat (V4)",
        "| Compétition | Pronostics | Scores exacts | Précision |",
        "|---|---:|---:|---:|",
    ]
    for comp,values in sorted(v4stats["by_competition"].items(),
                              key=lambda pair:-pair[1]["predictions"]):
        md.append(f"| {comp} | {values['predictions']} | {values['exact_hits']} | {values['exact_rate_percent']} % |")
    md += [
        "",
        "## Limites incontournables",
        "- URL de logo syntaxiquement valide ne prouve pas que le média aurait été téléchargé correctement.",
        "- Les rencontres passées ont été reconstruites depuis le calendrier ESPN consulté plus tard, pas des snapshots enregistrés la veille.",
        "- Aucun MP4 historique ni aucune publication Instagram/Facebook/YouTube/Threads/Bluesky n'est testé ici.",
        "- Ces tests ne mesurent ni les cotes ni le retour sur investissement.",
    ]
    (destination/"synthese_backtest_v4_octobre_2026.md").write_text(
        "\n".join(md)+"\n",encoding="utf-8")
    print("BACKTEST_V4_FULL_REPORT",json.dumps(
        {"status":result["status"],"comparison":comparison,
         "source_warnings":result["data_quality"]["source_warnings_count"]},
        ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--parts",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    merge(args.parts,args.out)


if __name__=="__main__":
    main()
