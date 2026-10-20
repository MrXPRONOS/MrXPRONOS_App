"""Private-side prospective metrics and standalone HTML dashboard, shadow only.

Aggregates contain no match identifiers, names, picks or source odds.
Never makes a claim of probability calibration from a tiny sample.
"""
from __future__ import annotations
import argparse
import html
import json
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

from exact_scores_prospective import MODEL, LEDGER, read_ledger, report


def wilson95(hits, count):
    if not count:
        return None
    z=1.96
    p=hits/count
    den=1+z*z/count
    center=(p+z*z/(2*count))/den
    half=z*sqrt((p*(1-p)+z*z/(4*count*count)))/den
    return [round(max(0,center-half),5),round(min(1,center+half),5)]


def aggregates(ledger, now):
    base=report(ledger,now)
    rows=list(ledger["predictions"].values())
    finished=[r for r in rows if r["status"]=="settled"]
    by_month=defaultdict(list)
    for r in finished:
        month=r["kickoff_utc"][:7]
        by_month[month].append(r)
    def summary(items):
        n=len(items)
        top1=sum(x["top1_hit"] for x in items)
        top3=sum(x["top3_hit"] for x in items)
        under=sum(x["under25_hit"] for x in items)
        brier=sum((x["under25"]["probability"]-x["under25_hit"])**2 for x in items)
        return {"n":n,
                "top1_hits":top1,"top3_hits":top3,"under25_hits":under,
                "top1_rate":round(top1/n,5) if n else None,
                "top3_rate":round(top3/n,5) if n else None,
                "under25_rate":round(under/n,5) if n else None,
                "under25_brier":round(brier/n,6) if n else None,
                "top1_wilson95":wilson95(top1,n),
                "top3_wilson95":wilson95(top3,n)}
    base["all"]=summary(finished)
    base["priority"]=summary([r for r in finished if r["selected"]])
    base["monthly"]={m:{"all":summary(items),
                        "priority":summary([r for r in items if r["selected"]])}
                     for m,items in sorted(by_month.items())}
    base["selection_rate"]=round(base["priority_captured"]/base["total_captured"],6) if base["total_captured"] else None
    base["samples_required_for_stability"]=100
    base["validated"] = base["priority"]["n"] >= 100
    base["prospective_only"]=True
    base["historical_reference"]={"n":124,"top1_rate":.19355,"top3_rate":.49194,
                                  "under25_rate":.70968,
                                  "label":"2026 retrospective; not a performance target or forecast"}
    return base


def percent(x):
    return "—" if x is None else f"{100*x:.2f} %"


def html_report(data):
    n=data["priority"]["n"]
    last=data["created_utc"]
    def card(title,value,sub):
        return (f'<section class="stat"><span>{html.escape(title)}</span>'
                f'<strong>{html.escape(str(value))}</strong><small>{html.escape(sub)}</small></section>')
    cards=(
        card("Prévisions capturées",data["total_captured"],"Avant coup d’envoi")+
        card("En attente",data["pending"],"Non comptées comme perdues")+
        card("Terminées",data["all"]["n"],"Scores réellement confirmés")+
        card("Matchs prioritaires terminés",n,
             "Échantillon limité" if n<100 else "Échantillon à contrôler")+
        card("Top 1 prioritaires",percent(data["priority"]["top1_rate"]),"Score exact le plus probable")+
        card("Top 3 prioritaires",percent(data["priority"]["top3_rate"]),"Bonne réponse parmi trois scores")+
        card("Under 2,5 prioritaires",percent(data["priority"]["under25_rate"]),"Moins de 3 buts au total")+
        card("Brier Under 2,5",data["priority"]["under25_brier"] if n else "—",
             "Plus petit = meilleure calibration")
    )
    rows=""
    for month,groups in data["monthly"].items():
        a,p=groups["all"],groups["priority"]
        rows+=("<tr><td>"+html.escape(month)+"</td><td>"+str(a["n"])+"</td><td>"+
               str(p["n"])+"</td><td>"+percent(p["top1_rate"])+"</td><td>"+
               percent(p["top3_rate"])+"</td><td>"+percent(p["under25_rate"])+"</td></tr>")
    if not rows:
        rows='<tr><td colspan="6" class="empty">Aucun match réglé pour le moment</td></tr>'
    status=("Prise de recul nécessaire : moins de 100 matchs prioritaires réglés."
            if n<100 else "Seuil minimal atteint : vérifier aussi la stabilité par mois et les intervalles.")
    # Strictly no fixture-level details, cookies, external data/scripts, or betting URLs.
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mr XPRONOS — Suivi prospectif des scores exacts</title>
<style>
:root{{--bg:#0b1120;--panel:#141e31;--stroke:#293951;--ink:#f6f9ff;--muted:#9db0c9;--orange:#ffab4f}}
*{{box-sizing:border-box}}body{{background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Arial,sans-serif;margin:0}}
main{{max-width:1140px;margin:0 auto;padding:30px 20px 55px}}header{{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}}
h1{{font-size:clamp(25px,4vw,42px);line-height:1.15;margin:12px 0}}h2{{font-size:20px;margin:32px 0 14px}}
.muted,small{{color:var(--muted)}}.tag{{border:1px solid #5d7a9e;color:#e6effe;border-radius:25px;padding:6px 12px;font-size:12px}}
.accent{{color:var(--orange)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:24px 0}}
.stat{{padding:19px;background:var(--panel);border:1px solid var(--stroke);border-radius:14px;min-height:132px;display:flex;flex-direction:column;gap:8px}}
.stat span{{font-size:13px;color:var(--muted)}}.stat strong{{font-size:29px;line-height:1.2}}.stat small{{font-size:11px}}
.note{{background:#172238;border-left:3px solid var(--orange);padding:16px 18px;border-radius:8px;margin-top:20px}}
table{{border-collapse:collapse;width:100%;background:var(--panel);border-radius:12px;overflow:hidden}}
th,td{{border-bottom:1px solid var(--stroke);text-align:left;padding:12px 14px;white-space:nowrap}}
th{{color:var(--muted);font-size:12px}}.scroll{{overflow-x:auto}}.empty{{text-align:center;color:var(--muted);padding:32px}}
footer{{color:var(--muted);font-size:12px;margin-top:25px}}
@media(max-width:800px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:430px){{.grid{{gap:8px}}.stat{{padding:13px;min-height:115px}}.stat strong{{font-size:23px}}}}
</style></head><body><main><header><div><div class="accent"><b>MR XPRONOS</b> · STATISTIQUES</div>
<h1>Tableau de bord <span class="accent">prospectif</span></h1>
<div class="muted">Prévisions horodatées, figées avant le match. Modèle : {html.escape(data["model"])}</div></div>
<div class="tag">EXPÉRIMENTAL · NON PUBLIÉ</div></header><div class="grid">{cards}</div>
<div class="note"><strong>{html.escape(status)}</strong><div class="muted">Intervalles à 95 % et couverture doivent être examinés avant toute activation publique. Matchs sans résultat : {data["overdue_unsettled"]}. Taux de sélection : {percent(data["selection_rate"])}.</div></div>
<h2>Résultats par mois</h2><div class="scroll"><table><thead><tr><th>Mois</th><th>Terminés</th><th>Prioritaires</th><th>Top 1</th><th>Top 3</th><th>Under 2,5</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<footer>Actualisé : {html.escape(last)} · Résultats futurs uniquement, sans cotes, sans rendement garanti. Référence historique Top 3 : 49,19 % / 124 matchs, exploratoire et non comparable directement.</footer></main></body></html>"""


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ledger",default=str(LEDGER))
    parser.add_argument("--output",default="tmp/exact-scores/prospective-dashboard.html")
    parser.add_argument("--summary",default="tmp/exact-scores/prospective-dashboard.json")
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    ledger=read_ledger(Path(args.ledger))
    data=aggregates(ledger,now)
    for filename,body in ((args.output,html_report(data)),
                          (args.summary,json.dumps(data,ensure_ascii=False,indent=2))):
        path=Path(filename)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(body,encoding="utf-8")
    print("PROSPECTIVE_DASHBOARD",
          json.dumps({"captured":data["total_captured"],
                      "settled":data["all"]["n"],
                      "priority_settled":data["priority"]["n"],
                      "overdue":data["overdue_unsettled"]},ensure_ascii=False))


if __name__=="__main__":
    main()
