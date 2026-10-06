#!/usr/bin/env python3
from __future__ import annotations
import io, json, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from PIL import Image

OUT = Path("prono-live/assets/bonus-banners")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7"})

SOURCES = {
  "1xbet-1": ("1xBet — Premier dépôt", "https://1xbet.com/fr/bonus/rules"),
  "1xbet-2": ("1xBet — Hyper Bonus", "https://1xbet.com/fr/bonus/rules/hyper_bonus"),
  "1xbet-3": ("1xBet — Lucky Friday", "https://1xbet.com/fr/promotions/lucky-friday"),
  "1xbet-4": ("1xBet — Crypto Freebet", "https://1xbet.com/fr/bonus/rules/crypto-freebet"),
  "1xbet-5": ("1xBet — Pari sans risque", "https://1xbet.com/fr/promotions/no-risk-bet"),

  "1win-1": ("1win — Bonus +500%", "https://1win.com/v3/landing-page/football?p=joz6"),
  "1win-2": ("1win — Fortune Rabbit", "https://1win.com/v3/2618/fortune-rabbit?p=lwi5"),
  "1win-3": ("1win — Sweet Bonanza", "https://1win.com/v3/2672/sweet-bonanza?p=8p84"),
  "1win-4": ("1win — Cashback hebdomadaire", "https://forum.1win.com/topic/44-%F0%9F%92%B0-get-up-to-30-cashback-on-your-weekly-losses/"),
  "1win-5": ("1win — 100 Free Spins Friday", "https://forum.1win.com/topic/111-%F0%9F%8E%81-collect-100-free-spins-every-friday/"),

  "betwinner-1": ("Betwinner — Premier dépôt", "https://guidebook.betwinner.com/fr/bonus-de-betwinner/bonus-de-premier-depot/"),
  "betwinner-2": ("Betwinner — Bonus du jeudi", "https://guidebook.betwinner.com/fr/bonus-de-betwinner/bonus-du-jeudi/"),
  "betwinner-3": ("Betwinner — Cashback sport", "https://guidebook.betwinner.com/fr/bonus-de-betwinner/remboursement-sur-les-sports/"),
  "betwinner-4": ("Betwinner — 20 paris perdants", "https://guidebook.betwinner.com/fr/bonus-de-betwinner/serie-de-20-paris-perdants/"),
  "betwinner-5": ("Betwinner — TOTO", "https://guidebook.betwinner.com/fr/bonus-de-betwinner/bonus-toto/"),

  "melbet-1": ("MelBet — Premier dépôt", "https://guidebook.melbet.com/fr/bonus/melbet-first-deposit-bonus/"),
  "melbet-2": ("MelBet — Bonus casino", "https://guidebook.melbet.com/fr/casino/"),
  "melbet-3": ("MelBet — Cashback application", "https://guidebook.melbet.com/fr/app/"),
  "melbet-4": ("MelBet — Code promo", "https://guidebook.melbet.com/fr/bonus/promo-code/"),
  "melbet-5": ("MelBet — Bonus & Cashback", "https://guidebook.melbet.com/fr/bonus/"),

  "linebet-1": ("Linebet — Premier dépôt", "https://linebet.com/fr/promotions/1st"),
  "linebet-2": ("Linebet — Pack casino", "https://linebet.com/fr/bonus/casino/promotions/slot_first_deposit"),
  "linebet-3": ("Linebet — Cashback hebdomadaire", "https://linebet.com/fr/bonus/rules/cash_sport"),
  "linebet-4": ("Linebet — Lundi Chanceux", "https://linebet.com/fr/bonus/rules/happy_monday"),
  "linebet-5": ("Linebet — Cashback VIP Casino", "https://linebet.com/fr/bonus/casino/promotions/vip_cashback"),

  "betclic-1": ("Betclic — Premier pari remboursé", "https://partner.betclic.fr/lp5/"),
  "betclic-2": ("Betclic — Offre mobile", "https://partner.betclic.ci/hello-world/"),
  "betclic-3": ("Betclic — Offre live", "https://partner.betclic.ci/meczlive/"),
  "betclic-4": ("Betclic — Bonus VIP", "https://partner.betclic.ci/bonusvip/"),
  "betclic-5": ("Betclic — But en Or", "https://promo.betclic.fr/but-en-or/"),
}

BAD = ("logo","favicon","sprite","icon","avatar","flag","qr","badge","payment","social","footer","header")
GOOD = ("promo","bonus","banner","hero","desktop","background","main","offer","welcome","cashback","freebet","deposit","friday")

def candidates_from_html(base_url: str, html: str):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for sel, attr in [
        ('meta[property="og:image"]', "content"),
        ('meta[property="og:image:secure_url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[property="twitter:image"]', "content"),
    ]:
        for el in soup.select(sel):
            if el.get(attr): found.append((urljoin(base_url, el.get(attr)), 100))
    for tag in soup.find_all(["img","source"]):
        for attr in ("src","data-src","data-original","data-lazy-src","srcset"):
            v=tag.get(attr)
            if not v: continue
            if attr=="srcset": v=v.split(",")[-1].strip().split(" ")[0]
            found.append((urljoin(base_url, v), 30))
    for m in re.findall(r'(?i)(https?:\\/\\/[^"\'<> )]+?\\.(?:webp|png|jpe?g)(?:\\?[^"\'<> )]*)?)', html):
        found.append((m.replace("\\/","/"), 20))
    for m in re.findall(r'(?i)url\\([\'"]?([^\'")]+\\.(?:webp|png|jpe?g)(?:\\?[^\'")]+)?)', html):
        found.append((urljoin(base_url, m), 25))
    out=[]; seen=set()
    for u,boost in found:
        if not u.startswith("http") or u in seen: continue
        seen.add(u); out.append((u,boost))
    return out

def try_image(url: str, referer: str, boost: int):
    try:
        r=SESSION.get(url, timeout=15, headers={"Referer":referer})
        if r.status_code!=200 or len(r.content)<5000: return None
        if "image" not in r.headers.get("content-type","") and not re.search(r'\\.(webp|png|jpe?g)(?:\\?|$)', url, re.I): return None
        im=Image.open(io.BytesIO(r.content)); im.load()
        w,h=im.size
        if w<420 or h<180: return None
        name=url.lower()
        ratio=w/max(1,h)
        score=boost + (w*h)/150000
        if 1.35 <= ratio <= 3.4: score += 55
        elif ratio < .8: score -= 35
        score += sum(18 for x in GOOD if x in name)
        score -= sum(40 for x in BAD if x in name)
        return score, im.convert("RGB"), url, (w,h)
    except Exception:
        return None

def save_webp(im: Image.Image, path: Path):
    maxw=1500
    if im.width>maxw:
        nh=round(im.height*(maxw/im.width))
        im=im.resize((maxw,nh), Image.LANCZOS)
    im.save(path, "WEBP", quality=86, method=6)

def scrape_banner(key: str, title: str, page_url: str):
    print(f"[{key}] {title} -> {page_url}", flush=True)
    try:
        r=SESSION.get(page_url, timeout=25, allow_redirects=True)
        r.raise_for_status()
        html=r.text
        items=[]
        for u,boost in candidates_from_html(r.url, html)[:100]:
            hit=try_image(u,r.url,boost)
            if hit: items.append(hit)
        if items:
            items.sort(key=lambda x:x[0], reverse=True)
            score,im,u,size=items[0]
            save_webp(im, OUT/f"{key}.webp")
            return {"mode":"asset","title":title,"page":r.url,"image":u,"size":size,"score":round(score,1)}
    except Exception as e:
        print(" scrape failed:",e, flush=True)
    return None

def screenshot_fallback(pending):
    if not pending: return {}
    from playwright.sync_api import sync_playwright
    results={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox"])
        page=browser.new_page(viewport={"width":1440,"height":900}, device_scale_factor=1)
        for key,title,url in pending:
            print(f"[{key}] screenshot fallback", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)
                # Dismiss common consent overlays when possible.
                for txt in ["Accepter","Tout accepter","Accept all","I agree","J’accepte","OK"]:
                    try:
                        loc=page.get_by_text(txt, exact=True)
                        if loc.count(): loc.first.click(timeout=700); page.wait_for_timeout(400)
                    except Exception: pass
                tmp=OUT/f"{key}.png"
                page.screenshot(path=str(tmp), full_page=False)
                im=Image.open(tmp).convert("RGB")
                # Keep a wide official-page crop.
                crop=im.crop((0,0,min(im.width,1440),min(im.height,760)))
                save_webp(crop, OUT/f"{key}.webp")
                tmp.unlink(missing_ok=True)
                results[key]={"mode":"official_page_screenshot","title":title,"page":page.url,"size":crop.size}
            except Exception as e:
                results[key]={"mode":"failed","title":title,"page":url,"error":str(e)}
        browser.close()
    return results

def main():
    manifest={}
    pending=[]
    for key,(title,url) in SOURCES.items():
        hit=scrape_banner(key,title,url)
        if hit: manifest[key]=hit
        else: pending.append((key,title,url))
        time.sleep(.25)
    manifest.update(screenshot_fallback(pending))
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    ok=sum(1 for x in manifest.values() if x.get("mode")!="failed")
    print(f"Saved {ok}/{len(SOURCES)} official promo visuals")

if __name__=="__main__":
    main()
