#!/usr/bin/env python3
"""Pages Open Graph statiques pour GitHub Pages, redirection vers la page dynamique.
Garde article.html?slug=... et conseil.html?slug=... pour éviter des régressions.
"""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
BASE="https://mrxpronos.github.io/MrXPRONOS_App/"
SAFE=re.compile(r"^[a-zA-Z0-9_-]{2,180}$")

def render(kind, item):
    slug=str(item["slug"])
    title=html.escape(str(item.get("title") or "Mr XPRONOS"),quote=True)
    desc=html.escape(str(item.get("meta_description") or item.get("excerpt") or item.get("summary") or "")[:220],quote=True)
    path=str(item.get("og_image") or item.get("image_url") or "assets/images/preview.jpg")
    if not path.startswith(("https://","http://")): path=BASE+path.lstrip("/")
    image=html.escape(path,quote=True)
    public=BASE+kind+"s/"+quote(slug)+"/"
    dest=BASE+("article.html" if kind=="article" else "conseil.html")+"?slug="+quote(slug)
    safe_dest=json.dumps(dest,ensure_ascii=True)
    # Un crawler lit les métadonnées statiques; un navigateur conserve les UTM.
    redirect_script="""<script>
(function(){
  var params = new URLSearchParams(window.location.search);
  var destination = new URL(__DEST__);
  ['utm_source','utm_medium','utm_campaign','utm_content'].forEach(function(key){
    var value=params.get(key);
    if(value && /^[A-Za-z0-9_-]{1,64}$/.test(value)) destination.searchParams.set(key,value);
  });
  window.location.replace(destination.toString());
})();
</script>""".replace("__DEST__",safe_dest)
    return f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Mr XPRONOS</title><meta name="description" content="{desc}">
<meta property="og:type" content="article"><meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}"><meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:url" content="{html.escape(public,quote=True)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}"><meta name="twitter:image" content="{image}">
<link rel="canonical" href="{html.escape(public,quote=True)}">
<meta http-equiv="refresh" content="3;url={html.escape(dest,quote=True)}">
{redirect_script}
</head><body><p>Redirection vers <a href="{html.escape(dest,quote=True)}">{title}</a>.</p></body></html>
'''

def build(root=ROOT, limit=None):
    counters={}
    for filename,kind,folder in (("articles.json","article","articles"),("conseils.json","conseil","conseils")):
        p=root/filename
        if not p.exists(): continue
        records=json.loads(p.read_text(encoding="utf-8"))
        count=0
        for item in records[:limit] if limit else records:
            if not isinstance(item,dict) or item.get("active") is False: continue
            slug=str(item.get("slug") or "")
            if not SAFE.fullmatch(slug): continue
            dest=root/folder/slug/"index.html"
            dest.parent.mkdir(parents=True,exist_ok=True)
            content=render(kind,item)
            if not dest.exists() or dest.read_text(encoding="utf-8")!=content:
                dest.write_text(content,encoding="utf-8")
            count+=1
        counters[folder]=count
    return counters

if __name__=="__main__":
    print("OG_STATIC_PAGES",json.dumps(build()))
