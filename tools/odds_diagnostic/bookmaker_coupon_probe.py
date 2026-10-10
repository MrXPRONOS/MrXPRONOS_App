#!/usr/bin/env python3
"""Anonymous bookmaker coupon probe: prepare a bet slip, never place a wager.

Uses a brand-new empty browser context for each bookmaker. No cookies, account,
deposit, stake, 'place bet', API credentials, CAPTCHA or access-control bypass.
A successful process run DOES NOT imply successful coupon creation: see JSON.
"""
import asyncio
import datetime as dt
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

ROOT = pathlib.Path("odds_diagnostic_results")
REPORT = ROOT / "bookmaker_coupon_report.json"
SITES = [
    {"name": "1xBet", "url": "https://1xbet.com/en/live/football", "host": "1xbet.com"},
    {"name": "1win", "url": "https://www.1win.global/en/sportsbook/", "host": "1win.global"},
    {"name": "Betwinner", "url": "https://betwinner.com/en/live/football", "host": "betwinner.com"},
    {"name": "Melbet", "url": "https://melbet.com/en/live/football", "host": "melbet.com"},
    {"name": "Linebet", "url": "https://linebet.com/en/live/football", "host": "linebet.com"},
    {"name": "BetClic", "url": "https://www.betclic.fr/football-s1", "host": "betclic.fr"},
]
CORNER = re.compile(r"\b(?:corners?|corner kicks?|corners totaux|total de corners)\b", re.I)
CHOICE = re.compile(r"\b(?:over|under|plus de|moins de)\s*(?:\(?\s*)?\d{1,2}[.,]5\b", re.I)
ODD = re.compile(r"(?<!\d)(?:[1-9]|[1-9]\d)[.,]\d{2,3}(?!\d)")
STOP_WORDS = re.compile(r"\b(?:place bet|bet now|confirm bet|one.click bet|quick bet|parier maintenant|mise rapide|placer un pari|confirmer le pari)\b", re.I)
BLOCK = re.compile(r"(?:access denied|forbidden|restricted in your|not available in your|captcha|verify you are human)", re.I)
SLIP_SELECTOR = '[data-testid*="betslip" i], [data-testid*="bet-slip" i], [class*="betslip" i], [class*="bet-slip" i], [class*="betSlip"], [class*="coupon" i]'
MATCH_URL = re.compile(r"/(?:live|line|prematch|sports?)/football/[^/?#]+/[^/?#]+", re.I)

def allowed_match_url(url, host):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname:
        return False
    if p.hostname != host and not p.hostname.endswith("." + host):
        return False
    return bool(MATCH_URL.search(p.path))

def visible_odds(text):
    return ODD.findall(text or "")[:4]

async def betslip_status(page, choice):
    """Confirm on a specific betslip panel, not just the price somewhere on a page."""
    matching = page.locator(SLIP_SELECTOR)
    for i in range(min(await matching.count(), 18)):
        item = matching.nth(i)
        try:
            if not await item.is_visible(timeout=350):
                continue
            txt=(await item.inner_text(timeout=850)).strip()[:1100]
            if len(txt)>750:
                continue
            if CHOICE.search(txt) and visible_odds(txt):
                return True, txt[:240]
        except Exception:
            continue
    return False, None

async def pick_match(page, hostname):
    links = await page.locator('a[href]').evaluate_all("""els => els.slice(0,650).map(el=>({
      url:el.href, text:(el.innerText||'').trim().slice(0,150),
      visible:!!(el.getClientRects().length)
    }))""")
    candidates = [x for x in links if x["visible"] and allowed_match_url(x["url"], hostname)]
    unique=[]
    for x in candidates:
        if x["url"] not in [t["url"] for t in unique]:
            unique.append(x)
    return unique

async def click_corner_option(page):
    out={"corner_label_seen":False,"corner_market_opened":False,
         "selection_text":None,"price_seen":None,"selection_clicked":False,
         "betslip_confirmed":False,"betslip_excerpt":None}
    headings=page.get_by_text(CORNER)
    for i in range(min(await headings.count(), 24)):
        try:
            h=headings.nth(i)
            if not await h.is_visible(timeout=500):
                continue
            out["corner_label_seen"]=True
            # Opening a category is not placing a bet.
            await h.click(timeout=1600)
            out["corner_market_opened"]=True
            await page.wait_for_timeout(1200)
            break
        except Exception:
            continue
    if not out["corner_label_seen"]:
        return out
    option_nodes=page.get_by_text(CHOICE)
    for i in range(min(await option_nodes.count(), 25)):
        try:
            o=option_nodes.nth(i)
            if not await o.is_visible(timeout=450):
                continue
            label=(await o.inner_text(timeout=700)).strip()[:95]
            if not CHOICE.search(label) or STOP_WORDS.search(label):
                continue
            ancestor=(await o.locator("xpath=..").inner_text(timeout=700)).strip()[:250]
            odds=visible_odds(ancestor)
            if not odds:
                continue
            # Zero stored credentials/cookies and only a selection click.
            out["selection_text"]=label
            out["price_seen"]=odds[0]
            await o.click(timeout=1400)
            out["selection_clicked"]=True
            await page.wait_for_timeout(1500)
            confirmed, excerpt=await betslip_status(page, label)
            out["betslip_confirmed"]=confirmed
            out["betslip_excerpt"]=excerpt
            break
        except Exception:
            continue
    return out

async def test_site(browser, site):
    out={"provider":site["name"],"entry":site["url"],"http_status":None,
        "final_host":None,"status":"not_tested","market_found":False,
        "event_url":None,"match_links_found":0,"coupon_prepared":False,
        "clicked_selection":False,"odds":None,"notes":[]}
    ctx=await browser.new_context(accept_downloads=False, service_workers="block")
    page=await ctx.new_page()
    # Forbid external navigation to payment/registration domains only by choosing known public entry URLs;
    # no authentication is attempted and no credentials are supplied.
    try:
        response=await page.goto(site["url"],wait_until="domcontentloaded",timeout=21000)
        out["http_status"]=response.status if response else None
        out["final_host"]=urlsplit(page.url).hostname
        if not response or response.status in (203,204,401,403,429) or response.status>=400:
            out["status"]="access_restricted_or_http_error"
            return out
        await page.wait_for_timeout(3500)
        body=(await page.locator("body").inner_text(timeout=4500))[:15000]
        if BLOCK.search(body[:1800]):
            out["status"]="blocked_or_challenge"
            return out
        if re.search(r"\b(?:log out|sign out|se déconnecter)\b",body[:1600],re.I):
            out["status"]="unexpected_authenticated_session"
            return out
        if re.search(r"one.click bet\s*(?:on|enabled)|pari en un clic activé",body[:1800],re.I):
            out["status"]="one_click_betting_enabled_unsafe"
            return out
        candidates=await pick_match(page,site["host"])
        out["match_links_found"]=len(candidates)
        if not candidates:
            out["status"]="no_public_football_event_link"
            out["notes"].append("Accessible landing page is not evidence of an available bet.")
            return out
        target=candidates[0]
        out["event_url"]=target["url"]
        resp=await page.goto(target["url"],wait_until="domcontentloaded",timeout=19000)
        if not resp or resp.status>=400:
            out["status"]="event_page_unavailable"
            return out
        await page.wait_for_timeout(3000)
        b=(await page.locator("body").inner_text(timeout=5000))[:14000]
        if BLOCK.search(b[:1500]):
            out["status"]="event_page_restricted"
            return out
        if re.search(r"one.click bet\s*(?:on|enabled)|pari en un clic activé",b[:1500],re.I):
            out["status"]="one_click_betting_enabled_unsafe"
            return out
        probe=await click_corner_option(page)
        out["market_found"]=probe["corner_label_seen"]
        out["clicked_selection"]=probe["selection_clicked"]
        out["odds"]=probe["price_seen"]
        out["selection"]=probe["selection_text"]
        out["coupon_prepared"]=probe["betslip_confirmed"]
        out["bet_slip_excerpt"]=probe["betslip_excerpt"]
        out["status"]=("confirmed_coupon_prepared_no_wager" if probe["betslip_confirmed"] else
                       "selection_clicked_but_coupon_not_verified" if probe["selection_clicked"] else
                       "corner_market_no_clickable_total" if probe["corner_label_seen"] else
                       "no_corner_market_found")
        if not out["coupon_prepared"]:
            out["notes"].append("No coupon claim without visible selection inside an identified slip container.")
        return out
    except Exception as exc:
        out["status"]="browser_error"
        out["error_type"]=type(exc).__name__
        return out
    finally:
        try:
            ROOT.mkdir(exist_ok=True,parents=True)
            await page.screenshot(path=str(ROOT / (site["name"].lower()+ "_coupon_probe.png")), timeout=3000)
        except Exception:
            pass
        await ctx.close()

async def main():
    ROOT.mkdir(exist_ok=True,parents=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        result=[]
        for site in SITES:
            item=await test_site(browser,site)
            result.append(item)
            print(f'{item["provider"]}: {item["status"]} (HTTP {item["http_status"]})',flush=True)
        await browser.close()
    confirmed=[r for r in result if r["coupon_prepared"]]
    output={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"anonymous_public_betslip_only",
            "no_account_or_bet_placement":True,
            "providers_count":len(result),
            "coupons_verified":len(confirmed),
            "conclusion":"COUPON_CONFIRMED" if confirmed else "NO_COUPON_CONFIRMED",
            "results":result}
    REPORT.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(output,indent=2,ensure_ascii=False),flush=True)
    # Exit nonzero when user-facing goal isn't met so Actions isn't misleadingly green.
    return 0 if confirmed else 2

if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))
