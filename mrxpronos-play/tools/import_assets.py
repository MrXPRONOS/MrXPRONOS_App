#!/usr/bin/env python3
"""Importe les assets officiels de Mr XPRONOS Play depuis le ZIP vérifié.
Depuis la racine du dépôt :
  python mrxpronos-play/tools/import_assets.py /chemin/vers/Mr_XPRONOS_Play_Assets_50_GitHub.zip
Puis :
  git add mrxpronos-play/
  git commit -m "assets(play): publish 50 validated graphics"
  git push origin main
"""
import json,hashlib,zipfile,shutil,sys
from pathlib import Path
if len(sys.argv)!=2: sys.exit("Usage : python mrxpronos-play/tools/import_assets.py <archive.zip>")
repo=Path.cwd()
if not (repo/".git").exists(): sys.exit("Lancer depuis le dépôt GitHub cloné.")
with zipfile.ZipFile(Path(sys.argv[1]).expanduser()) as z:
    if z.testzip():sys.exit("Archive corrompue.")
    m=json.loads(z.read("mrxpronos-play/assets-manifest.json"))
    a=m["assets"]
    if sorted(x["number"] for x in a)!=list(range(1,51)):sys.exit("Les 50 numéros attendus ne sont pas présents.")
    entries=set()
    for x in a:
        png="mrxpronos-play/"+x["png_path"]
        webp="mrxpronos-play/"+x["webp_path"]
        if hashlib.sha256(z.read(png)).hexdigest()!=x["sha256_png"]:sys.exit("SHA incorrect : "+png)
        z.getinfo(webp);entries.update((png,webp))
    if len(entries)!=100:sys.exit("Il manque des fichiers ou il y a des doublons.")
    for name in sorted(entries|{"mrxpronos-play/assets-manifest.json","mrxpronos-play/assets-manifest.csv","mrxpronos-play/README.md"}):
        out=repo/name
        out.parent.mkdir(parents=True,exist_ok=True)
        with z.open(name) as f,out.open("wb") as g:shutil.copyfileobj(f,g)
    assert all((repo/n).is_file() for n in entries)
print("OK : 50 PNG, 50 WebP et manifeste importés, empreintes validées. Commit/push requis.")
