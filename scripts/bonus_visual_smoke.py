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

    if width <= 700:
        hero_h = page.locator(".mx-bonus-hero").evaluate("(el) => el.getBoundingClientRect().height")
        if hero_h > 135:
            raise AssertionError(f"{label}: Bonus hero too tall ({hero_h}px)")

        if page.locator(".mx-bonus-copy p").is_visible():
            raise AssertionError(f"{label}: secondary Bonus hero description should be hidden")

        disclaimer = page.locator(".mx-offer-disclaimer")
        if disclaimer.get_attribute("open") is not None:
            raise AssertionError(f"{label}: conditions block should be collapsed by default")

        first_top = page.locator(".bonus-premium-card").first.evaluate("(el) => el.getBoundingClientRect().top")
        max_top = 350 if width >= 390 else 345
        if first_top > max_top:
            raise AssertionError(f"{label}: first offer starts too low ({first_top}px > {max_top}px)")

        desc = page.locator(".bonus-premium-card").first.locator(".bonus-card-body p")
        if desc.count() and desc.is_visible():
            raise AssertionError(f"{label}: offer description should be hidden until Details is opened")

        nav = page.locator("#bottom-nav")
        nav.wait_for(state="visible", timeout=10000)
        if page.locator("#bottom-nav .bottom-nav-item").count() != 5:
            raise AssertionError(f"{label}: bottom navigation does not have 5 items")

    cards = page.locator(".bonus-premium-card")
    total = cards.count()
    if total < 6:
        raise AssertionError(f"{label}: too few offer cards ({total})")

    if page.locator(".bonus-card-logo").count() != 0:
        raise AssertionError(f"{label}: duplicated bookmaker logo still rendered")

    banner_locator = page.locator(".bonus-banner-img")
    for i in range(banner_locator.count()):
        banner_locator.nth(i).scroll_into_view_if_needed()
        page.wait_for_timeout(35)
    banners = banner_locator.evaluate_all("""imgs => imgs.map(i => ({
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
    print(f"PASS {label}: {width}x{height}, content-first/offers/filter/modal/assets/overflow OK")
    context.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
