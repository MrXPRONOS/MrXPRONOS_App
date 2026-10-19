"""Generate a visually watermarked fake official #10 bulletin for QA only."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
from crypto import export_regulation_v2 as reg
from crypto import regulation_10_auto as auto

now=datetime.now(timezone.utc)
title="SEC proposes new regulation for crypto asset custody rules"
record=reg.parse_entry({
    "title":title,
    "link":"https://www.sec.gov/newsroom/press-releases/qa-crypto-announcement-simulation",
    "published_parsed":(now-timedelta(hours=2)).timetuple(),
},"SEC",now)

class OfficialFixture:
    status_code=200
    headers={"Content-Type":"text/html"}
    def raise_for_status(self): return None
    def iter_content(self,chunk_size=8192):
        yield ("<html><title>"+title+"</title><h1>"+title+
               "</h1><p>Fictional example used for QA poster only.</p></html>" +
               " "*400).encode()
    def close(self): pass

document=auto.verify_publication(record,now,getter=lambda url,**kw:OfficialFixture())
auto.validate_auto(document,now)
document["qa_only"]=True
path=Path("crypto/generated/test/regulation_10_auto_qa.json")
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("CRYPTO_REG10_QA_ONLY_SOURCE_FIXTURE",path)
