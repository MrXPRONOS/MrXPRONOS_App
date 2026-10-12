#!/usr/bin/env python3
"""Migre les slugs éditoriaux conflictuels sans changer les premiers liens existants.

Le premier slug valide reste identique; chaque doublon ultérieur reçoit un
suffixe stable dérivé de son contenu. Idempotent, réversible via git.
"""
from __future__ import annotations
import argparse,hashlib,json,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SAFE=re.compile(r"^[A-Za-z0-9_-]{2,180}$")

def slugify(raw):
    normalized=unicodedata.normalize("NFKD",str(raw or "")).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9-]","",re.sub(r"[\s_]+","-",normalized)).strip("-")[:130] or "contenu"

def fix_records(records):
    seen=set();counts={"duplicates_fixed":0,"invalid_fixed":0,"unchanged":0}
    for i,obj in enumerate(records):
        if not isinstance(obj,dict):continue
        original=str(obj.get("slug") or "").strip()
        base=original if SAFE.fullmatch(original) else slugify(original or obj.get("title") or f"contenu-{i}")
        if not SAFE.fullmatch(original):counts["invalid_fixed"]+=1
        proposed=base
        if proposed in seen:
            counts["duplicates_fixed"]+=1
            ident=hashlib.sha1(json.dumps([obj.get("title"),obj.get("content"),i],ensure_ascii=False).encode()).hexdigest()[:8]
            proposed=slugify(base)[:112]+"-"+ident
            while proposed in seen:
                ident=hashlib.sha1((ident+str(i)).encode()).hexdigest()[:8]
                proposed=slugify(base)[:112]+"-"+ident
        if proposed != original:
            obj["legacy_slug"]=original
            obj["slug"]=proposed
        else:counts["unchanged"]+=1
        seen.add(proposed)
    return counts

def migrate(root=ROOT,dry_run=False):
    result={}
    for filename in ("articles.json","conseils.json"):
        p=root/filename
        if not p.exists():continue
        data=json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data,list):raise ValueError(filename+" n'est pas une liste")
        counts=fix_records(data)
        result[filename]=counts
        if not dry_run and counts["duplicates_fixed"]+counts["invalid_fixed"]:
            p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EDITORIAL_UNIQUE_SLUGS",json.dumps(result,ensure_ascii=False))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    migrate(dry_run=not args.apply)
