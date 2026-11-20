#!/usr/bin/env python3
"""Execute the actual (unmodified) Mini App scripts in Chromium with mocked Telegram/API.
No production calls, Telegram secrets, or real-user data.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
worker = (ROOT / "worker.js").read_text(encoding="utf-8")
start = worker.index('const html="') + len('const html=')
end = worker.index(';\n', start)
html = json.loads(worker[start:end])
now = 1795160000000
day = "2026-11-20"
initial = {
    "user": {"user_id": "e2e-1", "display_name": "Joueur E2E", "username": "e2e",
             "confirmed_xp": 37, "confirmed_taps": 25,
             "created_ms": now - 86400000,
             "last_sync_ms": now, "next_sync_ms": now + 43200000},
    "game_features": {"tap": True, "wheel": True, "daily": True, "missions": True},
    "missions": [], "progression": {"level": 1, "confirmed_xp": 37},
    "profile": {}, "wallet": {"balance": 5, "total_events": 0,
                             "today_goals": [], "weekly": {"days": 0, "target": 4}},
    "shop": {"catalog": [], "inventory": [], "balance": 5, "available": True},
    "reward_intents": [], "wheel_plans": {},
    "wheel_claims": [], "daily_claims": [], "server_time": now,
}
claims = {}
events = []
errors = []
today = None

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    try:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Initial JS runs ahead of application scripts at navigation.
        page.add_init_script("""() => {
           const bucket = {};
           window.Telegram = {WebApp:{
             initData: 'test-signed-initdata',
             initDataUnsafe: {user:{id:123456,first_name:'Joueur E2E'}},
             ready(){},expand(){},
             DeviceStorage:{
               getItem(k,fn){fn(null,bucket[k]||null)},
               setItem(k,v,fn){bucket[k]=v;if(fn)fn(null,true)}
             },
             HapticFeedback:{impactOccurred(){},notificationOccurred(){}}
           }};
        }""")
        def route_handler(route):
            req = route.request
            url = req.url
            if url == "https://mrxp-e2e.test/":
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
            elif url.startswith("https://mrxp-e2e.test/api/"):
                path = url.split("https://mrxp-e2e.test", 1)[1]
                body = req.post_data_json if req.method == "POST" else {}
                events.append({"path":path, "body":body})
                if path == "/api/bootstrap":
                    value = {**initial,
                      "reward_intents": [
                        {"kind":k, "day":day, "reward_key":v["reward_key"],
                         "xp_awarded":v["xp_awarded"]}
                        for k,v in claims.items()
                      ],
                      "wheel_plans": {day:claims["wheel"]["reward_key"]} if "wheel" in claims else {},
                    }
                elif path == "/api/rewards/claim":
                    kind = body.get("kind")
                    if kind not in ("daily","wheel"):
                        route.fulfill(status=400,content_type="application/json",
                                      body='{"error":"Invalid kind"}')
                        return
                    duplicate = kind in claims
                    if not duplicate:
                        claims[kind] = {"reward_key":"daily" if kind=="daily" else "xp25",
                                        "xp_awarded":100 if kind=="daily" else 25}
                    value = {"ok":True, "kind":kind, "day":day, "duplicate":duplicate,
                             "confirmed":False, **claims[kind]}
                elif path == "/api/game-features":
                    value = {"features":initial["game_features"]}
                elif path == "/api/sync":
                    value = {"error":"Next 12h sync not available"}
                    route.fulfill(status=429,content_type="application/json",body=json.dumps(value))
                    return
                elif path == "/api/missions":
                    value = {"missions":[], "progression": initial["progression"]}
                elif path == "/api/credits":
                    value = {"wallet":initial["wallet"]}
                elif path == "/api/profile":
                    value = {"profile":initial["profile"], "progression":initial["progression"]}
                elif path == "/api/shop":
                    value = {"wallet":initial["wallet"],"shop":initial["shop"]}
                else:
                    value = {}
                route.fulfill(status=200,content_type="application/json",body=json.dumps(value))
            else:
                route.abort()
        page.route("**/*",route_handler)
        page.goto("https://mrxp-e2e.test/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_function("document.querySelector('#profile-name')?.textContent==='Joueur E2E'", timeout=15000)
        assert page.locator("#xp-value").inner_text().strip() == "37"
        # Real button handlers: no simulated fake XP is considered confirmed.
        page.locator("#daily-button").evaluate("(el)=>el.click()")
        page.wait_for_function("document.querySelector('#daily-button')?.disabled===true", timeout=8000)
        assert "daily" in claims, "Daily did not create a server intent"
        assert page.locator("#xp-value").inner_text().strip() == "37"
        page.locator("#mrxp-wheel-shortcut-button").evaluate("(el)=>el.click()")
        assert page.locator("#mrxp-wheel-game").is_visible()
        page.locator("#wheel-button").evaluate("(el)=>el.click()")
        page.wait_for_function("document.querySelector('#wheel-result')?.textContent.includes('25 XP')",timeout=10000)
        assert "wheel" in claims, "Wheel did not call server claim endpoint"
        assert page.locator("#xp-value").inner_text().strip() == "37"
        assert len([x for x in events if x["path"]=="/api/rewards/claim"]) == 2
        assert not errors, "Browser runtime errors: "+repr(errors)
        print("PASS: real browser JS, bootstrap, server-verified daily/wheel, no premature confirmed XP")
    finally:
        browser.close()
