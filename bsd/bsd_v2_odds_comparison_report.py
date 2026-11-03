"""Human-readable and CSV report of model-vs-external odds."""
import argparse
import csv
import json
from pathlib import Path

FIELDS=[
 "event_id","home_team","away_team","league_name","kickoff","selection_key",
 "market_code","category","model_probability","model_conservative_probability",
 "model_indicative_odds","provider","bookmaker","provider_source","provider_odds",
 "absolute_difference","relative_difference_pct","provider_implied_probability_pct",
 "model_implied_probability_pct","quote_updated_at","quote_capture_at",
 "timestamp_kind",
]


def markdown(report):
    cov=report.get("coverage") or {}
    lines=[
        "# BSD V2 — Cotes indicatives vs fournisseurs externes",
        "",
        "Observation du : **"+str(report.get("captured_at"))+"** (UTC).",
        "",
        "**Méthode :** le marché est choisi sans regarder les cotes, puis sa cote",
        "indicative est calculée avec la fonction de production",
        "`price_selected_market(selection, {}, now)`. Chaque fournisseur est",
        "interrogé pour le **même match, le même marché et la même période FT**.",
        "Les cotes ne doivent pas dépasser deux heures d'âge.",
        "",
        "## Couverture",
        "",
        "| Mesure | Nombre |",
        "|---|---:|",
    ]
    for key,label in [
      ("upcoming_in_horizon","Matchs futurs disponibles dans la fenêtre"),
      ("fixtures_checked","Matchs examinés après plafonnement"),
      ("football_eligible_pro_vip_79","Pronostics Pro/VIP >=79 %"),
      ("model_indicative_publishable","Pronostics publiables avec prix indicatif du modèle"),
      ("distinct_fixtures_with_pairs","Matchs ayant au moins une cote externe comparable"),
      ("source_pairs_total","Paires de cotes comparables"),
      ("no_independent_quote","Pronostics sans fournisseur comparable"),
    ]:
        lines.append("| "+label+" | "+str(cov.get(key,0))+" |")
    lines.extend(["","## Résultats par fournisseur","","| Fournisseur | Paires | Écart moyen (externe − indicatif) | Écart médian absolu | Écart médian relatif |",
                  "|---|---:|---:|---:|---:|"])
    for name,info in report.get("by_provider",{}).items():
        def v(k,suf=""):
            x=info.get(k)
            return "—" if x is None else str(x)+suf
        lines.append("| "+name+" | "+v("comparisons")+" | "+v("mean_signed_difference")+
                     " | "+v("median_absolute_difference")+" | "+v("median_absolute_relative_pct"," %")+" |")
    lines += [
        "",
        "## Interprétation",
        "",
        "Un écart positif signifie que la cote externe est supérieure à la cote",
        "indicative calculée par Mr XPRONOS sur la **même sélection**.",
        "Cela **ne prouve pas** que le fournisseur se trompe, qu'une cote est",
        "meilleure ou qu'un pari est rentable. Ce sont deux prix de nature différente.",
        "",
        "Le prix modèle dépend de la probabilité estimée ; le prix externe est une",
        "observation horodatée d'un fournisseur ou d'un consensus. Une cote",
        "`bsd_consensus` n'est pas nécessairement la cote d'un bookmaker particulier.",
        "",
    ]
    if not report.get("pairs"):
        lines += [
            "**Aucune paire comparable dans cette exécution.** C'est une mesure",
            "de couverture, pas une validation des écarts de prix. Vérifier les",
            "identifiants de fournisseurs, la disponibilité des marchés et les quotas.",
            "",
        ]
    lines += ["## Paires vérifiées", "", "| Match | Marché | Fournisseur | Indication | Externe | Écart |",
              "|---|---|---|---:|---:|---:|"]
    for row in (report.get("pairs") or [])[:100]:
        match=str(row.get("home_team"))+" – "+str(row.get("away_team"))
        match=match.replace("|","/")
        lines.append("| "+match+" | "+str(row.get("selection_key"))+" | "+str(row.get("provider"))+
                     " | "+str(row.get("model_odds"))+" | "+str(row.get("provider_odds"))+
                     " | "+str(row.get("absolute_difference"))+" |")
    if len(report.get("pairs") or [])>100:
        lines.append("\nSeules les 100 premières paires sont affichées ; voir le fichier CSV pour toutes.")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="bsd/odds_indicative_vs_external_report.json")
    p.add_argument("--md",default="bsd/odds_indicative_vs_external_resume.md")
    p.add_argument("--csv",default="bsd/odds_indicative_vs_external_pairs.csv")
    args=p.parse_args()
    d=json.loads(Path(args.input).read_text(encoding="utf-8"))
    Path(args.md).write_text(markdown(d),encoding="utf-8")
    with open(args.csv,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        w.writeheader()
        w.writerows(d.get("pairs") or [])
    print("BSD_ODDS_COMPARISON_ARTIFACTS",json.dumps({
      "markdown":args.md,"csv":args.csv,"pairs":len(d.get("pairs") or [])
    }))

if __name__=="__main__":main()
