#!/usr/bin/env python3
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
TODAY = datetime.now(timezone.utc).date().isoformat()

CACHE_DATA = {
    "generated_at": f"{TODAY}T16:30:00Z",
    "matches": [
        {
            "id": "offline-1",
            "event_date": f"{TODAY}T18:00:00Z",
            "home_team": "Lomé Stars",
            "away_team": "Gold United",
            "league": "Test League",
            "category": "vip",
            "status": "scheduled",
            "prediction": {"type": "Plus de 1,5 but", "confidence": 82},
        },
        {
            "id": "offline-2",
            "event_date": f"{TODAY}T20:00:00Z",
            "home_team": "Blue FC",
            "away_team": "Night City",
            "league": "Test League",
            "category": "simple",
            "status": "scheduled",
            "prediction": {"type": "1X", "confidence": 77},
        },
    ],
}

def assert_no_overflow(page, label):
    values = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(values["d"], values["b"]) > values["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {values}")

def install_and_control(page):
    page.goto(BASE + "/index.html", wait_until="domcontentloaded", timeout=60000)
    page.evaluate("""async () => {
      const reg = await navigator.serviceWorker.register('/service-worker.js', {scope:'/'});
      await navigator.serviceWorker.ready;
      if (reg.waiting) reg.waiting.postMessage('skipWaiting');
    }""")
    page.wait_for_function("() => !!navigator.serviceWorker.controller", timeout=60000)

def run_case(browser, width, height, label):
    context = browser.new_context(
        viewport={"width":width,"height":height},
        service_workers="allow"
    )
    page = context.new_page()
    install_and_control(page)

    page.evaluate("(data) => localStorage.setItem('cachedData', JSON.stringify(data))", CACHE_DATA)

    context.set_offline(True)

    # 1. Unknown document must fall back to offline.html.
    page.goto(BASE + "/missing-offline-probe.html", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#offline-title", timeout=10000)
    assert "hors ligne" in page.locator("#offline-title").inner_text().lower()
    assert page.locator("#cache-count").inner_text().strip() == "2"
    assert page.locator(".cached-match").count() == 2

    logo = page.locator(".brand img")
    if not logo.evaluate("(img) => img.complete && img.naturalWidth > 0"):
        raise AssertionError(f"{label}: offline logo did not load from cache")

    mark = page.locator(".offline-mark")
    if not mark.evaluate("(img) => img.complete && img.naturalWidth > 0"):
        raise AssertionError(f"{label}: offline mark did not load from cache")

    assert_no_overflow(page, label + "-fallback")

    # 2. A pre-cached page with a query string must use its stable HTML shell.
    page.goto(BASE + "/pronos.html?cat=vip", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("body.mx-pronos-page", timeout=10000)
    if page.locator("#offline-title").count():
        raise AssertionError(f"{label}: pronos query URL incorrectly fell back to offline.html")

    page.wait_for_timeout(900)
    cards = page.locator(".match-card")
    if cards.count() < 1:
        raise AssertionError(f"{label}: cached pronostic data was not rendered offline")

    assert_no_overflow(page, label + "-pronos")

    # 3. Return to fallback and verify automatic recovery when network comes back.
    page.goto(BASE + "/another-missing-offline-probe.html", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#offline-title", timeout=10000)
    context.set_offline(False)
    page.wait_for_url("**/index.html", timeout=6000)

    print(f"PASS {label}: offline fallback, cached assets, cached data, query shell and recovery OK")
    context.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_case(browser, 1024, 900, "desktop")
    run_case(browser, 390, 844, "mobile")
    browser.close()
