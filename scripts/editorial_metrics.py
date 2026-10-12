#!/usr/bin/env python3
"""Metrics locales de volume, variété et duplication. Pas de tracking utilisateur."""
import json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    result={}
    for file in ("articles.json","conseils.json","footnews.json"):
        path=ROOT/file
        if not path.exists():continue
        items=json.loads(path.read_text(encoding="utf-8"))
        titles=[str(x.get("title") or "").casefold().strip() for x in items if isinstance(x,dict)]
        result[file]={"count":len(titles),"unique_titles":len(set(titles)),
            "with_editorial_image":sum(str(x.get("image_url") or "").startswith("assets/images/editorial/") for x in items if isinstance(x,dict)),
            "visual_variants":dict(Counter(str(x.get("visual_variant") or "legacy") for x in items if isinstance(x,dict)))}
    out=ROOT/"assets/data/editorial_metrics.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
