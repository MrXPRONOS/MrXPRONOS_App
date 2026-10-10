#!/usr/bin/env python3
"""One-shot AiScore delayed corner odds diagnostic. Public pages only; no bypass, no wager."""
import asyncio
import datetime as dt
import json
import os
import pathlib
import re
import unicodedata
from urllib.parse import urlsplit
from aiscore_grid_parser import extract_corner_grid
from aiscore_markup_parser import extract_corner_odds_from_html

OUT = pathlib.Path("odds_diagnostic_results/aiscore_live_report.json")
SEEDS = [
    ("Puebla – Club Leon", "https://www.aiscore.com/match-puebla-club-leon/ndkz6i3yjzxixq3"),
    ("Union Santa Fe – Defensa y Justicia", "https://www.aiscore.com/pt/match-club-atletico-union-defensa-y-justicia/63kv9igw26gsx7e"),
]
LIVE_MINUTE = re.compile(r"(?:^|[^\w])(?:[1-9]\d?|1[01]\d|120)\s*['’′](?:\b|[^a-z])", re.I)
ENDED = re.compile(r"\b(?:full time|finished|match ended|final result)\b", re.I)
NUMBER = re.compile(r"^\s*(\d{1,3}(?:[,.]\d{1,3})?)\s*$")
LINE = re.compile(r"^\d{1,2}[,.]5$")
ODD = re.compile(r"^(?:\d{1,2}[,.]\d{2,3})$")

def normalized(s):
    s=unicodedata.normalize("NFKD",s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))

def valid_quote(line, over, under):
    texts=[str(v).strip().replace(",",".") for v in (line,over,under)]
    if not LINE.fullmatch(texts[0]): return None
    if not all(ODD.fullmatch(n) for n in texts[1:]): return None
    ov,un=float(texts[1]),float(texts[2])
    if not (1.01 <= ov <= 100 and 1.01 <= un <= 100):return None
    return {"total_corners":float(texts[0]),"over":ov,"under":un}

def parse_tables(tables):
    """Accept only triplets in tables with a Corners / Over / Under header."""
    quotes=[]
    for table in tables:
        rows=table.get("rows",[])
        if not rows:continue
        header_candidates=rows[:3]
        has_corner_header=any(any(re.search(r"\bcorners?\b",str(cell),re.I) for cell in row) for row in header_candidates)
        has_over_under=any("over" in " ".join(str(c).lower() for c in row) and "under" in " ".join(str(c).lower() for c in row) for row in header_candidates)
        if not (has_corner_header and has_over_under):continue
        for row in rows[1:]:
            if len(row)<3:continue
            # In AiScore's odds grid, the Corners columns are the last 3 cells.
            q=valid_quote(*row[-3:])
            if q and q not in quotes: quotes.append(q)
    return quotes[:12]

async def tables_from_dom(page):
    return await page.evaluate("""() => Array.from(document.querySelectorAll('table')).slice(0,15).map(t => ({
      rows:Array.from(t.querySelectorAll('tr')).slice(0,45).map(r =>
        Array.from(r.querySelectorAll('td,th')).map(c => (c.innerText||'').trim().slice(0,70)))
    }))""")

async def nodes_from_dom(page):
    return await page.evaluate("""() => {
      const els=Array.from(document.querySelectorAll('body *')).filter(e =>
        e.children.length===0 && e.getClientRects().length && (e.innerText||'').trim().length < 30);
      return els.slice(0,4000).map(e=>{const r=e.getBoundingClientRect(); return {
        text:(e.innerText||'').trim(), x:r.left+r.width/2, y:r.top+r.height/2
      }}).filter(n=>n.x>=0 && n.y>=0);
    }""")

async def discover(page):
    result={"url":"https://www.aiscore.com/","http_status":None,"status":"unknown","candidate_count":0}
    candidates=[]
    try:
        resp=await page.goto(result["url"],wait_until="domcontentloaded",timeout=25000)
        result["http_status"]=resp.status if resp else None
        if not resp or resp.status >=400:
            result["status"]="unavailable"
            return candidates,result
        await page.wait_for_timeout(4500)
        anchors=await page.locator('a[href*="/match-"]').evaluate_all("""els => els.slice(0,350).map(a => ({
          href:a.href, label:(a.innerText||a.getAttribute('title')||'').trim().slice(0,120),
          context:(a.parentElement && a.parentElement.parentElement ?
             a.parentElement.parentElement.innerText : '').trim().slice(0,180)
        }))""")
        for a in anchors:
            parsed=urlsplit(a.get("href",""))
            if not parsed.hostname or not (parsed.hostname=="aiscore.com" or parsed.hostname.endswith(".aiscore.com")):
                continue
            if not LIVE_MINUTE.search(a.get("context","")):continue
            candidates.append({"name":a.get("label") or "Match potentiel live","url":parsed.scheme+"://"+parsed.netloc+parsed.path,"source":"live_listing_with_minute"})
            if len(candidates)>=3:break
        result["status"]="loaded"
        result["candidate_count"]=len(candidates)
    except Exception as e:
        result["status"]="error"
        result["error_type"]=type(e).__name__
    return candidates,result

async def inspect_match(browser,name,url,source):
    result={"match":name[:120],"page_url":url,"discovery_source":source,
            "http_status":None,"page_status":"unknown","match_status":"unverified",
            "odds_tab_clicked":False,"waited_seconds":0,
            "corners_heading_visible":False,"displayed_corner_odds":[],"corner_odds_by_phase":[],
            "verified_live_match":False,"verified_inplay_odds":False,
            "note":"Values are only displayed table quotes; AiScore may show prematch prices during a live match."}
    page=await browser.new_page(viewport={"width":1300,"height":850})
    try:
        resp=await page.goto(url,wait_until="domcontentloaded",timeout=25000)
        result["http_status"]=resp.status if resp else None
        if not resp or resp.status>=400 or resp.status in (203,204):
            result["page_status"]="unavailable_or_restricted"
            return result
        result["page_status"]="loaded"
        await page.wait_for_timeout(1700)
        for label in ("Odds","Cotes"):
            try:
                tab=page.get_by_text(re.compile("^"+label+"$",re.I)).first
                if await tab.count() and await tab.is_visible(timeout=700):
                    await tab.click(timeout=1500)
                    result["odds_tab_clicked"]=True
                    break
            except Exception:pass
        for cycle in range(13):
            await page.wait_for_timeout(2200)
            result["waited_seconds"]+=2.2
            body=(await page.locator("body").inner_text(timeout=5000))[:35000]
            # Only use the upper portion of the match page for match status.
            top=body[:2200]
            if ENDED.search(top):
                result["match_status"]="full_time"
            elif LIVE_MINUTE.search(top) or re.search(r"\b(?:half time|1st half|2nd half)\b",top,re.I):
                result["match_status"]="potentially_live"
            elif result["match_status"]=="unverified":
                result["match_status"]="not_confirmed_live"
            result["corners_heading_visible"]=bool(re.search(r"\bcorners?\b",body,re.I))
            phase_quotes=extract_corner_odds_from_html(await page.content())
            if phase_quotes:
                result["corner_odds_by_phase"]=phase_quotes
            quotes=[{"total_corners":q["total_corners"],"over":q["over"],"under":q["under"]} for q in phase_quotes if q["phase"]=="in_play"]
            if not quotes:
                quotes=parse_tables(await tables_from_dom(page))
            if not quotes:
                quotes=extract_corner_grid(await nodes_from_dom(page))
            if quotes:
                result["displayed_corner_odds"]=quotes
                result["odds_observed_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
                break
        result["verified_live_match"]=source=="live_listing_with_minute" and result["match_status"]=="potentially_live"
        # No claim of an actual in-play market from the static AiScore table.
        result["verified_inplay_odds"]=bool(result["verified_live_match"] and any(q["phase"]=="in_play" for q in result["corner_odds_by_phase"]))
        if result["displayed_corner_odds"]:
            result["page_status"]="displayed_odds_found"
        else:
            result["page_status"]="no_displayed_corners_after_wait"
    except Exception as exc:
        result["page_status"]="browser_error"
        result["error_type"]=type(exc).__name__
    finally:
        await page.close()
    return result

async def main():
    from playwright.async_api import async_playwright
    OUT.parent.mkdir(exist_ok=True,parents=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        listing=await browser.new_page()
        discovered,discovery=await discover(listing)
        await listing.close()
        targets=discovered[:3]
        if not targets:
            targets=[{"name":name,"url":url,"source":"fallback_reference_not_verified_live"} for name,url in SEEDS]
        results=[]
        for match in targets[:3]:
            results.append(await inspect_match(browser,match["name"],match["url"],match["source"]))
        await browser.close()
    report={"tested_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"one_shot_public_browser_delay_28_seconds",
            "listing":discovery,
            "candidate_count":len(results),
            "pages_with_displayed_corner_odds":sum(bool(r["displayed_corner_odds"]) for r in results),
            "live_match_with_displayed_quotes":sum(bool(r["displayed_corner_odds"]) and r["verified_live_match"] for r in results),
            "verified_inplay_corner_market_count":sum(r["verified_inplay_odds"] for r in results),
            "matches":results}
    report["outcome"] = ("SOURCE_RESTRICTED_403" if discovery.get("http_status")==403 and all(r.get("http_status")==403 for r in results) else
                         "PUBLIC_ODDS_OBSERVED_NOT_INPLAY_VERIFIED" if report["pages_with_displayed_corner_odds"] else
                         "NO_PUBLIC_CORNER_ODDS_OBSERVED")
    if report["outcome"]=="SOURCE_RESTRICTED_403":
        print("::warning::AiScore returned HTTP 403 to GitHub runner; no odds were verified. Do not bypass access restrictions.")
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":asyncio.run(main())
