#!/usr/bin/env python3
"""Compatibility probe for sportsbooks that may accept Togo registrations.

Safety boundaries:
- no account is created
- no personal data is entered
- no deposit/stake/wager is made
- no odds are clicked
- no booking/share code is generated
The probe only checks public registration/country availability, prematch football
surface availability, and whether a public Book/Save/Share/Booking-Code control
exists in the rendered UI.
"""
import asyncio, datetime as dt, json, pathlib, re
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

OUT=pathlib.Path("odds_diagnostic_results/togo_bookmaker_compatibility.json")
ROOT=OUT.parent

SITES=[
 {"name":"PremierBet","registration":"https://www.premierbet.com/","sports":"https://www.premierbet.com/"},
 {"name":"1xBet","registration":"https://1xbet.com/en/registration","sports":"https://1xbet.com/en/line/football"},
 {"name":"1win","registration":"https://1win.com/","sports":"https://1win.com/"},
 {"name":"BetWinner","registration":"https://betwinner.com/en/registration","sports":"https://betwinner.com/en/line/football"},
 {"name":"MelBet","registration":"https://melbet.com/en/registration","sports":"https://melbet.com/en/line/football"},
 {"name":"MegaPari","registration":"https://megapari.com/en/registration","sports":"https://megapari.com/en/line/football"},
 {"name":"WinWin","registration":"https://winwin.bet/","sports":"https://winwin.bet/"},
 {"name":"BetAndYou","registration":"https://betandyou.com/en/registration","sports":"https://betandyou.com/en/line/football"},
 {"name":"SpinBetter","registration":"https://spinbetter.com/en/registration","sports":"https://spinbetter.com/en/line/football"},
 {"name":"FANSPORT","registration":"https://fan-sport.com/en/registration","sports":"https://fan-sport.com/en/line/football"},
]

TOGO=re.compile(r"\b(?:togo|togolese|togolais|togolaise)\b",re.I)
PHONE=re.compile(r"(?:\+|00)\s*228\b")
REG_WORDS=re.compile(r"\b(?:register|registration|sign.?up|s.?inscrire|inscription)\b",re.I)
FOOTBALL=re.compile(r"\bfootball\b",re.I)
PREMATCH=re.compile(r"\b(?:sports|line|prematch|pre-match|upcoming|football)\b",re.I)
BOOKING=re.compile(
    r"\b(?:booking\s*(?:code|number)?|book\s*(?:bet|ticket|betslip)?|"
    r"save\s*(?:bet|ticket|betslip)?|share\s*(?:bet|ticket|betslip|coupon)?|"
    r"reservation\s*code|sharecode|load\s*(?:code|betslip))\b",re.I)
BLOCK=re.compile(r"(?:access denied|forbidden|verify you are human|captcha|cloudflare|restricted in your)",re.I)

async def page_text(page,limit=40000):
    try:return (await page.locator("body").inner_text(timeout=5000))[:limit]
    except:return ""

async def country_evidence(page):
    evidence=[]
    body=await page_text(page)
    if TOGO.search(body): evidence.append("body_text_togo")
    if PHONE.search(body): evidence.append("body_text_+228")
    # select/options
    try:
        opts=await page.locator("option").all_inner_texts()
        if any(TOGO.search(x or "") for x in opts):evidence.append("select_option_togo")
        if any(PHONE.search(x or "") for x in opts):evidence.append("select_option_+228")
    except: pass
    # input/select aria and nearby rendered labels, useful for custom country widgets
    try:
        nodes=page.locator('input,select,[role="combobox"],[role="option"]')
        for i in range(min(await nodes.count(),350)):
            n=nodes.nth(i)
            try:
                vals=[
                    await n.get_attribute("value"),await n.get_attribute("aria-label"),
                    await n.get_attribute("placeholder"),await n.get_attribute("title")
                ]
                s=" ".join(str(x or "") for x in vals)
                if TOGO.search(s): evidence.append("form_attribute_togo");break
                if PHONE.search(s): evidence.append("form_attribute_+228");break
            except:continue
    except:pass
    return sorted(set(evidence)),body

async def public_actions(page):
    found=[]
    loc=page.locator('button,[role="button"],a,[aria-label],[title]')
    for i in range(min(await loc.count(),900)):
        n=loc.nth(i)
        try:
            if not await n.is_visible(timeout=80):continue
            vals=[
                (await n.inner_text(timeout=180)).strip()[:120],
                str(await n.get_attribute("aria-label") or "")[:120],
                str(await n.get_attribute("title") or "")[:120],
            ]
            label=re.sub(r"\s+"," "," | ".join(x for x in vals if x)).strip()
            if label and BOOKING.search(label) and label not in found:
                found.append(label)
                if len(found)>=25:break
        except:continue
    return found

async def inspect(browser,site):
    res={
      "provider":site["name"],"registration_url":site["registration"],
      "registration_http":None,"registration_final_url":None,
      "registration_accessible":False,"togo_registration_evidence":[],
      "togo_registration_verified":False,"sports_url":site["sports"],
      "sports_http":None,"sports_final_url":None,"prematch_football_visible":False,
      "booking_share_controls":[],"booking_share_feature_visible":False,
      "status":"not_tested"
    }
    ctx=await browser.new_context(service_workers="block",accept_downloads=False)
    page=await ctx.new_page()
    try:
        rr=await page.goto(site["registration"],wait_until="domcontentloaded",timeout=22000)
        res["registration_http"]=rr.status if rr else None
        res["registration_final_url"]=page.url
        await page.wait_for_timeout(2500)
        body=await page_text(page,18000)
        if rr and rr.status<400 and not BLOCK.search(body[:2500]):
            res["registration_accessible"]=True
            ev,_=await country_evidence(page)
            res["togo_registration_evidence"]=ev
            res["togo_registration_verified"]=bool(ev)
        # Sports/prematch public surface; read only.
        sr=await page.goto(site["sports"],wait_until="domcontentloaded",timeout=22000)
        res["sports_http"]=sr.status if sr else None
        res["sports_final_url"]=page.url
        await page.wait_for_timeout(3500)
        sport_body=await page_text(page,26000)
        if sr and sr.status<400 and not BLOCK.search(sport_body[:2500]):
            res["prematch_football_visible"]=bool(FOOTBALL.search(sport_body) and PREMATCH.search(sport_body))
            acts=await public_actions(page)
            res["booking_share_controls"]=acts
            res["booking_share_feature_visible"]=bool(acts or BOOKING.search(sport_body))
        if res["togo_registration_verified"] and res["prematch_football_visible"]:
            res["status"]="TOGO_AND_PREMATCH_VERIFIED"
        elif res["togo_registration_verified"]:
            res["status"]="TOGO_VERIFIED_PREMATCH_NOT_VISIBLE"
        elif res["registration_accessible"]:
            res["status"]="REGISTRATION_ACCESSIBLE_TOGO_NOT_PROVEN"
        else:
            res["status"]="REGISTRATION_UNAVAILABLE_OR_BLOCKED"
        return res
    except Exception as e:
        res["status"]="browser_error";res["error_type"]=type(e).__name__;return res
    finally:
        try:
            ROOT.mkdir(parents=True,exist_ok=True)
            p=re.sub(r"[^a-z0-9]+","_",site["name"].lower())
            await page.screenshot(path=str(ROOT/(p+"_togo_probe.png")),timeout=2500)
        except:pass
        await ctx.close()

async def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        results=[]
        for site in SITES:
            item=await inspect(browser,site)
            results.append(item)
            print(f'{item["provider"]}: {item["status"]}; togo={item["togo_registration_evidence"]}; booking={item["booking_share_feature_visible"]}',flush=True)
        await browser.close()
    output={
      "run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "mode":"read_only_togo_registration_and_booking_feature_probe",
      "no_registration_no_odds_click_no_wager":True,
      "providers_count":len(results),
      "togo_verified_count":sum(r["togo_registration_verified"] for r in results),
      "prematch_visible_count":sum(r["prematch_football_visible"] for r in results),
      "booking_feature_visible_count":sum(r["booking_share_feature_visible"] for r in results),
      "results":results
    }
    OUT.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(output,indent=2,ensure_ascii=False),flush=True)

if __name__=="__main__":asyncio.run(main())
