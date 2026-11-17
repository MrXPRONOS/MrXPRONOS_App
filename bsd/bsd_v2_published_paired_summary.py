"""Render paired BSD V2 research JSON as a standalone readable Markdown report."""
import argparse
import json
from pathlib import Path

LABELS = {
 "1":"Victoire domicile", "X":"Nul", "2":"Victoire extérieur",
 "1X":"Double chance 1X", "X2":"Double chance X2", "12":"Double chance 12",
 "BTTS_YES":"Les deux équipes marquent", "BTTS_NO":"Au moins une équipe ne marque pas",
 "OVER_15":"Plus de 1,5 but", "UNDER_15":"Moins de 1,5 but",
 "OVER_25":"Plus de 2,5 buts", "UNDER_25":"Moins de 2,5 buts",
 "OVER_35":"Plus de 3,5 buts", "UNDER_35":"Moins de 3,5 buts",
 "OVER_45":"Plus de 4,5 buts", "UNDER_45":"Moins de 4,5 buts",
 "HOME_OVER_05":"Domicile marque", "AWAY_OVER_05":"Extérieur marque",
 "HOME_UNDER_15":"Domicile marque moins de deux buts",
 "AWAY_UNDER_15":"Extérieur marque moins de deux buts",
 "AH_HOME_PLUS_15":"Handicap +1,5 domicile", "AH_AWAY_PLUS_15":"Handicap +1,5 extérieur",
 "DNB_HOME":"Remboursé si nul - domicile", "DNB_AWAY":"Remboursé si nul - extérieur",
 "HT_UNDER_15":"Moins de 1,5 but à la mi-temps",
}

def fmt(value):
 if value is None:return "—"
 return "%.2f %%"%(100*value)

def build(report):
 count=report["counts"];out=[
 "# Validation appariée BSD V2 — pronostics réellement archivés",
 "",
 "**Fenêtre des matchs enregistrés :** "+str(report["kickoff_from"])+" au "+str(report["kickoff_to"])+".",
 "",
 "Le backtest est restreint aux **identifiants de matchs présents dans le registre des publications**.",
 "Les historiques 2024–2025 ne servent qu'à entraîner et calibrer les modèles.",
 "",
 "## Périmètre et fidélité",
 "",
 "| Contrôle | Nombre |",
 "|---|---:|",
 ]
 for k,lab in (
  ("ledger_entries","Entrées dans le registre"),
  ("settled_ledger","Pronostics avec résultat"),
  ("pending_settlement","En attente de règlement"),
  ("settled_first_observed_prematch","Résultats avec première observation avant match"),
  ("settled_first_observed_after_kickoff","Résultats enregistrés au démarrage du registre après match"),
  ("verified_identical_scores","Scores identiques dans archive et registre"),
  ("original_market_settlement_agrees","Règlements du marché original concordants"),
  ("original_market_settlement_disagrees","Règlements du marché original discordants"),
  ("archived_match_not_found","Matchs absents de l'archive"),
  ("model_fixture_ineligible","Matchs sans caractéristiques historiques admissibles"),
 ):
  out.append("| "+lab+" | "+str(count.get(k,0))+" |")
 a=report["original_publication"].get("all",{})
 b=report["replay_same_original_market"].get("all",{})
 error=report["replay_original_probability_error"]
 out += [
 "",
 "## Comparaison appariée",
 "",
 "| Mesure sur les mêmes choix d'origine | Historique publié | Backtest rejoué |",
 "|---|---:|---:|",
 "| Nombre évalué | %s | %s |"%(a.get("n",0),b.get("n",0)),
 "| Victoires | %s | %s |"%(a.get("wins",0),b.get("wins",0)),
 "| Réussite | %s | %s |"%(fmt(a.get("rate")),fmt(b.get("rate"))),
 "| Brier | %s | %s |"%(a.get("brier"),b.get("brier")),
 "| Probabilité moyenne | %s | %s |"%(fmt(a.get("mean_probability")),fmt(b.get("mean_probability"))),
 "",
 "Écart moyen absolu des probabilités : **"+fmt(error.get("mean_absolute_error"))+"**, sur "+str(error.get("n"))+" observations.",
 "",
 "## Marché réellement choisi : historique vs reprise du même marché",
 "",
 "| Marché | Observations | Réussite publiée | Réussite du règlement rejoué |",
 "|---|---:|---:|---:|",
 ]
 publ=report["original_published_market_breakdown"]
 calc=report["replay_on_original_market_breakdown"]
 for key in sorted(publ):
  p=publ[key];q=calc.get(key,{})
  out.append("| "+LABELS.get(key,key)+" | "+str(p.get("n"))+" | "+fmt(p.get("rate"))+" | "+fmt(q.get("rate"))+" |")
 out+=["","## Tous les marchés sur les mêmes rencontres publiées","","| Marché | Matchs réglés | Réussite | Proba moyenne | Brier | Prédictions ≥79 % | Réussite sur ≥79 % |","|---|---:|---:|---:|---:|---:|---:|"]
 for key, item in sorted(report["market_recomputed_all_on_same_published_fixtures"].items()):
  sub=item.get("predicted_at_least_79pct",{})
  out.append("| "+LABELS.get(key,key)+" | "+str(item.get("n"))+" | "+fmt(item.get("rate"))+" | "+fmt(item.get("mean_probability"))+" | "+str(item.get("brier"))+" | "+str(sub.get("n",0))+" | "+fmt(sub.get("rate"))+" |")
 out+=["","## Sélection automatique du moteur sur les mêmes rencontres",""]
 for phase,label in (("prematch_first_observed","Vérification pré-match horodatée"),("counterfactual_late_record","Recalcul rétrospectif de publications tardivement enregistrées")):
  c=report["choice_replay"][phase]
  out += ["**"+label+"** — "+str(c["checked"])+" rencontres. "
          +str(c["with_choice"])+" propositions, "+str(c["no_choice"])+" sans sélection. "
          +str(c["same_market"])+" sélections identiques et "+str(c["different_market"])+" différentes. "
          +"Réussite du marché automatique : "+fmt(c["model_choice_performance"]["rate"])+".", ""]
 out+=["## Précautions","","- Une concordance des scores et des gains montre que le règlement est reproductible, pas que les pronostics sont rentables.","- La reproduction exacte du marché choisi est un test distinct, documenté ci-dessus.","- Les premières observations tardives ne constituent pas une preuve de publication pré-match.","- Les nouvelles options sont expérimentales, elles n'étaient pas proposées dans le système historique.","- Le pari remboursé si nul exclut les remboursements du calcul de taux de réussite.","- Ce rapport n'utilise aucune cote ou estimation de rentabilité.",""]
 return "\n".join(out)

def main():
 p=argparse.ArgumentParser();p.add_argument("--input",default="bsd/v2_published_paired_backtest_report.json")
 p.add_argument("--output",default="bsd/v2_published_paired_backtest_resume.md")
 a=p.parse_args()
 report=json.load(open(a.input,encoding="utf-8"))
 Path(a.output).write_text(build(report),encoding="utf-8")
 print("BSD_PUBLISHED_RESUME_READY",a.output)
if __name__=="__main__":main()
