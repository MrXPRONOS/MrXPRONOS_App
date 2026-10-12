#!/usr/bin/env python3
"""Audit non destructif par défaut. Nettoyage OPTIONNEL uniquement des images
générées dans assets/images/editorial, non référencées et anciennes de >=30j.
Ne touche jamais aux images manuelles ni aux six templates Telegram.
"""
from __future__ import annotations
import argparse,json,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXTENSIONS={".png",".jpg",".jpeg",".webp",".gif",".mp4",".mov"}
GENERATED_PATTERN=re.compile(r"^(?:article|conseil|match|news)-.+-(?:og|social|story)\.webp$")

def references(root):
    used=set()
    for name in ("articles.json","conseils.json","footnews.json"):
        p=root/name
        if not p.exists():continue
        try: records=json.loads(p.read_text(encoding="utf-8"))
        except (OSError,ValueError):continue
        for obj in records if isinstance(records,list) else []:
            if not isinstance(obj,dict):continue
            for field in ("image_url","og_image","social_image","story_image","image"):
                v=obj.get(field)
                if isinstance(v,str) and v.startswith("assets/images/"):
                    used.add(v)
    # Les pages OG historiques peuvent encore utiliser d'anciennes images.
    for folder in ("articles", "conseils"):
        directory=root/folder
        for page in directory.glob("*/index.html") if directory.exists() else ():
            try:
                page_text=page.read_text(encoding="utf-8")
                used.update(re.findall(r"assets/images/editorial/[A-Za-z0-9_-]+\.webp",page_text))
            except OSError:
                continue
    ledger=root/"assets/data/editorial_share_queue.json"
    if ledger.is_file():
        try:
            entries=json.loads(ledger.read_text(encoding="utf-8"))
            for entry in entries if isinstance(entries,list) else []:
                if not isinstance(entry,dict): continue
                for key in ("image","story_image"):
                    value=entry.get(key)
                    if isinstance(value,str) and value.startswith("assets/images/editorial/"):
                        used.add(value)
        except (ValueError,OSError):
            pass
    return used

def scan(root=ROOT,top=35,prune=False,min_age_days=30):
    assets=root/"assets"
    media=[]
    for p in assets.rglob("*") if assets.exists() else ():
        if p.is_file() and p.suffix.lower() in EXTENSIONS:
            media.append({"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size})
    media.sort(key=lambda x:x["bytes"],reverse=True)
    used=references(root)
    editorial=root/"assets/images/editorial"
    orphan_candidates=[]
    for p in editorial.glob("*.webp") if editorial.exists() else ():
        rel=p.relative_to(root).as_posix()
        if (rel not in used and GENERATED_PATTERN.fullmatch(p.name)
                and p.stat().st_mtime<time.time()-max(min_age_days,30)*86400):
            orphan_candidates.append(rel)
    # Explicit prune only; a report never removes anything.
    if prune:
        for rel in orphan_candidates:
            target=(root/rel).resolve()
            if target.is_relative_to(editorial.resolve()) and target.is_file():
                target.unlink()
    result={"media_files":len(media),"media_megabytes":round(sum(x["bytes"] for x in media)/1048576,2),
            "largest":media[:top],"orphan_candidates":orphan_candidates[:100],
            "orphan_count":len(orphan_candidates),"automatic_deletion":False,
            "deleted_count":len(orphan_candidates) if prune else 0}
    print("EDITORIAL_STORAGE_AUDIT",json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--top",type=int,default=35)
    p.add_argument("--prune-editorial-orphans",action="store_true",
                   help="Supprime seulement les images WebP éditoriales non référencées >=30 jours")
    p.add_argument("--min-age-days",type=int,default=30)
    args=p.parse_args()
    scan(top=max(1,args.top),prune=args.prune_editorial_orphans,min_age_days=args.min_age_days)
