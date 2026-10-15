#!/usr/bin/env python3
import asyncio, datetime as dt, json, pathlib, re
from playwright.async_api import async_playwright

OUT=pathlib.Path("odds_diagnostic_results/bangbet_deep_probe.json")
SHOT=pathlib.Path("odds_diagnostic_results/bangbet_deep_probe.png")
URL="https://grey.bangbet.com/"

ODD=re.compile(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|[1-9]\d)[.,]\d{2,3}(?!\d)")
EXACT_DC=re.compile(r"^(?:double chance|1x|x2|12)$",re.I)
EXACT_TOTAL=re.compile(r"^(?:over|under|plus de|moins de)\s*(?:1|2|3|4)[.,]5$",re.I)
DANGER=re.compile(r"(?:place bet|bet now|confirm bet|stake|deposit|withdraw|cash out|one.?click|parier|miser|valider)",re.I)
SLIP='[data-testid*="betslip" i],[data-testid*="bet-slip" i],[class*="betslip" i],[class*="bet-slip" i],[class*="coupon" i],[class*="ticket" i]'

async def text(el,limit=180):
    try:return re.sub(r"\s+"," ",(await el.inner_text(timeout=450)).strip())[:limit]
    except:return ""

async def find_real_market_option(page):
    # 1) exact accessible labels first
    for pattern,kind in ((EXACT_TOTAL,"total_goals"),(EXACT_DC,"double_chance")):
        nodes=page.locator("button,[role=button],a,span,div")
        for i in range(min(await nodes.count(),1800)):
            n=nodes.nth(i)
            try:
                if not await n.is_visible(timeout=80):continue
                t=await text(n,100)
                if not pattern.fullmatch(t):continue
                parent=n.locator("xpath=..")
                context=await text(parent,400)
                odds=ODD.findall(context)
                if not odds:continue
                return n,kind,t,odds[0],context
            except:continue
    # 2) inspect market blocks explicitly named Double Chance or Goals/Total, then find leaf odd cells
    market_headers=page.get_by_text(re.compile(r"^(?:Double Chance|Total(?: Goals)?|Goals)$",re.I))
    for i in range(min(await market_headers.count(),30)):
        h=market_headers.nth(i)
        try:
            if not await h.is_visible(timeout=180):continue
            # climb at most four ancestors and inspect small blocks
            cur=h
            for _ in range(4):
                cur=cur.locator("xpath=..")
                ctx=await text(cur,700)
                if len(ctx)>650:continue
                children=cur.locator("button,[role=button]")
                for j in range(min(await children.count(),40)):
                    c=children.nth(j)
                    if not await c.is_visible(timeout=100):continue
                    ct=await text(c,120)
                    if DANGER.search(ct):continue
                    odds=ODD.findall(ct)
                    if odds:
                        kind="double_chance" if re.search(r"Double Chance",ctx,re.I) else "total_goals"
                        return c,kind,ct,odds[0],ctx
        except:continue
    return None,None,None,None,None

async def locate_slip(page):
    loc=page.locator(SLIP)
    for i in range(min(await loc.count(),25)):
        x=loc.nth(i)
        try:
            if not await x.is_visible(timeout=180):continue
            t=await text(x,1600)
            if len(t)>8 and ODD.search(t):return x,t
        except:continue
    return None,None

async def enumerate_actions(page,slip):
    rows=[]
    scopes=[("slip",slip),("page",page)]
    seen=set()
    for scope_name,scope in scopes:
        els=scope.locator('button,[role="button"],a,[aria-label],[title]')
        for i in range(min(await els.count(),240)):
            e=els.nth(i)
            try:
                if not await e.is_visible(timeout=100):continue
                labels=[]
                for v in (await text(e,100),await e.get_attribute("aria-label"),await e.get_attribute("title")):
                    if v and str(v).strip():labels.append(re.sub(r"\s+"," ",str(v).strip())[:100])
                label=" | ".join(dict.fromkeys(labels))
                if not label or label in seen:continue
                seen.add(label)
                if re.search(r"(?:book|save|share|code|ticket|coupon|load|copy|bet)",label,re.I):
                    rows.append({"scope":scope_name,"label":label,"dangerous":bool(DANGER.search(label))})
            except:continue
    return rows[:80]

async def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    report={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"url":URL,
            "http_status":None,"market_kind":None,"selection_text":None,"odd":None,
            "selection_clicked":False,"betslip_verified":False,"betslip_text":None,
            "candidate_actions":[],"status":"not_started"}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(service_workers="block")
        page=await ctx.new_page()
        try:
            r=await page.goto(URL,wait_until="domcontentloaded",timeout=25000)
            report["http_status"]=r.status if r else None
            await page.wait_for_timeout(5500)
            n,kind,label,odd,context=await find_real_market_option(page)
            if n is None:
                report["status"]="no_exact_double_chance_or_total_option"
            else:
                report.update(market_kind=kind,selection_text=label,odd=odd,market_context=context)
                await n.click(timeout=1500)
                report["selection_clicked"]=True
                await page.wait_for_timeout(1400)
                slip,slip_text=await locate_slip(page)
                if slip is None:
                    report["status"]="selection_clicked_betslip_not_verified"
                else:
                    report["betslip_verified"]=True
                    report["betslip_text"]=slip_text[:900]
                    report["candidate_actions"]=await enumerate_actions(page,slip)
                    report["status"]="betslip_verified_actions_enumerated"
            try:await page.screenshot(path=str(SHOT),full_page=False,timeout=4000)
            except:pass
        except Exception as e:
            report["status"]="browser_error";report["error_type"]=type(e).__name__
        await ctx.close();await browser.close()
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=="__main__":asyncio.run(main())
