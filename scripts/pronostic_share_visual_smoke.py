#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/pronostic-share")
OUT.mkdir(parents=True, exist_ok=True)

MATCH = {
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "home_logo": "assets/images/home.webp",
    "away_logo": "assets/images/away.webp",
    "prediction": {
        "type": "Double chance 1X",
        "confidence": 86,
    },
}

def assert_inside(box, width, height, label):
    if not box:
        raise AssertionError(f"{label}: popup has no geometry")
    if box["x"] < -1 or box["y"] < -1:
        raise AssertionError(f"{label}: popup starts outside viewport {box}")
    if box["x"] + box["width"] > width + 2:
        raise AssertionError(f"{label}: popup horizontal overflow {box}")
    if box["y"] + box["height"] > height + 3:
        raise AssertionError(f"{label}: popup vertical overflow {box}")

def open_share(page):
    page.evaluate("(match) => window.sharePronostic(match)", MATCH)
    popup = page.locator("#pronostic-share-popup")
    popup.wait_for(state="visible", timeout=3000)
    page.wait_for_timeout(280)
    return popup

def run_view(browser, width, height, label):
    ctx = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto("http://127.0.0.1:8000/pronos.html", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function("() => typeof window.sharePronostic === 'function'", timeout=15000)

    # System confirm must never be used by pronostic sharing anymore.
    page.evaluate("""() => {
      window.__shareUrls = [];
      window.open = (url) => {
        window.__shareUrls.push(String(url));
        return {};
      };
      window.confirm = () => {
        throw new Error("Legacy confirm() must not be called");
      };
    }""")

    popup = open_share(page)
    sheet = popup.locator(".pronostic-share-sheet")
    box = sheet.bounding_box()
    assert_inside(box, width, height, label)

    if width <= 700:
        if abs((box["y"] + box["height"]) - height) > 4:
            raise AssertionError(f"{label}: share chooser is not bottom-sheet anchored {box}")
        if box["width"] < width - 3:
            raise AssertionError(f"{label}: mobile share chooser should use full width {box}")
    else:
        if box["width"] > 525:
            raise AssertionError(f"{label}: desktop/tablet share chooser too wide {box}")

    text = sheet.inner_text()
    for expected in ("Arsenal", "Chelsea", "Double chance 1X", "Confiance 86%"):
        if expected not in text:
            raise AssertionError(f"{label}: missing preview text {expected!r}")

    options = popup.locator("[data-share-platform]")
    if options.count() != 2:
        raise AssertionError(f"{label}: expected exactly two share platforms")

    wa = popup.locator('[data-share-platform="whatsapp"]')
    tg = popup.locator('[data-share-platform="telegram"]')
    if "WhatsApp" not in wa.inner_text() or "Telegram" not in tg.inner_text():
        raise AssertionError(f"{label}: platform labels missing")

    for selector, asset in [
        ('[data-share-platform="whatsapp"] img', "whatsapp.webp"),
        ('[data-share-platform="telegram"] img', "telegram.webp"),
    ]:
        img = popup.locator(selector)
        if asset not in (img.get_attribute("src") or ""):
            raise AssertionError(f"{label}: wrong platform icon for {asset}")
        if not img.evaluate("(el) => el.complete && el.naturalWidth > 0"):
            raise AssertionError(f"{label}: broken platform icon {asset}")

    if not page.locator("body").evaluate("(el) => el.classList.contains('mx-overlay-open')"):
        raise AssertionError(f"{label}: body is not locked while share popup is open")

    page.screenshot(path=str(OUT / f"pronostic-share-{width}.png"), full_page=True)

    wa.click()
    page.wait_for_timeout(100)
    if popup.is_visible():
        raise AssertionError(f"{label}: popup did not close after WhatsApp selection")
    wa_url = page.evaluate("() => window.__shareUrls.at(-1) || ''")
    if not wa_url.startswith("https://wa.me/"):
        raise AssertionError(f"{label}: unexpected WhatsApp URL {wa_url}")

    popup = open_share(page)
    tg.click()
    page.wait_for_timeout(100)
    tg_url = page.evaluate("() => window.__shareUrls.at(-1) || ''")
    if not tg_url.startswith("https://t.me/share/url"):
        raise AssertionError(f"{label}: unexpected Telegram URL {tg_url}")

    popup = open_share(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    if popup.is_visible():
        raise AssertionError(f"{label}: Escape did not close share popup")

    if page.locator("body").evaluate("(el) => el.classList.contains('mx-overlay-open')"):
        raise AssertionError(f"{label}: body lock was not released")

    if errors:
        raise AssertionError(f"{label}: page errors {errors}")

    print(f"PASS {label}: {width}x{height}, premium WhatsApp/Telegram share chooser OK")
    ctx.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_view(browser, 1024, 900, "desktop")
    run_view(browser, 768, 1024, "tablet")
    run_view(browser, 390, 844, "mobile")
    run_view(browser, 320, 720, "small-mobile")
    browser.close()
