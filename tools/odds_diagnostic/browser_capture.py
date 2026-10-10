#!/usr/bin/env python3
"""Observation ponctuelle de pages publiques dans Chromium, sans login ni contournement.
N'enregistre ni HAR, ni cookies, ni URL contenant des paramètres sensibles.
"""
import asyncio, datetime, json, pathlib, re
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
from har_audit import provider_for
from validation import validate

TARGETS=[("sportybet","https://www.sportybet.com/ng/"),("1xbet","https://1xbet.com/en")]
OUT=pathlib.Path("odds_diagnostic_results/browser_capture.json")
async def visit(browser, provider, url):
    page=await browser.new_page()
    result={"provider":provider,"site":urlsplit(url).hostname,"status":"not_started","responses_observed":0,
            "json_responses":0,"markets":{"corners":0,"shots":0,"fouls":0},
            "unmapped_numeric_markets":0,"status_codes":{},"limitations":[]}
    tasks=[]
    async def observe(response):
        try:
            if provider_for(response.url)!=provider:return
            result["responses_observed"]+=1
            status=str(response.status)
            result["status_codes"][status]=result["status_codes"].get(status,0)+1
            typ=response.headers.get("content-type","").lower()
            if "json" not in typ or result["json_responses"]>=50:return
            body=await response.body()
            if len(body)>1_000_000:return
            obj=json.loads(body)
            result["json_responses"]+=1
            v=validate(obj,provider)
            if v["analysis"]:
                for kind,n in v["analysis"]["counts"].items():result["markets"][kind]+=n
                result["unmapped_numeric_markets"]+=v["analysis"]["unmapped_numeric_markets"]
        except Exception:
            result["limitations"].append("a_json_response_could_not_be_analyzed")
    page.on("response",lambda response:tasks.append(asyncio.create_task(observe(response))))
    try:
        resp=await page.goto(url,wait_until="domcontentloaded",timeout=25000)
        result["status"]="page_loaded" if resp else "navigation_without_response"
        await page.wait_for_timeout(9000)
        await asyncio.gather(*tasks,return_exceptions=True)
    except Exception as exc:
        result["status"]="navigation_failed"
        result["error_type"]=type(exc).__name__
    finally:
        await page.close()
    result["verified_bookmaker_live_odds"]=False
    result["limitations"].append("Aucun clic de marché ni authentification; absence de cote ne prouve pas absence du marché.")
    return result
async def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        results=[]
        for name,url in TARGETS:
            results.append(await visit(browser,name,url))
        await browser.close()
    report={"generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
       "method":"public_browser_observation_once_no_login_no_bypass",
       "results":results}
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":asyncio.run(main())
