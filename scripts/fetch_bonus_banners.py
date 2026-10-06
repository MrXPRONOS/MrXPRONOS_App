#!/usr/bin/env python3
from __future__ import annotations
import io, json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from PIL import Image
from playwright.sync_api import sync_playwright

OUT=Path("prono-live/assets/bonus-banners")
OUT.mkdir(parents=True,exist_ok=True)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36"
S=requests.Session(); S.headers.update({"User-Agent":UA,"Accept-Language":"fr-FR,fr;q=0.9,en;q=0.7"})

SOURCES={
"1xbet-1":("1xBet — Premier dépôt","https://1xbet.com/fr/bonus/rules"),
"1xbet-2":("1xBet — Hyper Bonus","https://1xbet.com/fr/bonus/rules/hyper_bonus"),
"1xbet-3":("1xBet — Lucky Friday","https://1xbet.com/fr/promotions/lucky-friday"),
"1xbet-4":("1xBet — Crypto Freebet","https://1xbet.com/fr/bonus/rules/crypto-freebet"),
"1xbet-5":("1xBet — Pari sans risque","https://1xbet.com/fr/promotions/no-risk-bet"),
"1win-1":("1win — Bonus bienvenue","https://1win.com/v3/landing-page/football?p=joz6"),
"1win-2":("1win — Promotion 2","https://1win.com/"),
"1win-3":("1win — Promotion 3","https://1win.com/"),
"1win-4":("1win — Cashback","https://forum.1win.com/topic/44-%F0%9F%92%B0-get-up-to-30-cashback-on-your-weekly-losses/"),
"1win-5":("1win — Free Spins Friday","https://forum.1win.com/topic/111-%F0%9F%8E%81-collect-100-free-spins-every-friday/"),
"betwinner-1":("Betwinner — Premier dépôt","https://guidebook.betwinner.com/fr/bonus-de-betwinner/bonus-de-premier-depot/"),
"betwinner-2":("Betwinner — Bonus du jeudi","https://guidebook.betwinner.com/fr/bonus-de-betwinner/bonus-du-jeudi/"),
"betwinner-3":("Betwinner — Cashback sport","https://guidebook.betwinner.com/fr/bonus-de-betwinner/remboursement-sur-les-sports/"),
"betwinner-4":("Betwinner — 20 paris perdants","https://guidebook.betwinner.com/fr/bonus-de-betwinner/serie-de-20-paris-perdants/"),
"betwinner-5":("Betwinner — TOTO","https://guidebook.betwinner.com/fr/bonus-de-betwinner/bonus-toto/"),
"melbet-1":("MelBet — Premier dépôt","https://guidebook.melbet.com/fr/bonus/melbet-first-deposit-bonus/"),
"melbet-2":("MelBet — Bonus casino","https://guidebook.melbet.com/fr/casino/"),
"melbet-3":("MelBet — Bonus application","https://guidebook.melbet.com/fr/app/"),
"melbet-4":("MelBet — Code promo","https://guidebook.melbet.com/fr/bonus/promo-code/"),
"melbet-5":("MelBet — Bonus & Cashback","https://guidebook.melbet.com/fr/bonus/"),
"linebet-1":("Linebet — Premier dépôt","https://linebet.com/fr/promotions/1st"),
"linebet-2":("Linebet — Pack casino","https://linebet.com/fr/bonus/casino/promotions/slot_first_deposit"),
"linebet-3":("Linebet — Cashback hebdomadaire","https://linebet.com/fr/bonus/rules/cash_sport"),
"linebet-4":("Linebet — Lundi Chanceux","https://linebet.com/fr/bonus/rules/happy_monday"),
"linebet-5":("Linebet — Cashback VIP Casino","https://linebet.com/fr/bonus/casino/promotions/vip_cashback"),
"betclic-1":("Betclic — Bienvenue","https://partner.betclic.fr/lp5/"),
"betclic-2":("Betclic — Offre mobile","https://partner.betclic.ci/hello-world/"),
"betclic-3":("Betclic — Offre live","https://partner.betclic.ci/meczlive/"),
"betclic-4":("Betclic — Bonus VIP","https://partner.betclic.ci/bonusvip/"),
"betclic-5":("Betclic — But en Or","https://promo.betclic.fr/but-en-or/")
}

GOOD=("promo","bonus","banner","hero","welcome","cashback","freebet","deposit","friday","offer","campaign","desktop","main")
BAD=("logo","favicon","sprite","icon","avatar","flag","qr","payment","social","footer","header","trustpilot","cookie")

def save_webp(im:Image.Image,path:Path):
    im=im.convert("RGB")
    if im.width>1600:
        h=round(im.height*1600/im.width); im=im.resize((1600,h),Image.LANCZOS)
    im.save(path,"WEBP",quality=88,method=6)

def download_image(url,referer):
    try:
        r=S.get(url,timeout=20,headers={"Referer":referer})
        if r.status_code!=200 or len(r.content)<6000:return None
        im=Image.open(io.BytesIO(r.content)); im.load()
        if im.width<500 or im.height<180:return None
        return im
    except Exception:return None

def score_candidate(c):
    w,h=c.get("w",0),c.get("h",0)
    if w<420 or h<160:return -9999
    ratio=w/max(h,1)
    if ratio<1.15 or ratio>4.2:return -9999
    txt=(" ".join([c.get("src",""),c.get("alt",""),c.get("cls","")])).lower()
    score=(w*h)/9000
    if 1.45<=ratio<=3.4:score+=80
    score+=sum(30 for x in GOOD if x in txt)
    score-=sum(90 for x in BAD if x in txt)
    return score

def dismiss(page):
    for txt in ["Tout accepter","Accepter","Accept all","I agree","J’accepte","OK","Continuer"]:
        try:
            loc=page.get_by_text(txt,exact=True)
            if loc.count():loc.first.click(timeout=650);page.wait_for_timeout(250)
        except Exception:pass

def collect_candidates(page):
    return page.evaluate("""() => {
      const out=[];
      document.querySelectorAll('img').forEach(el=>{
        const r=el.getBoundingClientRect();
        const s=el.currentSrc||el.src||'';
        if(s && r.width>0 && r.height>0)out.push({src:s,w:r.width,h:r.height,alt:el.alt||'',cls:el.className||'',kind:'img'});
      });
      document.querySelectorAll('body *').forEach(el=>{
        const r=el.getBoundingClientRect();
        if(r.width<420||r.height<160||r.width>1800||r.height>1100)return;
        const bg=getComputedStyle(el).backgroundImage||'';
        const m=bg.match(/url\\(["']?(.+?)["']?\\)/);
        if(m&&m[1])out.push({src:m[1],w:r.width,h:r.height,alt:'',cls:(el.className||'')+' '+(el.id||''),kind:'bg'});
      });
      return out;
    }""")

def element_screenshot(page,path):
    selectors=['[class*="promo"]','[class*="banner"]','[class*="hero"]','main section','section']
    best=None
    for sel in selectors:
        try:
            for i in range(min(page.locator(sel).count(),40)):
                el=page.locator(sel).nth(i)
                box=el.bounding_box()
                if not box:continue
                w,h=box["width"],box["height"]
                if w<600 or h<220 or h>900:continue
                ratio=w/max(h,1)
                if not (1.2<=ratio<=4.2):continue
                area=w*h
                if best is None or area>best[0]:best=(area,el)
        except Exception:pass
    if best:
        tmp=path.with_suffix(".png")
        best[1].screenshot(path=str(tmp))
        im=Image.open(tmp); save_webp(im,path); tmp.unlink(missing_ok=True)
        return True
    return False

def main():
    manifest={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        page=browser.new_page(viewport={"width":1440,"height":900},device_scale_factor=1,user_agent=UA,locale="fr-FR")
        for key,(title,url) in SOURCES.items():
            print(f"[{key}] {title}",flush=True)
            entry={"title":title,"source":url}
            try:
                page.goto(url,wait_until="domcontentloaded",timeout=50000)
                page.wait_for_timeout(3000);dismiss(page);page.wait_for_timeout(700)
                candidates=collect_candidates(page)
                candidates=sorted(candidates,key=score_candidate,reverse=True)
                saved=False
                for c in candidates[:20]:
                    if score_candidate(c)<0:continue
                    src=urljoin(page.url,c["src"])
                    im=download_image(src,page.url)
                    if im:
                        save_webp(im,OUT/f"{key}.webp")
                        entry.update({"mode":"official_banner","image":src,"page":page.url,"size":[im.width,im.height]})
                        saved=True;break
                if not saved and element_screenshot(page,OUT/f"{key}.webp"):
                    entry.update({"mode":"official_promo_element","page":page.url})
                    saved=True
                if not saved:
                    tmp=OUT/f"{key}.png";page.screenshot(path=str(tmp),full_page=False)
                    im=Image.open(tmp).crop((0,0,1440,760));save_webp(im,OUT/f"{key}.webp");tmp.unlink(missing_ok=True)
                    entry.update({"mode":"official_page_crop","page":page.url})
            except Exception as e:
                entry.update({"mode":"failed","error":str(e)})
                print("  failed:",e,flush=True)
            manifest[key]=entry
            time.sleep(.2)
        browser.close()
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Saved",sum(v.get("mode")!="failed" for v in manifest.values()),"/",len(SOURCES),"visuals",flush=True)

if __name__=="__main__":main()
