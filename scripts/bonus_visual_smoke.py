#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/bonus-responsive")
OUT.mkdir(parents=True, exist_ok=True)

def no_overflow(page, label):
    size = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(size["d"], size["b"]) > size["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {size}")

def run_view(browser, width, height, label):
    context = browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page = context.new_page()
    page.goto("http://127.0.0.1:8000/bonus.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".bonus-premium-card").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(900)

    no_overflow(page, label)

    cards = page.locator(".bonus-premium-card")
    total = cards.count()
    if total < 6:
        raise AssertionError(f"{label}: too few offer cards ({total})")

    if page.locator(".bonus-card-logo").count() != 0:
        raise AssertionError(f"{label}: duplicated bookmaker logo still rendered")

    banners = page.locator(".bonus-banner-img").evaluate_all("""imgs => imgs.map(i => ({
      src:i.getAttribute('src'), ok:i.complete && i.naturalWidth>0,
      w:i.naturalWidth,h:i.naturalHeight
    }))""")
    broken=[i for i in banners if not i["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken offer banners {broken[:3]}")
    if len(banners) != total:
        raise AssertionError(f"{label}: expected exactly one banner per card")

    selector = page.locator("#bonus-bookmaker-select")
    if selector.count() != 1:
        raise AssertionError(f"{label}: bookmaker selector missing")
    options = selector.locator("option")
    if options.count() < 2:
        raise AssertionError(f"{label}: bookmaker options missing")

    selector.select_option(index=1)
    page.wait_for_timeout(120)
    filtered = page.locator(".bonus-premium-card").count()
    if filtered < 1 or filtered >= total:
        raise AssertionError(f"{label}: bookmaker filtering failed ({filtered}/{total})")
    selector.select_option("all")
    page.wait_for_timeout(120)

    details = page.locator(".bonus-premium-card button[data-index]").first
    details.click()
    page.locator("#bonus-modal").wait_for(state="visible", timeout=5000)
    if not page.locator("#bonus-modal-title").inner_text().strip():
        raise AssertionError(f"{label}: bonus modal title empty")
    page.locator("#bonus-modal .close").click()
    page.locator("#bonus-modal").wait_for(state="hidden", timeout=5000)

    if width <= 700:
        banner_h = page.locator(".bonus-card-art").first.bounding_box()["height"]
        if banner_h > 150:
            raise AssertionError(f"{label}: offer banner still too tall ({banner_h})")
        action_boxes = page.locator(".bonus-actions .btn").first.evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")
        if action_boxes and min(action_boxes) < 34:
            raise AssertionError(f"{label}: offer action touch target too small {action_boxes}")

    no_overflow(page, label)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(120)
    page.screenshot(path=str(OUT/f"bonus-{width}.png"), full_page=True)
    print(f"PASS {label}: {width}x{height}, offers/filter/modal/assets/overflow OK")
    context.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
