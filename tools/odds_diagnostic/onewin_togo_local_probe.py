#!/usr/bin/env python3
"""1win Togo local/self-hosted probe.

Run this from a machine/network genuinely located in Togo, or from an explicitly
chosen infrastructure location such as Render Frankfurt for diagnostics.
No proxy/VPN bypass is configured by this script.
No registration, credentials, stake, deposit, or wager submission.
"""
import asyncio, datetime as dt, json, pathlib, re
from urllib.parse import urlsplit, parse_qs
from playwright.async_api import async_playwright

ROOT=pathlib.Path("odds_diagnostic_results")
OUT=ROOT/"onewin_togo_local_probe.json"
URL="https://1win.com/betting/prematch/99"

REGION_BLOCK=re.compile(r"(?:site is not available in your region|not available in your region|restricted in your region|service in your region is restricted|regional restrictions)",re.I)
TARGET=re.compile(r"(?:double chance|\b1x\b|\bx2\b|\b12\b|over\s*2[.,]5|under\s*2[.,]5|total(?: goals?)?)",re.I)
ODD=re.compile(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|[1-9]\d)[.,]\d{2,3}(?!\d)")
SHARE=re.compile(r"(?:share\s*bet|sharebet|booking\s*code|bet\s*code|copy\s*(?:code|link)|share\s*link)",re.I)
DANGER=re.compile(r"(?:place bet|bet now|confirm|stake|deposit|withdraw|cash out)",re.I)

async def txt(el,limit=220):
    try:
        return re.sub(r"\s+"," ",(await el.inner_text(timeout=500)).strip())[:limit]
    except:
        return ""

async def visible_controls(page, regex):
    out=[]
    nodes=page.locator("button,[role=button],a,[aria-label],[title]")
    for i in range(min(await nodes.count(),1600)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=70):
                continue
            vals=[
                await txt(n,100),
                str(await n.get_attribute("aria-label") or "")[:100],
                str(await n.get_attribute("title") or "")[:100],
            ]
            label=" | ".join(dict.fromkeys(v.strip() for v in vals if v and v.strip()))
            if label and regex.search(label) and label not in out:
                out.append(label[:220])
                if len(out)>=80:
                    break
        except:
            continue
    return out

async def click_target(page):
    # Enter the Football section first so esports counters like "LoL 12"
    # cannot be mistaken for the football market "12".
    nav=page.locator("button,[role=button],a")
    for i in range(min(await nav.count(),1200)):
        n=nav.nth(i)
        try:
            if not await n.is_visible(timeout=60):
                continue
            label=(await txt(n,120)).strip()
            if re.fullmatch(r"Football(?:\\s+\\d+)?", label, re.I):
                await n.click(timeout=1200)
                await page.wait_for_timeout(1800)
                break
        except:
            continue

    nodes=page.locator("button,[role=button],a")
    samples=[]
    for i in range(min(await nodes.count(),2200)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=60):
                continue
            label=await txt(n,120)
            parent=await txt(n.locator("xpath=.."),320)
            local=" | ".join([label,parent])
            if DANGER.search(local):
                continue
            odds=ODD.findall(local)
            # Prefer a pure decimal-odd button after entering Football.
            pure_odd = bool(re.fullmatch(r"\\s*\\d{1,2}[.,]\\d{2,3}\\s*", label))
            football_market = bool(TARGET.search(local) or re.search(r"\\b(?:1x2|winner|total|goals?|double chance|handicap)\\b", local, re.I))
            if not odds or not (pure_odd or football_market):
                continue
            samples.append({"label":label,"context":parent[:250],"odds":odds[:4]})
            if not odds:
                continue
            await n.click(timeout=1000)
            await page.wait_for_timeout(1200)
            return {"clicked":True,"label":label,"odd":odds[0],"context":parent[:320]},samples[:50]
        except:
            continue
    return {"clicked":False},samples[:50]

async def share_code(page):
    q=parse_qs(urlsplit(page.url).query)
    for key in ("sharebet","shareBet","shareCode","sharecode","bookingCode","code"):
        vals=q.get(key,[])
        if vals and re.fullmatch(r"[A-Za-z0-9_-]{4,40}",vals[0] or ""):
            return vals[0],"url"
    body=(await page.locator("body").inner_text(timeout=5000))[:40000]
    for line in body.splitlines():
        if SHARE.search(line):
            m=re.search(r"([A-Za-z0-9_-]{5,32})",line)
            if m:
                return m.group(1),"labelled_text"
    return None,None

async def wait_for_sportsbook(page, attempts=8, delay_ms=2500):
    """Wait for the JS sportsbook UI instead of trusting only domcontentloaded."""
    last_body=""
    for attempt in range(1, attempts+1):
        try:
            body=(await page.locator("body").inner_text(timeout=5000))[:50000]
        except:
            body=""
        last_body=body or last_body
        low=body.lower()
        if REGION_BLOCK.search(body):
            return body, attempt
        if "football" in low and (ODD.search(body) or "betting" in low or "prematch" in low):
            return body, attempt
        await page.wait_for_timeout(delay_ms)
        if attempt in (3,6) and not body.strip():
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
            except:
                pass
    return last_body, attempts

async def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    rep={
        "run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"infrastructure_location_probe",
        "url":URL,
        "http_status":None,
        "final_url":None,
        "page_title":None,
        "response_headers":{},
        "body_excerpt":None,
        "region_blocked":False,
        "body_region_excerpt":None,
        "football_visible":False,
        "selection":None,
        "market_samples":[],
        "share_controls":[],
        "share_code":None,
        "share_code_source":None,
        "network_candidates":[],
        "document_state":{},
        "status":"not_started",
        "no_proxy_or_location_spoofing":True,
        "no_login_no_stake_no_wager":True
    }
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(service_workers="block")
        page=await ctx.new_page()
        network_candidates=[]
        async def record_response(resp):
            try:
                rt=resp.request.resource_type
                url=resp.url
                ct=(await resp.all_headers()).get("content-type","")
                if rt not in ("xhr","fetch") and "json" not in ct.lower():
                    return
                low=url.lower()
                if not any(k in low for k in ("bet","sport","event","match","prematch","line","odd","coef")):
                    return
                item={"status":resp.status,"resource_type":rt,"url":url[:500],"content_type":ct[:120]}
                if "json" in ct.lower():
                    try:
                        raw=await resp.text()
                        item["body_excerpt"]=re.sub(r"\\s+"," ",raw)[:900]
                    except:
                        pass
                if len(network_candidates)<80:
                    network_candidates.append(item)
            except:
                pass
        page.on("response", record_response)
        try:
            r=await page.goto(URL,wait_until="domcontentloaded",timeout=30000)
            rep["http_status"]=r.status if r else None
            rep["final_url"]=page.url
            if r:
                h=await r.all_headers()
                for k in ("server","content-type","cf-ray","cf-cache-status","location","x-request-id"):
                    if h.get(k):
                        rep["response_headers"][k]=h.get(k)
            try:
                rep["page_title"]=(await page.title())[:300]
            except:
                pass
            await page.wait_for_timeout(5000)
            try:
                body=(await page.locator("body").inner_text(timeout=6000))[:50000]
            except:
                body=""
            rep["body_excerpt"]=re.sub(r"\s+"," ",body).strip()[:1200] or None
            try:
                rep["document_state"]={
                    "ready_state":await page.evaluate("document.readyState"),
                    "html_length":await page.evaluate("document.documentElement.outerHTML.length"),
                    "body_text_length":await page.evaluate("(document.body && document.body.innerText || '').length"),
                    "script_count":await page.locator("script").count(),
                    "iframe_count":await page.locator("iframe").count(),
                }
            except Exception as exc:
                rep["document_state"]={"error":type(exc).__name__}
            rep["network_candidates"]=network_candidates[:80]
            rep["football_visible"]="football" in body.lower()
            if not rep["football_visible"]:
                try:
                    rep["football_visible"] = bool(await page.get_by_text("Football", exact=False).count())
                except:
                    pass

            m=REGION_BLOCK.search(body)
            if m:
                rep["region_blocked"]=True
                start=max(0,m.start()-180); end=min(len(body),m.end()+260)
                rep["body_region_excerpt"]=re.sub(r"\s+"," ",body[start:end])
                rep["status"]="REGION_BLOCKED_STOPPED"
            elif rep["http_status"] is not None and rep["http_status"] >= 400:
                rep["status"]=f"HTTP_{rep['http_status']}_ACCESS_BLOCKED"
            else:
                rep["share_controls"]=await visible_controls(page,SHARE)
                sel,samples=await click_target(page)
                rep["selection"]=sel
                rep["market_samples"]=samples
                if sel.get("clicked"):
                    await page.wait_for_timeout(1400)
                    rep["share_controls"]=list(dict.fromkeys(rep["share_controls"]+await visible_controls(page,SHARE)))[:100]
                    code,src=await share_code(page)
                    rep["share_code"]=code
                    rep["share_code_source"]=src
                    rep["status"]="SHARE_CODE_EXPOSED" if code else "SELECTION_CLICKED_NO_SHARE_CODE"
                else:
                    rep["status"]="SPORTSBOOK_OPEN_NO_TARGET_SELECTION"
            try:
                await page.screenshot(path=str(ROOT/"onewin_togo_local_probe.png"),full_page=False,timeout=5000)
            except:
                pass
        except Exception as e:
            rep["status"]="browser_error"
            rep["error_type"]=type(e).__name__
            rep["error"]=str(e)[:400]
        await ctx.close()
        await browser.close()
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(rep,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))
