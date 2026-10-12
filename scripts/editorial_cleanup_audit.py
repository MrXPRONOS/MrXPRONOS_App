#!/usr/bin/env python3
"""Audit sans destruction: repère fichiers lourds et médias probablement orphelins.

Aucun fichier n'est supprimé automatiquement: les ressources peuvent être utilisées
par HTML/CSS/JS de façon dynamique.
"""
from pathlib import Path
import argparse,json
ROOT=Path(__file__).resolve().parents[1]
EXTENSIONS={".png",".jpg",".jpeg",".webp",".gif",".mp4",".mov"}
IGNORED={".git","node_modules",".venv","__pycache__"}
def scan(root=ROOT,top=35):
    assets=root/"assets"
    media=[]
    for p in assets.rglob("*") if assets.exists() else ():
        if p.is_file() and p.suffix.lower() in EXTENSIONS:
            media.append({"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size})
    media.sort(key=lambda x:x["bytes"],reverse=True)
    result={"media_files":len(media),"media_megabytes":round(sum(x["bytes"] for x in media)/1048576,2),"largest":media[:top],"automatic_deletion":False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--top",type=int,default=35);args=p.parse_args()
    scan(top=max(1,args.top))
