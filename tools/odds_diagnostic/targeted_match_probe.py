#!/usr/bin/env python3
"""Read-only public bookmaker match-page probe. No logins, staking or bet submission."""
import asyncio
import datetime
import json
import pathlib
import re
from playwright.async_api import async_playwright

MATCHES = [
    {"provider": "sportybet", "kind": "live", "url": "https://www.sportybet.com/ng/lite/live/detail?eventId=sr%3Amatch%3A72335194&fromUrl=%2Fng%2Flite&marketGroupsName=Corners&sportId=sr%3Asport%3A1"},
    {"provider": "sportybet", "kind": "prematch_reference", "url": "https://www.sportybet.com/ng/lite/preMatch/detail?eventId=sr%3Amatch%3A72335194&marketGroupsName=Corners&sportId=sr%3Asport%3A1"},
    {"provider": "1xbet", "kind": "live", "url": "https://1xbet.com/en/live/football/214147-colombia-categoria-primera-a/760119822-alianza-valledupar-aguilas-doradas"},
]
OUT = pathlib.Path("odds_diagnostic_results/targeted_match_probe.json")
MARKET = re.compile(r"(?i)(?:total\s+(?:number\s+of\s+)?corners|corners?\s*(?:-|:)?\s*(?:o/u|over/under)|corners?\s+total)")
LINE_ODD = re.compile(r"(?i)\b(over|under|plus de|moins de)\s*(\d{1,2}[,.]\d)\s+(\d{1,3}[,.]\d{2,3})\b")

def parse_quotes(body):
    """Requires an explicit corner market header and a nearby qualified selection."""
    lines = [x.strip() for x in body.splitlines() if x.strip()]
    quotes = []
    for i, line in enumerate(lines):
        if not MARKET.search(line):
            continue
        for following in lines[i + 1:i + 7]:
            if len(following) > 100:
                continue
            m = LINE_ODD.search(following)
            if m:
                quotes.append({"market": line[:80], "selection": m.group(1), "line": m.group(2), "odd": m.group(3)})
                if len(quotes) == 5:
                    return quotes
    return quotes

async def run_one(browser, match):
    result = {"provider": match["provider"], "page_type": match["kind"],
              "fixture": "Alianza Valledupar – Aguilas Doradas",
              "http_status": None, "rendered_title": None, "page_text_length": 0,
              "home_team_visible": False, "away_team_visible": False,
              "corner_word_visible": False, "corner_market_header_visible": False,
              "public_corner_contexts": [], "quotes": [], "screenshot_saved": False,
              "match_page_verified": False, "quote_verified_for_match": False}
    page = await browser.new_page(viewport={"width": 1366, "height": 900})
    try:
        response = await page.goto(match["url"], wait_until="domcontentloaded", timeout=23000)
        result["http_status"] = response.status if response else None
        if not response or response.status >= 400 or response.status in (203, 204):
            result["status"] = "access_restricted_or_invalid_response"
            return result
        await page.wait_for_timeout(6500)
        result["rendered_title"] = (await page.title())[:160]
        body = (await page.locator("body").inner_text(timeout=6000))[:110000]
        result["page_text_length"] = len(body)
        result["home_team_visible"] = "alianza" in body.lower()
        result["away_team_visible"] = "aguilas" in body.lower() or "águilas" in body.lower()
        result["match_page_verified"] = result["home_team_visible"] and result["away_team_visible"]
        result["corner_word_visible"] = bool(re.search(r"\bcorners?\b", body, re.I))
        result["corner_market_header_visible"] = bool(MARKET.search(body))
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"\bcorners?\b", line, re.I):
                context = " / ".join(x.strip()[:60] for x in lines[max(0,i-1):i+3])
                if context not in result["public_corner_contexts"]:
                    result["public_corner_contexts"].append(context[:230])
                if len(result["public_corner_contexts"]) >= 5:
                    break
        if result["match_page_verified"]:
            result["quotes"] = parse_quotes(body)
        result["quote_verified_for_match"] = bool(result["quotes"]) and result["match_page_verified"]
        result["status"] = ("corner_quote_visible" if result["quote_verified_for_match"] else
                            "match_no_corner_quote" if result["match_page_verified"] else
                            "wrong_or_empty_page")
        screenshot = OUT.parent / (match["provider"] + "_" + match["kind"] + ".png")
        await page.screenshot(path=str(screenshot), full_page=False, timeout=7000)
        result["screenshot_saved"] = True
    except Exception as exc:
        result["status"] = "navigation_exception"
        result["error_type"] = type(exc).__name__
    finally:
        await page.close()
    return result

async def main():
    OUT.parent.mkdir(exist_ok=True, parents=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        results = []
        for target in MATCHES:
            results.append(await run_one(browser, target))
        await browser.close()
    report = {
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "live_status_independently_verified": False,
        "bookmaker_live_corner_odds_verified": any(x["quote_verified_for_match"] and x["page_type"] == "live" for x in results),
        "results": results,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
