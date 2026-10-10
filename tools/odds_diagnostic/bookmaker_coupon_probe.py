#!/usr/bin/env python3
"""Public pre-match betslip/share-code diagnostic for Mr XPRONOS.

The probe uses anonymous browser contexts, never signs in, never enters a stake,
never deposits, and never clicks a button whose label indicates placing/confirming
a wager. It may click a public market selection and a public Book/Save/Share
control in order to read a bookmaker-generated share/booking code.
"""
import asyncio, datetime as dt, json, pathlib, re
from urllib.parse import urlsplit, parse_qs
from playwright.async_api import async_playwright

ROOT=pathlib.Path("odds_diagnostic_results")
REPORT=ROOT/"bookmaker_coupon_report.json"

SITES=[
 {"name":"1xBet","url":"https://1xbet.com/en/line/football","hosts":["1xbet.com"]},
 {"name":"1win","url":"https://www.1win.global/en/sportsbook/","hosts":["1win.global"]},
 {"name":"Betwinner","url":"https://betwinner.com/en/line/football","hosts":["betwinner.com"]},
 {"name":"Melbet","url":"https://melbet.com/en/line/football","hosts":["melbet.com"]},
 {"name":"Linebet","url":"https://linebet.com/en/line/football","hosts":["linebet.com"]},
 {"name":"BetClic","url":"https://www.betclic.fr/football-s1","hosts":["betclic.fr"]},
 {"name":"SportyBet","url":"https://www.sportybet.com/gh/","hosts":["sportybet.com"]},
 {"name":"Bet9ja","url":"https://web.bet9ja.com/","hosts":["bet9ja.com"]},
 {"name":"BetKing","url":"https://www.betking.com/","hosts":["betking.com"]},
 {"name":"Betika","url":"https://www.betika.com/en-ke/","hosts":["betika.com"]},
 {"name":"MSport","url":"https://www.msport.com/gh/","hosts":["msport.com"]},
 {"name":"MozzartBet","url":"https://www.mozzartbet.com/en/kladjenje/sport/1","hosts":["mozzartbet.com"]},
 {"name":"betPawa","url":"https://www.betpawa.com/","hosts":["betpawa.com"]},
 {"name":"PremierBet","url":"https://www.premierbet.com/","hosts":["premierbet.com"]},
 {"name":"Hollywoodbets","url":"https://www.hollywoodbets.net/","hosts":["hollywoodbets.net"]},
 {"name":"BangBet","url":"https://grey.bangbet.com/","hosts":["bangbet.com"]},
]

BLOCK=re.compile(r"(?:access denied|forbidden|verify you are human|captcha|restricted in your|not available in your country|cloudflare)",re.I)
AUTH=re.compile(r"\b(?:log out|logout|sign out|déconnexion|se déconnecter)\b",re.I)
DANGEROUS=re.compile(r"\b(?:place bet|bet now|confirm bet|quick bet|one.?click bet|parier|miser|placer le pari|confirmer le pari|deposit|déposer|cash out|withdraw)\b",re.I)
MARKET=re.compile(r"(?:double chance|1x\b|x2\b|12\b|over\s*2[.,]5|under\s*2[.,]5|over\s*1[.,]5|under\s*1[.,]5|plus de\s*2[.,]5|moins de\s*2[.,]5|total(?: goals?)?)",re.I)
ODD=re.compile(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|[1-9]\d)[.,]\d{2,3}(?!\d)")
SLIP='[data-testid*="betslip" i],[data-testid*="bet-slip" i],[class*="betslip" i],[class*="bet-slip" i],[class*="coupon" i],[class*="ticket" i]'
BOOK_ACTION=re.compile(r"^(?:book(?: bet| betslip| ticket)?|save(?: bet| betslip| ticket)?|share(?: bet| betslip| ticket| coupon)?|booking(?: code)?|get(?: booking| bet| coupon)? code|reserve(?: ticket)?|reservation code|sharecode)$",re.I)
COPY_ACTION=re.compile(r"^(?:copy(?: code| booking code| coupon code| share code)?|copier(?: le)? code|copy)$",re.I)
CODE_LABEL=re.compile(r"(?:booking|bet(?:slip)?|coupon|ticket|reservation|share)\s*(?:code|number|id)|(?:code|sharecode)\s*[:#-]?",re.I)
PLAIN_CODE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{4,31}$")

def plausible_code(v):
    s=str(v or "").strip().strip("'\"")
    if not PLAIN_CODE.fullmatch(s): return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3})?",s): return None
    if s.lower() in {"xpvip","football","coupon","booking","sharecode","betslip"}: return None
    return s

async def safe_body(page,limit=16000):
    return (await page.locator("body").inner_text(timeout=5000))[:limit]

async def find_slip(page):
    loc=page.locator(SLIP)
    for i in range(min(await loc.count(),20)):
        n=loc.nth(i)
        try:
            if not await n.is_visible(timeout=300): continue
            txt=(await n.inner_text(timeout=700)).strip()
            if 5<len(txt)<1400 and ODD.search(txt):
                return n,txt[:350]
        except Exception: pass
    return None,None

async def click_market(page):
    """Try a harmless pre-match selection. Never click a wager-submit action."""
    nodes=page.locator("button,[role=button],a,div,span")
    for i in range(min(await nodes.count(),1600)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=120): continue
            txt=re.sub(r"\s+"," ",(await n.inner_text(timeout=250)).strip())[:130]
            if not txt or DANGEROUS.search(txt) or not MARKET.search(txt): continue
            parent=(await n.locator("xpath=..").inner_text(timeout=350))[:260]
            odds=ODD.findall(parent)
            if not odds: continue
            await n.click(timeout=900)
            await page.wait_for_timeout(850)
            slip,excerpt=await find_slip(page)
            if slip:
                return {"clicked":True,"selection":txt,"odd":odds[0],"slip_excerpt":excerpt}
        except Exception: continue
    return {"clicked":False,"selection":None,"odd":None,"slip_excerpt":None}

async def read_code_from_scope(scope):
    # readonly inputs first
    inputs=scope.locator('input,textarea')
    for i in range(min(await inputs.count(),25)):
        el=inputs.nth(i)
        try:
            if not await el.is_visible(timeout=200): continue
            meta=" ".join(str(await el.get_attribute(k) or "") for k in ("placeholder","aria-label","name","id"))
            val=await el.input_value(timeout=350)
            if CODE_LABEL.search(meta):
                c=plausible_code(val)
                if c:return c,"field"
        except Exception: pass
    # explicitly labelled text
    txt=(await scope.inner_text(timeout=650))[:2500]
    for line in txt.splitlines():
        if not CODE_LABEL.search(line): continue
        m=re.search(r"([A-Za-z0-9_-]{5,32})\s*$",line.strip())
        if m:
            c=plausible_code(m.group(1))
            if c:return c,"labelled_text"
    return None,None

async def click_named_action(scope,regex):
    els=scope.locator('button,[role=button],a')
    for i in range(min(await els.count(),120)):
        el=els.nth(i)
        try:
            if not await el.is_visible(timeout=220): continue
            label=re.sub(r"\s+"," ",(await el.inner_text(timeout=300)).strip())[:90]
            if not label:
                label=str(await el.get_attribute("aria-label") or await el.get_attribute("title") or "")[:90]
            if DANGEROUS.search(label): continue
            if regex.fullmatch(label):
                await el.click(timeout=1000)
                return label
        except Exception: continue
    return None

async def extract_generated_code(page,slip):
    out={"action_clicked":None,"code":None,"code_source":None}
    c,src=await read_code_from_scope(slip)
    if c:
        out.update(code=c,code_source=src)
        return out
    label=await click_named_action(slip,BOOK_ACTION)
    if not label:
        label=await click_named_action(page,BOOK_ACTION)
    if not label:return out
    out["action_clicked"]=label
    await page.wait_for_timeout(900)
    # inspect slip + dialogs/popovers
    scopes=[slip]
    dialogs=page.locator('[role=dialog],[class*="modal" i],[class*="popover" i],[class*="share" i]')
    for i in range(min(await dialogs.count(),10)):
        scopes.append(dialogs.nth(i))
    for scope in scopes:
        try:
            if hasattr(scope,"is_visible") and not await scope.is_visible(timeout=200): continue
            c,src=await read_code_from_scope(scope)
            if c:
                out.update(code=c,code_source=src)
                return out
            copied=await click_named_action(scope,COPY_ACTION)
            if copied:
                await page.wait_for_timeout(250)
                # Some sites place code in URL after share
                q=parse_qs(urlsplit(page.url).query)
                for key in ("shareCode","sharecode","bookingCode","booking","code"):
                    for val in q.get(key,[]):
                        c=plausible_code(val)
                        if c:
                            out.update(code=c,code_source="url_after_copy")
                            return out
        except Exception: continue
    # URL may change immediately after Book/Share
    q=parse_qs(urlsplit(page.url).query)
    for key in ("shareCode","sharecode","bookingCode","booking","code"):
        for val in q.get(key,[]):
            c=plausible_code(val)
            if c:
                out.update(code=c,code_source="url_after_share")
                return out
    return out

async def test_site(browser,site):
    out={"provider":site["name"],"entry":site["url"],"http_status":None,"final_url":None,
         "status":"not_tested","selection_clicked":False,"coupon_prepared":False,
         "selection":None,"odds":None,"booking_action":None,"coupon_code":None,
         "code_source":None,"notes":[]}
    ctx=await browser.new_context(service_workers="block",accept_downloads=False)
    page=await ctx.new_page()
    try:
        r=await page.goto(site["url"],wait_until="domcontentloaded",timeout=22000)
        out["http_status"]=r.status if r else None
        out["final_url"]=page.url
        if not r or r.status in (203,204,401,403,429) or r.status>=400:
            out["status"]="access_restricted_or_http_error"; return out
        await page.wait_for_timeout(3000)
        body=await safe_body(page)
        if BLOCK.search(body[:2500]):
            out["status"]="blocked_or_challenge"; return out
        if AUTH.search(body[:1800]):
            out["status"]="unexpected_authenticated_session"; return out
        probe=await click_market(page)
        out["selection_clicked"]=probe["clicked"]
        out["selection"]=probe["selection"]
        out["odds"]=probe["odd"]
        if not probe["clicked"]:
            out["status"]="no_clickable_double_chance_or_total"; return out
        slip,_=await find_slip(page)
        if not slip:
            out["status"]="selection_clicked_but_betslip_not_verified"; return out
        out["coupon_prepared"]=True
        generated=await extract_generated_code(page,slip)
        out["booking_action"]=generated["action_clicked"]
        out["coupon_code"]=generated["code"]
        out["code_source"]=generated["code_source"]
        out["status"]="CODE_GENERATED" if generated["code"] else "betslip_ready_no_code_exposed"
        return out
    except Exception as exc:
        out["status"]="browser_error"; out["error_type"]=type(exc).__name__; return out
    finally:
        try:
            ROOT.mkdir(exist_ok=True,parents=True)
            await page.screenshot(path=str(ROOT/(re.sub(r"[^a-z0-9]+","_",site["name"].lower())+"_coupon.png")),timeout=3000)
        except Exception: pass
        await ctx.close()

async def main():
    ROOT.mkdir(exist_ok=True,parents=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        results=[]
        for site in SITES:
            item=await test_site(browser,site)
            results.append(item)
            print(f'{item["provider"]}: {item["status"]} code={item["coupon_code"]}',flush=True)
        await browser.close()
    codes={r["provider"]:r["coupon_code"] for r in results if r["coupon_code"]}
    report={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"anonymous_prematch_booking_code_probe",
            "no_login_no_stake_no_wager_submission":True,
            "providers_count":len(results),
            "generated_code_count":len(codes),
            "generated_codes":codes,
            "results":results}
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
    return 0 if codes else 2

if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))
