#!/usr/bin/env python3
"""Read-only bookmaker feature matrix across 16 sites.

This diagnostic does NOT click odds, create a betting coupon, generate/load a booking code,
log in, enter a stake, place a wager, deposit funds, or bypass CAPTCHAs/geoblocks.
It only records whether public pre-match pages expose relevant markets and booking/share UI.
"""
import asyncio, datetime as dt, json, pathlib, re
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

OUTDIR=pathlib.Path("odds_diagnostic_results")
REPORT=OUTDIR/"bookmaker_feature_matrix.json"

SITES=[
 {"name":"1xBet","url":"https://1xbet.com/en/line/football"},
 {"name":"1win","url":"https://www.1win.global/en/sportsbook/"},
 {"name":"Betwinner","url":"https://betwinner.com/en/line/football"},
 {"name":"Melbet","url":"https://melbet.com/en/line/football"},
 {"name":"Linebet","url":"https://linebet.com/en/line/football"},
 {"name":"BetClic","url":"https://www.betclic.fr/football-s1"},
 {"name":"SportyBet","url":"https://www.sportybet.com/gh/sport/sport/football/today"},
 {"name":"Bet9ja","url":"https://sports.bet9ja.com/?lang=en"},
 {"name":"BetKing","url":"https://m.betking.com/en-ng"},
 {"name":"Betika","url":"https://www.betika.com/fr-cd/"},
 {"name":"MSport","url":"https://www.msport.com/gh/"},
 {"name":"MozzartBet","url":"https://www.mozzartbet.com/en/kladjenje/sport/1?date=today"},
 {"name":"betPawa","url":"https://www.betpawa.com/betPawa"},
 {"name":"PremierBet","url":"https://www.premierbet.com/"},
 {"name":"Hollywoodbets","url":"https://www.hollywoodbets.net/betting/"},
 {"name":"BangBet","url":"https://grey.bangbet.com/"},
]

BLOCK=re.compile(r"(access denied|forbidden|captcha|verify you are human|not available in your|restricted in your|gcore|cloudflare ray id)",re.I)
DOUBLE=re.compile(r"(double chance|1x\b|x2\b|12\b|chance double)",re.I)
TOTAL=re.compile(r"(over\s*/?\s*under|total goals?|goals? total|plus de\s*\d|moins de\s*\d|over\s*\d|under\s*\d|total de buts)",re.I)
BETSLIP=re.compile(r"(bet\s*slip|betslip|coupon|ticket)",re.I)
BOOKING=re.compile(r"(booking code|booking number|book a bet|book bet|book:|sharecode|sharing code|share bet|reservation code|load shared betslip|load betslip|ticket code)",re.I)
LOGIN=re.compile(r"\b(log ?in|sign ?in|connexion)\b",re.I)

async def check(browser,site):
    ctx=await browser.new_context(service_workers="block")
    page=await ctx.new_page()
    row={"provider":site["name"],"entry":site["url"],"http_status":None,"final_url":None,
         "accessible":False,"blocked_or_challenge":False,"body_chars":0,
         "double_chance_visible":False,"total_goals_visible":False,
         "betslip_visible":False,"booking_or_share_ui_visible":False,
         "login_ui_visible":False,"status":"not_tested"}
    try:
        resp=await page.goto(site["url"],wait_until="domcontentloaded",timeout=22000)
        row["http_status"]=resp.status if resp else None
        row["final_url"]=page.url
        if not resp or resp.status>=400 or resp.status in (203,204):
            row["status"]="restricted_or_http_error"
            return row
        await page.wait_for_timeout(3500)
        text=(await page.locator("body").inner_text(timeout=5000))[:50000]
        row["body_chars"]=len(text)
        row["blocked_or_challenge"]=bool(BLOCK.search(text[:4500]))
        if row["blocked_or_challenge"]:
            row["status"]="blocked_or_challenge"
            return row
        row["accessible"]=True
        row["double_chance_visible"]=bool(DOUBLE.search(text))
        row["total_goals_visible"]=bool(TOTAL.search(text))
        row["betslip_visible"]=bool(BETSLIP.search(text))
        row["booking_or_share_ui_visible"]=bool(BOOKING.search(text))
        row["login_ui_visible"]=bool(LOGIN.search(text[:5000]))
        row["status"]="accessible_read_only"
        return row
    except Exception as exc:
        row["status"]="browser_error"
        row["error_type"]=type(exc).__name__
        return row
    finally:
        try:
            OUTDIR.mkdir(parents=True,exist_ok=True)
            await page.screenshot(path=str(OUTDIR/(site["name"].lower().replace(" ","_")+"-feature.png")),full_page=False,timeout=2500)
        except Exception:
            pass
        await ctx.close()

async def main():
    OUTDIR.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        results=[]
        for s in SITES:
            r=await check(browser,s)
            results.append(r)
            print(f'{r["provider"]}: {r["status"]} HTTP={r["http_status"]} bookingUI={r["booking_or_share_ui_visible"]}',flush=True)
        await browser.close()
    summary={
      "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "mode":"read_only_feature_matrix",
      "sites_tested":len(results),
      "accessible":sum(r["accessible"] for r in results),
      "booking_or_share_ui_visible":sum(r["booking_or_share_ui_visible"] for r in results),
      "double_chance_visible":sum(r["double_chance_visible"] for r in results),
      "total_goals_visible":sum(r["total_goals_visible"] for r in results),
      "no_wager_or_code_generation":True,
      "results":results
    }
    REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    asyncio.run(main())
