#!/usr/bin/env python3
"""Controle automatisé du contenu, liens, doublons et tailles d'images.
Par défaut, avertit sans supprimer aucune entrée.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
JSON_FILES=("articles.json","conseils.json","footnews.json")
def validate(root=ROOT, strict=False):
    issues=[]; warnings=[]; summary={}
    for fname in JSON_FILES:
        path=root/fname
        if not path.exists(): continue
        try:
            records=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(records,list): raise ValueError("not a list")
        except (ValueError,OSError) as exc:
            issues.append(f"{fname}: JSON invalide: {exc}");continue
        summary[fname]=len(records)
        seen_titles=set();seen_urls=set()
        for n,item in enumerate(records):
            if not isinstance(item,dict):
                issues.append(f"{fname}[{n}]: pas un objet");continue
            title=str(item.get("title") or "").strip()
            if not title or len(title)>250: issues.append(f"{fname}[{n}]: titre manquant ou trop long")
            key=re.sub(r"\W+","",title.casefold())
            if key in seen_titles: warnings.append(f"{fname}[{n}]: titre doublon historique")
            seen_titles.add(key)
            link=item.get("link")
            if link and (not isinstance(link,str) or not link.startswith("https://")):
                issues.append(f"{fname}[{n}]: lien source non HTTPS")
            if link and link in seen_urls: warnings.append(f"{fname}[{n}]: lien source doublon")
            if link:seen_urls.add(link)
            for field in ("image_url","social_image","story_image"):
                value=item.get(field)
                if not value or not str(value).startswith("assets/images/editorial/"):continue
                visual=root/value
                if not visual.is_file():
                    issues.append(f"{fname}[{n}]: fichier image absent {value}");continue
                try:
                    with Image.open(visual) as im:
                        expected={"image_url":(1200,630),"social_image":(1080,1080),"story_image":(1080,1920)}[field]
                        if im.size!=expected: issues.append(f"{fname}[{n}]: taille {field} incorrecte")
                        if im.format!="WEBP":issues.append(f"{fname}[{n}]: format {field} incorrect")
                except (OSError,ValueError):
                    issues.append(f"{fname}[{n}]: image corrompue {value}")
    result={"counts":summary,"problems":len(issues),"sample":issues[:30],"warnings":len(warnings),"warning_sample":warnings[:30]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if strict and issues else 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--strict",action="store_true")
    args=p.parse_args();sys.exit(validate(strict=args.strict))
