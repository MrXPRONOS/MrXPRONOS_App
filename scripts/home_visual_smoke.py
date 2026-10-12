#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/home-responsive")
OUT.mkdir(parents=True, exist_ok=True)

def no_overflow(page, label):
    size = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    maximum = max(size["d"], size["b"])
    if maximum > size["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {maximum}px > {size['v']}px")

def run_view(browser, width, height, label):
    context = browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page = context.new_page()
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto("http://127.0.0.1:8000/index.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".mx-feature-card").first.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(900)

    no_overflow(page, label)

    showcase = page.locator(".mx-home-showcase")
    if showcase.count() != 1 or not showcase.is_visible():
        raise AssertionError(f"{label}: home showcase missing")

    page.wait_for_function("""() => {
      const top=document.querySelector('#top-today-picks');
      const verified=document.querySelector('#verified-picks');
      const settled=(el)=>el && (el.querySelector('.pick-card') || el.querySelector('.no-events'));
      return settled(top) && settled(verified);
    }""", timeout=10000)

    top_cards = page.locator("#top-today-picks .pick-card")
    verified_cards = page.locator("#verified-picks .pick-card")
    if top_cards.count() > 3:
        raise AssertionError(f"{label}: too many highlighted daily selections ({top_cards.count()})")
    if verified_cards.count() > 3:
        raise AssertionError(f"{label}: too many verified result cards ({verified_cards.count()})")

    proofbar = page.locator(".mx-home-proofbar")
    if proofbar.count() != 1 or not proofbar.is_visible():
        raise AssertionError(f"{label}: performance proof bar missing")

    cards = page.locator(".mx-feature-card")
    if cards.count() != 3:
        raise AssertionError(f"{label}: expected 3 primary action cards, got {cards.count()}")

    hrefs = cards.evaluate_all("els => els.map(e => e.getAttribute('href'))")
    expected = ["pronos.html", "live.html", "bonus.html"]
    if hrefs != expected:
        raise AssertionError(f"{label}: primary action links changed: {hrefs}")

    images = page.locator(".mx-feature-card img").evaluate_all(
        "imgs => imgs.map(i => ({src:i.getAttribute('src'), ok:i.complete && i.naturalWidth>0}))"
    )
    broken = [item for item in images if not item["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken primary action assets {broken}")

    if width <= 700:
        hero_h = page.locator(".mx-hero").evaluate("(el)=>el.getBoundingClientRect().height")
        max_hero = 240 if width >= 390 else 222
        if hero_h > max_hero:
            raise AssertionError(f"{label}: hero too tall ({hero_h}px > {max_hero}px)")

        hero_desc = page.locator(".mx-hero-copy > p")
        if hero_desc.count() and hero_desc.is_visible():
            raise AssertionError(f"{label}: secondary hero description should be hidden")

        grid = page.locator(".mx-feature-grid")
        grid_top = grid.evaluate("(el)=>el.getBoundingClientRect().top")
        grid_bottom = grid.evaluate("(el)=>el.getBoundingClientRect().bottom")
        if grid_top > 310:
            raise AssertionError(f"{label}: primary actions start too low ({grid_top}px)")
        if grid_bottom > 415:
            raise AssertionError(f"{label}: primary actions do not fit early enough ({grid_bottom}px)")

        card_desc = cards.first.locator("p")
        if card_desc.count() and card_desc.is_visible():
            raise AssertionError(f"{label}: primary action descriptions should be hidden")

        details = page.locator(".mx-home-detail")
        if details.count() != 2:
            raise AssertionError(f"{label}: expected two secondary detail sections")
        for i in range(details.count()):
            if details.nth(i).get_attribute("open") is not None:
                raise AssertionError(f"{label}: secondary detail section {i} should be collapsed")

        details.first.locator("summary").click()
        if details.first.get_attribute("open") is None:
            raise AssertionError(f"{label}: collapsed secondary section cannot be opened")
        details.first.locator("summary").click()

        for group_name, group in [("daily", top_cards), ("verified", verified_cards)]:
            if group.count():
                heights = group.evaluate_all("(nodes)=>nodes.map(n=>n.getBoundingClientRect().height)")
                if max(heights) > 138:
                    raise AssertionError(f"{label}: {group_name} home card too tall: {heights}")

        proof_h = proofbar.evaluate("(el)=>el.getBoundingClientRect().height")
        if proof_h > 52:
            raise AssertionError(f"{label}: performance proof bar too tall ({proof_h}px)")

        support_desc = page.locator(".mx-support p")
        if support_desc.count() and support_desc.is_visible():
            raise AssertionError(f"{label}: support description should not add mobile reading load")

        nav = page.locator("#bottom-nav")
        nav.wait_for(state="visible", timeout=10000)
        nav_items = page.locator("#bottom-nav .bottom-nav-item")
        if nav_items.count() != 5:
            raise AssertionError(f"{label}: expected 5 bottom navigation items, got {nav_items.count()}")
    else:
        details = page.locator(".mx-home-detail")
        for i in range(details.count()):
            if details.nth(i).get_attribute("open") is None:
                raise AssertionError(f"{label}: desktop secondary sections should remain expanded")

    no_overflow(page, label)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(150)
    page.screenshot(path=str(OUT/f"home-{width}.png"), full_page=True)

    if page_errors:
        raise AssertionError(f"{label}: page errors {page_errors}")

    print(f"PASS {label}: {width}x{height}, content-first/actions/selections/results/proof/details/navigation/overflow OK")
    context.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_view(browser, 1024, 900, "desktop")
    run_view(browser, 390, 844, "mobile")
    run_view(browser, 320, 720, "small-mobile")
    browser.close()
