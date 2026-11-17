"""Real-layout QA for #11 with fictional source, NEVER real-world news.

The data has the same schema as a news feed article, but is stored in a separate
file with qa_only=true. It cannot be delivered through test sender or production.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from crypto import export_regulation_11 as news

now=datetime.now(timezone.utc)
row=news.parse_entry({
 "title":"Ghana regulator proposes new crypto asset licensing rules for exchanges",
 "link":"https://www.coindesk.com/news/2026/10/19/ghana-crypto-licensing-fictional-qa-example",
 "published":(now-timedelta(hours=2)).isoformat(),
},"CoinDesk",now)
report=news.build(row,now)
report["qa_only"]=True
path=Path("crypto/generated/test/regulation_11_real_fixture.json")
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print("REG11_FICTITIOUS_REAL_LAYOUT_QA_ONLY",path)
