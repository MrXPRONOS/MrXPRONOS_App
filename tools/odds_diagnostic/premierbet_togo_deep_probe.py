#!/usr/bin/env python3
import asyncio,datetime as dt,json,pathlib,re
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

ROOT=pathlib.Path("odds_diagnostic_results")
OUT=ROOT/"premierbet_togo_deep_probe.json"
ENTRY="https://sports2.premierbet.com/en/mini/Fixture/Category/143"

ODD=re.compile(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|[1-9]\d)[.,]\d{2,3}(?!\d)")
MARKET=re.compile(r"(?:double chance|over\s*[1234][.,]5|under\s*[1234][.,]5|total(?: goals?)?)",re.I)
DANGER=re.compile(r"(?:place bet|bet now|confirm|stake|deposit|withdraw|cash out|one.?click|parier|miser|valider)",re.I)
CODE_ACTION=re.compile(r"(?:book|booking|reserve|reservation|share|save|code|coupon|ticket)",re.I)
MATCH_PATH=re.compile(r"/mini/Fixture/Match/\d+",re.I)

async def txt(el,limit=300):
    try:return re.sub(r"\s+"," ",(await el.inner_text(timeout=500)).strip())[:limit]
    except:return ""

async def first_match(page):
    links=page.locator('a[href]')
    for i in range(min(await links.count(),800)):
        a=links.nth(i)
        try:
            if not await a.is_visible(timeout=80):continue
            href=await a.get_attribute("href")
            if not href:continue
            if MATCH_PATH.search(href):
                return await a.get_attribute("href"),await txt(a,160)
        except:continue
    return None,None

async def find_market_click(page):
    nodes=page.locator('button,[role="button"],a,div,span')
    for i in range(min(await nodes.count(),1800)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=70):continue
            t=await txt(n,110)
            if not t or DANGER.search(t) or not MARKET.search(t):continue
            context=await txt(n.locator("xpath=.."),260)
            odds=ODD.findall(context)
            if not odds:continue
            await n.click(timeout=1100)
            await page.wait_for_timeout(900)
            return {"label":t,"odd":odds[0],"context":context}
        except:continue
    return None

async def find_betslip(page):
    sels='[class*="betslip" i],[class*="bet-slip" i],[class*="coupon" i],[class*="ticket" i],[data-testid*="betslip" i]'
    loc=page.locator(sels)
    for i in range(min(await loc.count(),20)):
        n=loc.nth(i)
        try:
            if not await n.is_visible(timeout=100):continue
            t=await txt(n,1800)
            if ODD.search(t):return n,t
        except:continue
    # fallback: page section containing literal Betslip + an odd
    candidates=page.get_by_text(re.compile(r"\bBetslip\b",re.I))
    for i in range(min(await candidates.count(),20)):
        h=candidates.nth(i)
        try:
            if not await h.is_visible(timeout=100):continue
            cur=h
            for _ in range(4):
                cur=cur.locator("xpath=..")
                t=await txt(cur,1800)
                if ODD.search(t):return cur,t
        except:continue
    return None,None

async def actions(scope):
    out=[]
    els=scope.locator('button,[role="button"],a,[aria-label],[title]')
    for i in range(min(await els.count(),250)):
        e=els.nth(i)
        try:
            if not await e.is_visible(timeout=80):continue
            label=await txt(e,100)
            if not label:
                label=str(await e.get_attribute("aria-label") or await e.get_attribute("title") or "")
            label=re.sub(r"\s+"," ",label).strip()[:100]
            if label and CODE_ACTION.search(label) and not DANGER.search(label) and label not in out:
                out.append(label)
        except:continue
    return out[:60]

async def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    rep={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"entry":ENTRY,"http_status":None,
         "match_url":None,"match_text":None,"market":None,"betslip_verified":False,
         "betslip_text":None,"candidate_actions":[],"status":"not_started"}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(service_workers="block")
        page=await ctx.new_page()
        try:
            r=await page.goto(ENTRY,wait_until="domcontentloaded",timeout=25000)
            rep["http_status"]=r.status if r else None
            await page.wait_for_timeout(3500)
            href,mtext=await first_match(page)
            rep["match_text"]=mtext
            if not href:
                rep["status"]="no_public_match_link"
            else:
                url=href if href.startswith("http") else "https://sports2.premierbet.com"+href
                rep["match_url"]=url
                rr=await page.goto(url,wait_until="domcontentloaded",timeout=25000)
                rep["match_http"]=rr.status if rr else None
                await page.wait_for_timeout(3500)
                market=await find_market_click(page)
                rep["market"]=market
                if not market:
                    rep["status"]="no_clickable_double_chance_or_total"
                else:
                    slip,st=await find_betslip(page)
                    if not slip:
                        rep["status"]="selection_clicked_betslip_not_verified"
                    else:
                        rep["betslip_verified"]=True
                        rep["betslip_text"]=st[:1000]
                        rep["candidate_actions"]=await actions(slip)
                        rep["status"]="betslip_verified_actions_enumerated"
            try:await page.screenshot(path=str(ROOT/"premierbet_togo_deep_probe.png"),timeout=4000)
            except:pass
        except Exception as e:
            rep["status"]="browser_error";rep["error_type"]=type(e).__name__;rep["error"]=str(e)[:250]
        await ctx.close();await browser.close()
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(rep,indent=2,ensure_ascii=False))

if __name__=="__main__":asyncio.run(main())
