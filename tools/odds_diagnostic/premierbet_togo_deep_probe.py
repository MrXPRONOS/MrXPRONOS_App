#!/usr/bin/env python3
import asyncio,datetime as dt,json,pathlib,re
from playwright.async_api import async_playwright

ROOT=pathlib.Path("odds_diagnostic_results")
OUT=ROOT/"premierbet_togo_deep_probe.json"
MATCH="https://sports2.premierbet.com/en/mini/Fixture/Match/7474403"
BETSLIP="https://sports2.premierbet.com/en/mini/BetSlip"

TARGETS=[
    ("total_goals_over_2_5", re.compile(r"\bOver\s*\(?\s*2[.,]5\s*\)?\b",re.I)),
    ("double_chance_x2", re.compile(r"\bX2\b",re.I)),
]
CODEISH=re.compile(r"(?:book|booking|reserve|reservation|share|save|code|coupon|ticket|load)",re.I)
DANGER=re.compile(r"(?:place bet|bet now|confirm|stake|deposit|withdraw|cash out|one.?click|parier|miser|valider)",re.I)

async def norm_text(el,limit=400):
    try:return re.sub(r"\s+"," ",(await el.inner_text(timeout=700)).strip())[:limit]
    except:return ""

async def click_exact_market(page):
    # Build a DOM map of every clickable odd. We only click when the target
    # market label is in the link's *small local container*, not in a huge
    # ancestor containing unrelated markets.
    rows = await page.locator("a[href*='BetSlip/SelectMatchOdd']").evaluate_all("""els => els.map((a,idx) => {
      const clean = s => (s||'').replace(/\\s+/g,' ').trim();
      let p=a;
      const scopes=[];
      for(let k=0;k<3 && p;k++,p=p.parentElement){
        scopes.push(clean(p.innerText).slice(0,260));
      }
      const prev=clean(a.previousElementSibling && a.previousElementSibling.innerText).slice(0,120);
      const next=clean(a.nextElementSibling && a.nextElementSibling.innerText).slice(0,120);
      return {idx, text:clean(a.innerText).slice(0,100), href:a.getAttribute('href'),
              parent:scopes[1]||'', grandparent:scopes[2]||'', prev, next};
    })""")
    page._mrx_candidates=rows[:140]

    # Prefer containers that explicitly bind the target label and the link odd.
    for target_name, pat in TARGETS:
        for row in rows:
            local=" | ".join([row.get("prev",""),row.get("text",""),row.get("next",""),row.get("parent","")])
            if len(local)>520:
                local=" | ".join([row.get("prev",""),row.get("text",""),row.get("next","")])
            if not pat.search(local):
                continue
            href=row.get("href") or ""
            oddm=re.search(r"[?&]Odd=([^&]+)",href)
            odd=oddm.group(1) if oddm else None
            # Click the exact mapped anchor by href.
            a=page.locator("a[href="+json.dumps(href)+"]").first
            try:
                if await a.is_visible(timeout=300):
                    await a.click(timeout=1600)
                    await page.wait_for_timeout(1500)
                    return {"target":target_name,"label":local[:500],"odd":odd,"href":href,
                            "after_click_url":page.url,"mapping":"local_dom"}
            except Exception:
                continue
    return None

async def collect_actions(page):
    out=[]
    nodes=page.locator("button,[role='button'],a,input[type='button'],input[type='submit'],[aria-label],[title]")
    for i in range(min(await nodes.count(),600)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=80):continue
            vals=[
                await norm_text(n,120),
                str(await n.get_attribute("value") or "")[:120],
                str(await n.get_attribute("aria-label") or "")[:120],
                str(await n.get_attribute("title") or "")[:120],
            ]
            label=" | ".join(dict.fromkeys(x.strip() for x in vals if x and x.strip()))
            if label and CODEISH.search(label) and label not in [x["label"] for x in out]:
                out.append({"label":label,"dangerous":bool(DANGER.search(label))})
        except:continue
    return out[:80]

async def collect_fields(page):
    out=[]
    nodes=page.locator("input,textarea")
    for i in range(min(await nodes.count(),100)):
        n=nodes.nth(i)
        try:
            if not await n.is_visible(timeout=80):continue
            out.append({
              "name":await n.get_attribute("name"),
              "id":await n.get_attribute("id"),
              "placeholder":await n.get_attribute("placeholder"),
              "value":(await n.input_value(timeout=300))[:120]
            })
        except:continue
    return out[:60]

async def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    rep={"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"match_url":MATCH,
         "match_http":None,"selection":None,"market_link_sample":[],"betslip_http":None,"betslip_url":None,
         "betslip_text":None,"selection_visible_in_betslip":False,
         "candidate_actions":[],"fields":[],"status":"not_started"}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(service_workers="block")
        page=await ctx.new_page()
        try:
            r=await page.goto(MATCH,wait_until="domcontentloaded",timeout=25000)
            rep["match_http"]=r.status if r else None
            await page.wait_for_timeout(7000)
            rep["selection"]=await click_exact_market(page)
            if not rep["selection"]:
                rep["market_link_sample"]=getattr(page,"_mrx_candidates",[])[:80]
                rep["status"]="target_market_not_found"
            else:
                br=await page.goto(BETSLIP,wait_until="domcontentloaded",timeout=25000)
                rep["betslip_http"]=br.status if br else None
                rep["betslip_url"]=page.url
                await page.wait_for_timeout(1200)
                body=(await page.locator("body").inner_text(timeout=5000))
                rep["betslip_text"]=re.sub(r"\s+"," ",body).strip()[:4000]
                label=rep["selection"]["label"]
                # Match names and/or market should survive in the slip if session selection worked.
                rep["selection_visible_in_betslip"]=(
                    "Liverpool" in body and "Manchester City" in body and
                    (("Over" in body and "2.5" in body) or "X2" in body)
                )
                rep["candidate_actions"]=await collect_actions(page)
                rep["fields"]=await collect_fields(page)
                rep["status"]="BETSLIP_SELECTION_VERIFIED" if rep["selection_visible_in_betslip"] else "BETSLIP_OPEN_BUT_SELECTION_NOT_VERIFIED"
            try:await page.screenshot(path=str(ROOT/"premierbet_togo_deep_probe.png"),full_page=True,timeout=5000)
            except:pass
        except Exception as e:
            rep["status"]="browser_error";rep["error_type"]=type(e).__name__;rep["error"]=str(e)[:350]
        await ctx.close();await browser.close()
    OUT.write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(rep,indent=2,ensure_ascii=False))

if __name__=="__main__":asyncio.run(main())
