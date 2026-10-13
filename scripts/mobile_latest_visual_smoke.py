#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path("artifacts/mobile-latest")
OUT.mkdir(parents=True,exist_ok=True)

def assert_no_overflow(page,label):
    size=page.evaluate("() => ({w:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(size["d"],size["b"]) > size["w"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {size}")

def run_mobile(browser,width,height,label):
    ctx=browser.new_context(viewport={"width":width,"height":height},service_workers="block")
    page=ctx.new_page()
    page.goto("http://127.0.0.1:8000/index.html",wait_until="domcontentloaded",timeout=60000)
    page.locator(".assistant-button").wait_for(state="visible",timeout=12000)
    page.wait_for_timeout(500)
    assert_no_overflow(page,label)

    # Latest assistant improvements must be genuinely mobile, not desktop-only.
    page.locator(".assistant-button").click()
    panel=page.locator(".assistant-window")
    panel.wait_for(state="visible",timeout=3000)
    page.wait_for_timeout(250)

    input_el=page.locator("#assistant-input")
    font_size=float(input_el.evaluate("(el)=>parseFloat(getComputedStyle(el).fontSize)"))
    if font_size < 16:
        raise AssertionError(f"{label}: assistant input must be >=16px to avoid iOS focus zoom, got {font_size}")

    pseudo=page.locator("#assistant-send").evaluate("(el)=>getComputedStyle(el,'::after').content")
    if "↑" not in pseudo:
        raise AssertionError(f"{label}: compact mobile send arrow missing: {pseudo}")

    quick=page.locator(".quick-actions")
    if quick.evaluate("(el)=>getComputedStyle(el).overflowX") not in ("auto","scroll"):
        raise AssertionError(f"{label}: assistant quick actions should scroll horizontally")
    if quick.locator(".btn").count() < 3:
        raise AssertionError(f"{label}: assistant quick actions missing")

    if width <= 345:
        extra=page.locator(".assistant-status-extra")
        if extra.count() and extra.evaluate("(el)=>getComputedStyle(el).display") != "none":
            raise AssertionError(f"{label}: extra assistant status should hide on very small mobile")

    page.locator(".assistant-close").click()
    page.locator(".assistant-button").wait_for(state="visible",timeout=2000)

    # Generic modal must inherit the latest premium mobile treatment.
    page.evaluate("""() => {
      const modal=document.getElementById('article-modal');
      document.getElementById('article-modal-title').textContent='Analyse du match';
      document.getElementById('article-modal-content').innerHTML='<p>Lecture rapide du contexte et du pronostic.</p><p><strong>Confiance : 82%</strong></p>';
      const img=document.getElementById('article-modal-image');
      img.style.display='none';
      modal.style.display='flex';
    }""")
    modal=page.locator("#article-modal")
    content=modal.locator(".modal-content")
    content.wait_for(state="visible",timeout=3000)
    page.wait_for_timeout(300)

    box=content.bounding_box()
    if not box or abs((box["y"]+box["height"])-height) > 4:
        raise AssertionError(f"{label}: modal should be bottom-sheet anchored {box}")

    family=content.locator("h3").evaluate("(el)=>getComputedStyle(el).fontFamily")
    if "Montserrat" not in family:
        raise AssertionError(f"{label}: popup title typography not harmonized: {family}")

    cta=page.locator("#article-modal-link")
    decoration=cta.evaluate("(el)=>getComputedStyle(el).textDecorationLine")
    if decoration != "none":
        raise AssertionError(f"{label}: mobile popup CTA must not be underlined: {decoration}")

    if not page.locator("body").evaluate("(el)=>el.classList.contains('mx-overlay-open')"):
        raise AssertionError(f"{label}: body scroll lock class missing while modal is open")
    overflow=page.locator("body").evaluate("(el)=>getComputedStyle(el).overflow")
    if overflow != "hidden":
        raise AssertionError(f"{label}: page should lock scroll behind modal, got {overflow}")

    launcher=page.locator(".assistant-button")
    if launcher.evaluate("(el)=>getComputedStyle(el).pointerEvents") != "none":
        raise AssertionError(f"{label}: assistant launcher must not intercept modal taps")

    page.screenshot(path=str(OUT/f"mobile-parity-{width}.png"),full_page=True)
    modal.locator(".close").click()
    page.wait_for_timeout(120)
    if modal.is_visible():
        raise AssertionError(f"{label}: modal close failed")
    if page.locator("body").evaluate("(el)=>el.classList.contains('mx-overlay-open')"):
        raise AssertionError(f"{label}: body lock was not released after closing modal")

    # iOS guide keeps the same bottom-sheet treatment.
    page.evaluate("document.getElementById('ios-guide-popup').style.display='flex'")
    guide=page.locator("#ios-guide-popup .ios-guide-content")
    guide.wait_for(state="visible",timeout=2000)
    page.wait_for_timeout(300)
    gbox=guide.bounding_box()
    if not gbox or abs((gbox["y"]+gbox["height"])-height) > 4:
        raise AssertionError(f"{label}: iOS guide should be bottom-sheet anchored {gbox}")
    page.locator("#close-ios-guide").click()

    assert_no_overflow(page,label)
    print(f"PASS {label}: {width}x{height}, latest assistant/popup mobile parity OK")
    ctx.close()

def verify_live_mobile_css(browser):
    ctx=browser.new_context()
    css=ctx.request.get("http://127.0.0.1:8000/assets/css/live-premium.css").text()
    html=ctx.request.get("http://127.0.0.1:8000/live.html").text()
    if "Latest premium UI parity — mobile" not in css:
        raise AssertionError("LIVE mobile parity CSS missing")
    if "20261013-mobile-parity1" not in html:
        raise AssertionError("LIVE premium CSS cache-bust missing")
    print("PASS LIVE mobile parity CSS/cache version")
    ctx.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_mobile(browser,390,844,"mobile")
    run_mobile(browser,320,720,"small-mobile")
    verify_live_mobile_css(browser)
    browser.close()
