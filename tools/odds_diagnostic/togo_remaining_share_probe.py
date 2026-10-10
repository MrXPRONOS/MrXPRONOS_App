#!/usr/bin/env python3
"""Grouped anonymous share/booking-code capability probe for Togo candidates.
No registration, no credentials, no stake, no wager submission.
"""
import asyncio, datetime as dt, json, pathlib, re
from urllib.parse import urlsplit, parse_qs
from playwright.async_api import async_playwright

ROOT=pathlib.Path("odds_diagnostic_results")
OUT=ROOT/"togo_remaining_share_probe.json"

SITES=[
 {"name":"MegaPari","urls":["https://megapari.com/en/line/football","https://megapari.com/en"]},
 {"name":"BetAndYou","urls":["https://betandyou.com/en/line/football","https://betandyou.com/en"]},
 {"name":"WinWin","urls":["https://winwin.bet/en/line/football","https://winwin.bet/en"]},
 {"name":"SpinBetter","urls":["https://spinbetter.com/en/line/football","https://spinbetter.com/en"]},
 {"name":"FANSPORT","urls":["https://fan-sport.com/en/line/football","https://fan-sport.com/en"]},
]

BLOCK=re.compile(r"(?:not available in your region|access denied|forbidden|captcha|verify you are human|/block\b|cloudflare)",re.I)
FOOT=re.compile(r"\bfootball\b",re.I)
TARGET=re.compile(r"(?:double chance|\b1x\b|\bx2\b|\b12\b|over\s*[1234][.,]5|under\s*[1234][.,]5|total(?: goals?)?)",re.I)
ODD=re.compile(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|[1-9]\d)[.,]\d{2,3}(?!\d)")
SHARE=re.compile(r"(?:book(?:ing)?\s*(?:code|bet|ticket|betslip)?|save\s*(?:bet|ticket|betslip)?|share\s*(?:bet|ticket|betslip|coupon)?|reservation\s*code|sharecode|load\s*(?:code|betslip)|copy\s*(?:code|link)?)",re.I)
DANGER=re.compile(r"(?:place bet|bet now|confirm|stake|deposit|withdraw|cash out|one.?click)",re.I)

async def txt(el,limit=250):
    try:return re.sub(r"\s+"," ",(await el.inner_text(timeout=450)).strip())[:limit]
    except:return ""

async def inspect_controls(page, regex, maxn=80):
    out=[]
    loc=page.locator("button,[role=button],a,[aria-label],[title],input[type=button],input[type=submit]")
    for i in range(min(await loc.count(),1600)):
        n=loc.nth(i)
        try:
            if not await n.is_visible(timeout=60): continue
            vals=[
                await txt(n,100),
                str(await n.get_attribute("aria-label") or "")[:100],
                str(await n.get_attribute("title") or "")[:100],
                str(await n.get_attribute("value") or "")[:100],
            ]
            label=" | ".join(dict.fromkeys(x.strip() for x in vals if x and x.strip()))
            if label and regex.search(label) and label not in out:
                out.append(label[:220])
                if len(out)>=maxn: break
        except: continue
    return out

async def try_selection(page):
    nodes=page.locator("button,[role=button],a,div,span")
    samples=[]
    for i in range(min(await nodes.count(),2200)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=50): continue
            label=await txt(n,120)
            if not label or DANGER.search(label) or not TARGET.search(label): continue
            parent=await txt(n.locator("xpath=.."),320)
            odds=ODD.findall(parent)
            samples.append({"label":label,"context":parent[:260],"odds":odds[:4]})
            if not odds: continue
            await n.click(timeout=900)
            await page.wait_for_timeout(1000)
            return {"clicked":True,"label":label,"odd":odds[0],"context":parent[:320]},samples[:40]
        except: continue
    return {"clicked":False},samples[:40]

async def code_from_url_or_text(page):
    q=parse_qs(urlsplit(page.url).query)
    for key in ("shareCode","sharecode","sharebet","bookingCode","booking","code"):
        vals=q.get(key,[])
        if vals and re.fullmatch(r"[A-Za-z0-9_-]{4,40}",vals[0] or ""):
            return vals[0],"url"
    body=(await page.locator("body").inner_text(timeout=5000))[:30000]
    for line in body.splitlines():
        if SHARE.search(line):
            m=re.search(r"([A-Za-z0-9_-]{5,32})",line)
            if m and not re.fullmatch(r"(booking|sharecode|reservation|betslip|coupon)",m.group(1),re.I):
                return m.group(1),"labelled_text"
    return None,None

async def test_site(browser,site):
    res={"provider":site["name"],"attempts":[],"usable_url":None,"http_status":None,
         "football_visible":False,"blocked":False,"share_feature_visible":False,
         "share_controls":[],"selection":None,"market_samples":[],
         "share_code":None,"share_code_source":None,"status":"not_tested"}
    ctx=await browser.new_context(service_workers="block")
    page=await ctx.new_page()
    try:
        for u in site["urls"]:
            try:
                r=await page.goto(u,wait_until="domcontentloaded",timeout=22000)
                await page.wait_for_timeout(5000)
                body=(await page.locator("body").inner_text(timeout=5000))[:30000]
                att={"url":u,"http":r.status if r else None,"final_url":page.url,
                     "excerpt":re.sub(r"\s+"," ",body)[:1000]}
                res["attempts"].append(att)
                if BLOCK.search(page.url+" "+body[:3000]) or (r and r.status in (203,401,403,429)):
                    continue
                if r and r.status<400:
                    res["usable_url"]=page.url;res["http_status"]=r.status
                    res["football_visible"]=bool(FOOT.search(body) or "line/football" in u)
                    share_controls=await inspect_controls(page,SHARE)
                    res["share_controls"]=share_controls
                    res["share_feature_visible"]=bool(share_controls or SHARE.search(body))
                    break
            except Exception as e:
                res["attempts"].append({"url":u,"error_type":type(e).__name__})
        if not res["usable_url"]:
            res["blocked"]=True
            res["status"]="NO_USABLE_PUBLIC_PAGE"
            return res
        sel,samples=await try_selection(page)
        res["selection"]=sel;res["market_samples"]=samples
        if sel.get("clicked"):
            await page.wait_for_timeout(900)
            share_controls=await inspect_controls(page,SHARE)
            res["share_controls"]=list(dict.fromkeys(res["share_controls"]+share_controls))[:80]
            res["share_feature_visible"]=bool(res["share_controls"])
            code,src=await code_from_url_or_text(page)
            res["share_code"]=code;res["share_code_source"]=src
            res["status"]="SHARE_CODE_EXPOSED" if code else "SELECTION_CLICKED_NO_CODE"
        else:
            res["status"]="PAGE_OPEN_NO_TARGET_SELECTION"
        return res
    except Exception as e:
        res["status"]="browser_error";res["error_type"]=type(e).__name__;return res
    finally:
        try:
            ROOT.mkdir(parents=True,exist_ok=True)
            name=re.sub(r"[^a-z0-9]+","_",site["name"].lower())
            await page.screenshot(path=str(ROOT/(name+"_remaining_share_probe.png")),timeout=3000)
        except: pass
        await ctx.close()

async def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        results=[]
        for site in SITES:
            x=await test_site(browser,site)
            results.append(x)
            print(f'{x["provider"]}: {x["status"]} code={x["share_code"]}',flush=True)
        await browser.close()
    rep={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
         "mode":"anonymous_togo_candidates_share_probe",
         "no_registration_no_stake_no_wager":True,
         "providers_count":len(results),
         "usable_count":sum(bool(x["usable_url"]) for x in results),
         "selection_clicked_count":sum(bool((x["selection"] or {}).get("clicked")) for x in results),
         "code_count":sum(bool(x["share_code"]) for x in results),
         "results":results}
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(rep,indent=2,ensure_ascii=False),flush=True)

if __name__=="__main__":asyncio.run(main())
