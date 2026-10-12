#!/usr/bin/env python3
"""Tableau de bord gratuit: couverture, diversité visuelle, file de diffusion, taille.
Les clics réels ne sont JAMAIS inventés. Les campagnes UTM restent mesurables.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets/data/editorial_share_queue.json"
OUT=ROOT/"assets/data/editorial_metrics.json"

def collect(root=ROOT):
    report={"contents":{},"delivery":{},"assets":{},"real_clicks":None,
            "conversion_rate":None,"ab_measurement":"requires real external analytics"}
    for file in ("articles.json","conseils.json","footnews.json"):
        path=root/file
        if not path.is_file():continue
        records=json.loads(path.read_text(encoding="utf-8"))
        valid=[x for x in records if isinstance(x,dict)]
        titles=[str(x.get("title") or "").casefold().strip() for x in valid]
        report["contents"][file]={
            "count":len(valid),"unique_titles":len(set(titles)),
            "with_editorial_image":sum(str(x.get("image_url") or "").startswith("assets/images/editorial/") for x in valid),
            "visual_variants":dict(sorted(Counter(str(x.get("visual_variant") or "legacy") for x in valid).items())),
            "source_types":dict(sorted(Counter(str(x.get("source") or x.get("type") or "unspecified") for x in valid).items())),
            "with_social_image":sum(bool(x.get("social_image")) for x in valid),
        }
    if (root/"assets/images/editorial").exists():
        media=[x for x in (root/"assets/images/editorial").rglob("*") if x.is_file()]
        report["assets"]={"files":len(media),"size_mb":round(sum(x.stat().st_size for x in media)/1048576,2),
                          "by_format":dict(sorted(Counter(x.suffix.lower() for x in media).items()))}
    queue=root/"assets/data/editorial_share_queue.json"
    if queue.is_file():
        items=json.loads(queue.read_text(encoding="utf-8"))
        status=Counter()
        for i in items:
            if not isinstance(i,dict):continue
            for platform,v in (i.get("platform_status") or {}).items():status[platform+":"+str(v)]+=1
        report["delivery"]={"items":len(items),"active_items":sum(not x.get("retired",False) for x in items if isinstance(x,dict)),
                            "retired_items":sum(bool(x.get("retired")) for x in items if isinstance(x,dict)),
                            "platform_states":dict(sorted(status.items()))}
    return report

def write(root=ROOT):
    result=collect(root)
    target=root/"assets/data/editorial_metrics.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EDITORIAL_METRICS",json.dumps(result,ensure_ascii=False))
    return result

if __name__=="__main__":write()
