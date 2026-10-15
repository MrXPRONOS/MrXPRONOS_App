#!/usr/bin/env python3
"""1win anonymous prematch/share-bet capability probe.

No account creation, no stake entry, no wager confirmation. The script only:
- opens the public prematch sportsbook
- inspects rendered football markets
- if possible, clicks one harmless prematch selection
- inspects the resulting betslip/share controls and URL for a sharebet code
"""
import asyncio,datetime as dt,json,pathlib,re
from urllib.parse import urlsplit,parse_qs
from playwright.async_api import async_playwright

ROOT=pathlib.Path("odds_diagnostic_results")
OUT=ROOT/"onewin_togo_share_probe.json"
URLS=[
 "https://1win.com/bets/prematch/99",
 "https://1win.com/en/bets/prematch/99",
 "https://1win.com/betting",
]
TARGET=re.compile(r"(?:double chance|\bX2\b|\b1X\b|over\s*2[.,]5|under\s*2[.,]5|total)",re.I)
ODD=re.compile(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|[1-9]\d)[.,]\d{2,3}(?!\d)")
SHARE=re.compile(r"(?:share\s*bet|sharebet|booking\s*code|get\s*code|copy\s*code|load\s*code|bet\s*code)",re.I)
DANGER=re.compile(r"(?:place bet|bet now|confirm|stake|deposit|withdraw|cash out)",re.I)

async def t(el,limit=300):
    try:return re.sub(r"\s+"," ",(await el.inner_text(timeout=500)).strip())[:limit]
    except:return ""

async def inspect_page(page):
    body=(await page.locator("body").inner_text(timeout=5000))[:50000]
    controls=[]
    loc=page.locator("button,[role=button],a,[aria-label],[title]")
    for i in range(min(await loc.count(),1200)):
        n=loc.nth(i)
        try:
            if not await n.is_visible(timeout=70):continue
            vals=[await t(n,120),str(await n.get_attribute("aria-label") or ""),str(await n.get_attribute("title") or "")]
            label=" | ".join(dict.fromkeys(x.strip() for x in vals if x and x.strip()))
            if label and (SHARE.search(label) or TARGET.search(label)):
                controls.append(label[:220])
                if len(controls)>=100:break
        except:continue
    return body,controls

async def click_selection(page):
    nodes=page.locator("button,[role=button],a,div,span")
    samples=[]
    for i in range(min(await nodes.count(),2200)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=60):continue
            label=await t(n,130)
            if not label or DANGER.search(label) or not TARGET.search(label):continue
            parent=await t(n.locator("xpath=.."),320)
            odds=ODD.findall(parent)
            samples.append({"label":label,"parent":parent[:260],"odds":odds[:4]})
            if not odds:continue
            await n.click(timeout=1000)
            await page.wait_for_timeout(1000)
            return {"clicked":True,"label":label,"odd":odds[0],"context":parent[:350]},samples[:50]
        except:continue
    return {"clicked":False},samples[:50]

async def share_code_from_page(page):
    q=parse_qs(urlsplit(page.url).query)
    for key in ("sharebet","shareBet","booking","bookingCode","code"):
        vals=q.get(key,[])
        if vals and re.fullmatch(r"[A-Za-z0-9_-]{4,40}",vals[0] or ""):
            return vals[0],"url"
    body=(await page.locator("body").inner_text(timeout=5000))[:30000]
    for line in body.splitlines():
        if SHARE.search(line):
            m=re.search(r"([A-Za-z0-9_-]{5,32})",line)
            if m:return m.group(1),"labelled_text"
    return None,None

async def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    rep={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"attempts":[],
         "chosen_url":None,"http_status":None,"football_visible":False,
         "share_feature_visible":False,"selection":None,"market_samples":[],
         "share_code":None,"share_code_source":None,"status":"not_started"}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(service_workers="block")
        page=await ctx.new_page()
        try:
            for u in URLS:
                try:
                    r=await page.goto(u,wait_until="domcontentloaded",timeout=22000)
                    await page.wait_for_timeout(7000)
                    body,controls=await inspect_page(page)
                    att={"url":u,"http":r.status if r else None,"final_url":page.url,
                         "body_excerpt":re.sub(r"\s+"," ",body)[:1500],"controls":controls[:30]}
                    rep["attempts"].append(att)
                    if r and r.status<400 and ("football" in body.lower() or "prematch" in page.url.lower() or controls):
                        rep["chosen_url"]=page.url;rep["http_status"]=r.status if r else None
                        rep["football_visible"]="football" in body.lower()
                        rep["share_feature_visible"]=bool(SHARE.search(body) or any(SHARE.search(x) for x in controls))
                        break
                except Exception as e:
                    rep["attempts"].append({"url":u,"error_type":type(e).__name__})
            if not rep["chosen_url"]:
                rep["status"]="no_usable_public_sportsbook"
            else:
                sel,samples=await click_selection(page)
                rep["selection"]=sel;rep["market_samples"]=samples
                if sel.get("clicked"):
                    await page.wait_for_timeout(1200)
                    body2,controls2=await inspect_page(page)
                    rep["share_feature_visible"]=rep["share_feature_visible"] or bool(SHARE.search(body2) or any(SHARE.search(x) for x in controls2))
                    rep["post_selection_controls"]=controls2[:60]
                    code,src=await share_code_from_page(page)
                    rep["share_code"]=code;rep["share_code_source"]=src
                    rep["post_selection_url"]=page.url
                    rep["status"]="SHARE_CODE_EXPOSED" if code else "SELECTION_CLICKED_NO_SHARE_CODE"
                else:
                    rep["status"]="SPORTSBOOK_OPEN_NO_TARGET_SELECTION"
            try:await page.screenshot(path=str(ROOT/"onewin_togo_share_probe.png"),full_page=False,timeout=4000)
            except:pass
        except Exception as e:
            rep["status"]="browser_error";rep["error_type"]=type(e).__name__;rep["error"]=str(e)[:300]
        await ctx.close();await browser.close()
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(rep,indent=2,ensure_ascii=False))

if __name__=="__main__":asyncio.run(main())
