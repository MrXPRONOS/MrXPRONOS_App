#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/assistant-responsive")
OUT.mkdir(parents=True, exist_ok=True)

def no_overflow(page, label):
    size = page.evaluate("() => ({v: innerWidth, d: document.documentElement.scrollWidth, b: document.body.scrollWidth})")
    if max(size["d"], size["b"]) > size["v"] + 1:
        raise AssertionError(f"{label}: page horizontal overflow {size}")

def run_view(browser, width, height, label):
    ctx = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto("http://127.0.0.1:8000/index.html", wait_until="domcontentloaded", timeout=60000)
    button = page.locator(".assistant-button")
    button.wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(350)

    no_overflow(page, label)

    mark = button.locator("img")
    if "mrxpronos-mark.webp" not in (mark.get_attribute("src") or ""):
        raise AssertionError(f"{label}: assistant button does not use local Mr XPRONOS mark")
    if not mark.evaluate("(img) => img.complete && img.naturalWidth > 0"):
        raise AssertionError(f"{label}: assistant button mark is broken")

    bb = button.bounding_box()
    if not bb:
        raise AssertionError(f"{label}: assistant button has no geometry")

    if width > 700:
        if not (145 <= bb["width"] <= 200 and 52 <= bb["height"] <= 64):
            raise AssertionError(f"{label}: desktop/tablet launcher geometry unexpected {bb}")
    else:
        if bb["width"] > 62 or bb["height"] > 62:
            raise AssertionError(f"{label}: mobile launcher too large {bb}")
        nav = page.locator("#bottom-nav")
        if nav.count() and nav.is_visible():
            nav_bb = nav.bounding_box()
            if nav_bb and bb["y"] + bb["height"] > nav_bb["y"] + 2:
                raise AssertionError(f"{label}: assistant launcher overlaps bottom navigation")

    button.click()
    panel = page.locator(".assistant-window")
    panel.wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(250)

    pbb = panel.bounding_box()
    if not pbb:
        raise AssertionError(f"{label}: assistant panel has no geometry")

    if width >= 901:
        if not (510 <= pbb["width"] <= 555):
            raise AssertionError(f"{label}: desktop panel should be compact, got {pbb}")
        if pbb["x"] < width - pbb["width"] - 32:
            raise AssertionError(f"{label}: desktop panel not anchored right")
    elif width >= 701:
        if pbb["width"] < width - 40:
            raise AssertionError(f"{label}: tablet panel leaves too much empty space {pbb}")
        if pbb["x"] < 10:
            raise AssertionError(f"{label}: tablet panel should keep outer margin {pbb}")
    else:
        if abs(pbb["x"]) > 1 or abs(pbb["y"]) > 1:
            raise AssertionError(f"{label}: mobile panel should start at viewport origin {pbb}")
        if abs(pbb["width"] - width) > 2 or abs(pbb["height"] - height) > 3:
            raise AssertionError(f"{label}: mobile panel should fill viewport {pbb}")

    if page.locator(".assistant-header").bounding_box()["height"] > (86 if width > 700 else 76):
        raise AssertionError(f"{label}: assistant header too tall")

    if page.locator(".quick-actions .btn").count() < 3:
        raise AssertionError(f"{label}: quick actions missing")

    assistant_message = page.locator(".message.assistant").first
    assistant_message.wait_for(state="visible", timeout=5000)
    if assistant_message.bounding_box()["width"] > pbb["width"] - 12:
        raise AssertionError(f"{label}: assistant message overflows panel")

    send = page.locator("#assistant-send")
    if width <= 700 and send.bounding_box()["width"] > 58:
        raise AssertionError(f"{label}: mobile send control should stay compact")

    panel.evaluate("(el) => { const r=el.getBoundingClientRect(); if (el.scrollWidth > el.clientWidth + 1) throw new Error('panel horizontal overflow'); }")

    page.screenshot(path=str(OUT / f"assistant-{width}.png"), full_page=True)

    page.locator(".assistant-close").click()
    button.wait_for(state="visible", timeout=3000)

    if errors:
        raise AssertionError(f"{label}: page errors {errors}")

    print(f"PASS {label}: {width}x{height}, launcher/panel/header/messages/actions/input/overflow OK")
    ctx.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_view(browser, 1024, 900, "desktop")
    run_view(browser, 768, 1024, "tablet")
    run_view(browser, 390, 844, "mobile")
    run_view(browser, 320, 720, "small-mobile")
    browser.close()
