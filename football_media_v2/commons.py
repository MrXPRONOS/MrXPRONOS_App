"""Télécharge uniquement des photos d'illustration dont Wikimedia Commons expose
une licence commercialement réutilisable : CC0, PD, ou CC BY 4.0 / 3.0.

Cette découverte n'autorise PAS à republier des vidéos de matchs protégés.
L'attribution est intégrée aux descriptions. Si licence ou auteur ambigu : rejet.
"""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import requests

API='https://commons.wikimedia.org/w/api.php'
SEARCHES=['football player match soccer stadium','association football goalkeeper action','football stadium crowd soccer']
LICENSES={'CC0','CC0 1.0','Public domain','CC BY 4.0','CC BY 3.0','CC-BY-4.0','CC-BY-3.0'}
UA='MrXPRONOS-FootballStories/2.0 (educational-football-stories; attribution)'

def strip_html(txt:str)->str:
    cleaned=re.sub(r'<[^>]*>',' ',txt)
    cleaned=html.unescape(cleaned)
    return re.sub(r'\s+',' ',cleaned).strip()[:140]

def permitted(metadata:dict)->bool:
    if not metadata or not isinstance(metadata,dict): return False
    license_name=strip_html(metadata.get('LicenseShortName',{}).get('value',''))
    return license_name in LICENSES

def get_photos(folder:Path,maximum=4)->list[dict]:
    folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'commons_credits.json'
    if cache.exists():
        try:
            data=json.loads(cache.read_text('utf8'))
            found=[d for d in data if Path(d['file']).is_file()]
            if len(found)>=2:return found[:maximum]
        except (OSError,ValueError,KeyError):pass
    picked=[];visited=set()
    for query in SEARCHES:
        if len(picked)>=maximum:break
        try:
            r=requests.get(API,params={'action':'query','format':'json','generator':'search',
                 'gsrsearch':query,'gsrnamespace':6,'gsrlimit':20,'prop':'imageinfo',
                 'iiprop':'url|size|mime|extmetadata','iiurlwidth':'1200'},
                 headers={'User-Agent':UA},timeout=24)
            r.raise_for_status();pages=r.json().get('query',{}).get('pages',{}).values()
        except (requests.RequestException,ValueError):continue
        for page in pages:
            try:
                title=page.get('title','')
                if title in visited:continue
                visited.add(title)
                item=page['imageinfo'][0];metadata=item.get('extmetadata') or {}
                if not permitted(metadata):continue
                if item.get('mime') not in {'image/jpeg','image/png'}:continue
                if item.get('width',0)<900 or item.get('height',0)<600:continue
                url=item.get('thumburl') or item.get('url')
                source=item.get('descriptionurl','')
                # strict no redirect to untrusted hosts
                if urlparse(url).hostname not in {'upload.wikimedia.org','commons.wikimedia.org'}:continue
                author=strip_html(metadata.get('Artist',{}).get('value',''))
                license_short=strip_html(metadata.get('LicenseShortName',{}).get('value',''))
                license_url=metadata.get('LicenseUrl',{}).get('value','')
                if license_short.startswith('CC BY') and not author:continue
                if not source.startswith('https://commons.wikimedia.org/wiki/'):continue
                data=requests.get(url,headers={'User-Agent':UA},timeout=28)
                data.raise_for_status()
                if len(data.content)<16_000 or len(data.content)>12_000_000:continue
                ext='.jpg' if item.get('mime')=='image/jpeg' else '.png'
                filename=f'commons_{len(picked):02}{ext}'
                path=folder/filename
                path.write_bytes(data.content)
                # PIL verifies actual content before use
                from PIL import Image
                with Image.open(path) as im:
                    im.verify()
                picked.append({'file':str(path.resolve()),'title':title,'author':author,
                    'license':license_short,'license_url':license_url,'source':source})
                if len(picked)>=maximum:break
            except (requests.RequestException,ValueError,KeyError,OSError,TypeError):continue
    cache.write_text(json.dumps(picked,ensure_ascii=False,indent=2),encoding='utf8')
    return picked
