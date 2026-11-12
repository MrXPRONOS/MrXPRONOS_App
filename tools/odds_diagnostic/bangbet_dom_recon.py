#!/usr/bin/env python3
import asyncio,json,re,datetime as dt,pathlib
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

OUT=pathlib.Path("odds_diagnostic_results/bangbet_dom_recon.json")
URL="https://grey.bangbet.com/"
TERMS=re.compile(r"(double chance|over|under|total|goals?|1x2|booking|share|coupon|ticket|code)",re.I)

async def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    report={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"entry":URL}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(service_workers="block")
        page=await ctx.new_page()
        try:
            r=await page.goto(URL,wait_until="domcontentloaded",timeout=25000)
            report["http_status"]=r.status if r else None
            await page.wait_for_timeout(5000)
            report["title"]=await page.title()
            report["final_url"]=page.url
            report["frames"]=[{"url":f.url,"name":f.name} for f in page.frames]
            report["links"]=await page.locator("a[href]").evaluate_all("""els => els.slice(0,500).map(a=>({
              text:(a.innerText||'').trim().replace(/\\s+/g,' ').slice(0,140),
              href:a.href,
              visible:!!a.getClientRects().length
            })).filter(x=>x.visible && x.text)""")
            report["buttons"]=await page.locator("button,[role=button]").evaluate_all("""els => els.slice(0,700).map(e=>({
              text:(e.innerText||e.getAttribute('aria-label')||e.getAttribute('title')||'').trim().replace(/\\s+/g,' ').slice(0,140),
              tag:e.tagName,
              cls:(e.className||'').toString().slice(0,180),
              visible:!!e.getClientRects().length
            })).filter(x=>x.visible && x.text)""")
            all_text=(await page.locator("body").inner_text(timeout=5000))
            lines=[re.sub(r"\\s+"," ",x).strip() for x in all_text.splitlines()]
            report["term_lines"]=[x[:300] for x in lines if x and TERMS.search(x)][:160]
            # Candidate event links: same host, visible, not nav/login/help.
            host=urlsplit(page.url).hostname or ""
            candidates=[]
            for x in report["links"]:
                h=urlsplit(x["href"]).hostname or ""
                if h!=host and not h.endswith("."+host):continue
                t=x["text"]
                if re.search(r"(login|register|help|promo|bonus|casino|jackpot|virtual|home|live now)",t,re.I):continue
                path=urlsplit(x["href"]).path.lower()
                if re.search(r"(event|match|fixture|prematch|sport|football)",path) or re.search(r"\\bvs\\b|\\bv\\b",t,re.I):
                    candidates.append(x)
            report["candidate_event_links"]=candidates[:80]
        except Exception as e:
            report["error_type"]=type(e).__name__
            report["error"]=str(e)[:300]
        await ctx.close();await browser.close()
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":asyncio.run(main())
