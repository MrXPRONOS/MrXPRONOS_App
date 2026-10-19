"""Generates an explicitly fake, non-publishable legal approval image for QA."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
from crypto.export_regulation_v2 import parse_entry,select_candidate
from crypto.regulation_10_approval import approved_report

now=datetime.now(timezone.utc)
a=parse_entry({
    "title":"SEC proposes new regulation for crypto asset custody rules",
    "link":"https://www.sec.gov/newsroom/press-releases/qa-simulation-not-real",
    "published_parsed":(now-timedelta(hours=2)).timetuple(),
},"SEC",now)
candidate=select_candidate([a],{"reviewed_urls":[]},now)
approval={
    "candidate_fingerprint":candidate["fingerprint"],
    "source_url":a["url"],"human_approved":True,
    "jurisdiction_checked":True,"stage_checked":True,"effective_date_checked":True,
    "primary_text_checked":True,"exceptions_checked":True,
    "approved_by":"Simulateur QA — pas un éditeur réel",
    "title_fr":"La SEC propose des règles sur la conservation des cryptoactifs",
    "summary_fr":"Maquette fictive pour vérifier le design d'une annonce réglementaire déjà relue. Aucun événement réel confirmé.",
    "jurisdiction":"ÉTATS-UNIS",
    "review_note":"Cette simulation QA n'est pas une approbation d'un événement.",
    "verified_stage":"PROPOSITION","effective_date":"non_applicable",
    "official_source":"SEC",
    "official_url":"https://www.sec.gov/newsroom/press-releases/qa-simulation-not-real",
    "reviewed_at":now.isoformat(),
}
out=approved_report(candidate,approval,now)
out["qa_only"]=True
p=Path("crypto/generated/test/regulation_v2_approved.json")
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("REG10_QA_FAKE_APPROVAL_NOT_PUBLISHABLE",p)
