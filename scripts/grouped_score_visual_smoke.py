#!/usr/bin/env python3
"""Browser-only proof that grouped-score preview is responsive and honest.

Uses synthetic, intercepted preview data — never a real bookmaker quotation.
Screenshots are private GitHub Action artifacts, not published site content.
"""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

SIZES=(1440,1024,768,390,320)
FIXTURE={
    "format":"mrx-1xbet-grouped-preview-v1","published":False,
    "experimental":True,
    "matches":[{
      "id":"synthetic-browser-test",
      "home_team":"Équipe A","away_team":"Équipe B",
      "league":"Test League","kickoff_utc":"2030-12-11T17:00:00+00:00",
      "status":"pending","direction":"home",
      "h2h_priority":True,"under25_priority":True,
      "groups":[
        {"group_id":"G4","scores":[[1,0],[2,0],[3,0]],
         "probability":.315,"direction_eligible":True,
         "quote_documented":False,"odds":None},
        {"group_id":"G1","scores":[[0,0],[1,0],[0,1]],
         "probability":.27,"direction_eligible":True,
         "quote_documented":False,"odds":None},
        {"group_id":"G2","scores":[[0,1],[0,2],[0,3]],
         "probability":.135,"direction_eligible":False,
         "quote_documented":False,"odds":None},
        {"group_id":"G3","scores":[[0,4],[0,5],[0,6]],
         "probability":.005,"direction_eligible":False,
         "quote_documented":False,"odds":None},
      ]
    },{
      "id":"synthetic-finished",
      "home_team":"Équipe C","away_team":"Équipe D",
      "kickoff_utc":"2026-01-02T17:00:00+00:00",
      "status":"settled","direction":"away",
      "h2h_priority":False,"under25_priority":False,
      "groups":[{"group_id":"G2","scores":[[0,1],[0,2],[0,3]],
                 "probability":.21,"direction_eligible":True,
                 "quote_documented":True,"odds":2.8,"hit":1}]
    }]
}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--url",default="http://127.0.0.1:8000/scores-groupes.html")
    p.add_argument("--out",default="artifacts/grouped-score-responsive")
    args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    failures=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        for width in SIZES:
            page=browser.new_page(viewport={"width":width,"height":840})
            errors=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.route("**/scores-groupes-preview.json*",
                       lambda route:route.fulfill(status=200,content_type="application/json",
                                                  body=json.dumps(FIXTURE)))
            try:
                page.goto(args.url,wait_until="domcontentloaded",timeout=30000)
                page.locator(".match").first.wait_for(timeout=12000)
                n=page.locator(".match").count()
                if n!=1:failures.append(f"{width}px: expected 1 upcoming card, got {n}")
                if "Cote 1xBet" not in page.locator("#matches").inner_text():
                    failures.append(f"{width}px: unverified quotes disclaimer missing")
                if "2.80" in page.locator("#matches").inner_text():
                    failures.append(f"{width}px: historical quote leaked to upcoming view")
                if page.evaluate("() => document.documentElement.scrollWidth > innerWidth+2"):
                    failures.append(f"{width}px: horizontal overflow")
                if page.locator(".expand").count()==1:
                    page.locator(".expand").click()
                    if page.locator(".match .group").count()!=4:
                        failures.append(f"{width}px: expand control does not show 4 score groups")
                if width==390:
                    page.locator("#camp").select_option("away")
                    if page.locator(".match").count()!=0:
                        failures.append("away direction unexpectedly includes home fixture")
                    page.locator("#camp").select_option("home")
                    if page.locator(".match").count()!=1:
                        failures.append("home direction filtered out home fixture")
                    page.locator("[data-status='history']").click()
                    page.locator("#camp").select_option("all")
                    if page.locator(".match").count()!=1:
                        failures.append("history tab failed")
                    if "2.80" not in page.locator("#matches").inner_text():
                        failures.append("documented historical quote not visible")
                if errors:failures.append(f"{width}px: JS errors {errors[:2]}")
                page.screenshot(path=str(out/f"grouped-{width}.png"),full_page=True)
            except Exception as err:
                failures.append(f"{width}px: {type(err).__name__}: {err}")
            finally:
                page.close()
        browser.close()
    if failures:
        print("FAILURES:",*failures,sep="\n - ")
        raise SystemExit(1)
    print("PASS grouped-score: 5 viewports, no overflow, DC filters, history and documented quote labels")

if __name__=="__main__":
    main()
