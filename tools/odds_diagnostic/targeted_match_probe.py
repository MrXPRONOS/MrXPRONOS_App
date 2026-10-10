#!/usr/bin/env python3
"""Single public live match quote probe. No login, no bet placement, no anti-bot bypass."""
import asyncio, datetime, json, pathlib, re
from playwright.async_api import async_playwright
from corner_slip_probe import inspect_corner_selection

MATCHES=[
 {"provider":"sportybet","url":"https://www.sportybet.com/ng/lite/live/detail?eventId=sr%3Amatch%3A72335194&fromUrl=%2Fng%2Flite&marketGroupsName=Corners&sportId=sr%3Asport%3A1"},
 {"provider":"1xbet","url":"https://1xbet.com/en/live/football/214147-colombia-categoria-primera-a/760119822-alianza-valledupar-aguilas-doradas"},
]
OUT=pathlib.Path("odds_diagnostic_results/targeted_match_probe.json")
async def run_one(browser,match):
 result={"provider":match["provider"],"match":"Alianza Valledupar - Aguilas Doradas","http_status":None,
         "page_accessible":False,"corner_text_present":False,"corner_total_text_present":False,
         "quotes":[],"selection_test":{"stage":"not_attempted"}}
 page=await browser.new_page()
 try:
  resp=await page.goto(match["url"],wait_until="domcontentloaded",timeout=23000)
  result["http_status"]=resp.status if resp else None
  if not resp or resp.status>=400:
   result["status"]="blocked_or_http_error"
   return result
  result["page_accessible"]=True
  await page.wait_for_timeout(3500)
  body=(await page.locator("body").inner_text(timeout=6000))[:70000]
  result["corner_text_present"]=bool(re.search(r"corner",body,re.I))
  result["corner_total_text_present"]=bool(re.search(r"(corners?[^\\n]{0,60}(over|under)|corners?\\s*[-:]?\\s*over/under)",body,re.I))
  # The market title and the next two choices must be adjacent. Never treat goal totals as corner totals.
  lines=[x.strip() for x in body.splitlines() if x.strip()]
  for idx,line in enumerate(lines):
   if re.search(r"corners?\\s*[-:]\\s*over/under|total\\s+corners|corners?\\s+over/under",line,re.I):
    window=lines[idx+1:idx+6]
    offers=[x for x in window if re.search(r"^(over|under|plus de|moins de)\\s+\\d+(?:[,.]\\d+)?\\s+\\d+[.,]\\d{2,3}$",x,re.I)]
    if offers:result["quotes"].append({"market":line[:80],"offers":offers[:2]})
    if len(result["quotes"])>=5:break
  # A quote in the visible market is enough: clicking isn't needed.
  result["status"]="corner_quote_visible" if result["quotes"] else "no_corner_quote_found"
 except Exception as exc:
  result["status"]="navigation_exception";result["error_type"]=type(exc).__name__
 finally:
  await page.close()
 return result
async def main():
 OUT.parent.mkdir(exist_ok=True,parents=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  results=[]
  for match in MATCHES:
   results.append(await run_one(browser,match))
  await browser.close()
 report={"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"live_status_independently_verified":False,"actual_corner_odds_verified":any(x["quotes"] for x in results),"results":results}
 OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__": asyncio.run(main())
