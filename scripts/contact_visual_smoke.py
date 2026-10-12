#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/contact-responsive")
OUT.mkdir(parents=True, exist_ok=True)

def no_overflow(page, label):
    size = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(size["d"], size["b"]) > size["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {size}")

def run_view(browser, width, height, label):
    ctx=browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page=ctx.new_page()
    page.goto("http://127.0.0.1:8000/contact.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".contact-card").first.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(500)

    no_overflow(page,label)

    if width <= 700:
        hero_h=page.locator(".mx-contact-hero").evaluate("(el)=>el.getBoundingClientRect().height")
        if hero_h > 130:
            raise AssertionError(f"{label}: Contact hero too tall ({hero_h}px)")
        if page.locator(".mx-contact-copy p").is_visible():
            raise AssertionError(f"{label}: secondary Contact description should be hidden")
        first_top=page.locator(".contact-card").first.evaluate("(el)=>el.getBoundingClientRect().top")
        if first_top > 245:
            raise AssertionError(f"{label}: contact channels start too low ({first_top}px)")
        nav=page.locator("#bottom-nav")
        nav.wait_for(state="visible", timeout=10000)
        if page.locator("#bottom-nav .bottom-nav-item").count()!=5:
            raise AssertionError(f"{label}: expected 5 bottom navigation items")

    cards=page.locator(".contact-card")
    if cards.count()!=7:
        raise AssertionError(f"{label}: expected 7 contact cards, got {cards.count()}")

    imgs=page.locator(".contact-card img").evaluate_all("imgs => imgs.map(i => ({src:i.getAttribute('src'),ok:i.complete && i.naturalWidth>0}))")
    broken=[i for i in imgs if not i["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken contact icons {broken}")

    # All contact links must remain tappable and valid destinations.
    links=page.locator(".contact-card a")
    if links.count()!=7:
        raise AssertionError(f"{label}: expected 7 contact links")
    for href in links.evaluate_all("els => els.map(e => e.getAttribute('href'))"):
        if not href or href=="#":
            raise AssertionError(f"{label}: invalid contact href {href!r}")

    columns=page.locator(".contact-grid").evaluate("(el)=>getComputedStyle(el).gridTemplateColumns.split(' ').length")
    expected = 3 if width >= 901 else 2
    if columns!=expected:
        raise AssertionError(f"{label}: expected {expected} contact columns, got {columns}")

    first_h=cards.first.bounding_box()["height"]
    max_card_h = 200 if width > 700 else 90
    if first_h>max_card_h:
        raise AssertionError(f"{label}: contact card remains too tall ({first_h} > {max_card_h})")

    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(OUT/f"contact-{width}.png"),full_page=True)
    print(f"PASS {label}: {width}x{height}, direct-channels/cards/icons/links/grid/overflow OK")
    ctx.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,1024,900,"desktop")
    run_view(browser,768,1024,"tablet")
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
