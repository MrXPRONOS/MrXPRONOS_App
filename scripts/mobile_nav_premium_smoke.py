#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/mobile-nav-premium")
OUT.mkdir(parents=True, exist_ok=True)

DATA = {
  "generated_at":"2026-10-12T18:00:00Z",
  "matches":[]
}

def routes(page):
    empty="[]"
    page.route("**/data.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(DATA)))
    for name in ["articles.json","conseils.json","infos.json","footnews.json","bonus.json","bookmakers.json","testimonials.json"]:
        page.route(f"**/{name}*", lambda r, _req=None, body=empty: r.fulfill(status=200, content_type="application/json", body=body))

def no_overflow(page,label):
    dims=page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(dims["d"],dims["b"]) > dims["v"] + 1:
        raise AssertionError(f"{label}: overflow {dims}")

def image_health(locator,label):
    items=locator.evaluate_all("""imgs => imgs.map(i => ({
      src:i.getAttribute('src'), ok:i.complete && i.naturalWidth>0,
      w:i.naturalWidth, h:i.naturalHeight
    }))""")
    broken=[x for x in items if not x["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken icons {broken}")
    return items

def assert_bottom(page, expected, label):
    nav=page.locator("#bottom-nav")
    nav.wait_for(state="visible",timeout=10000)
    items=nav.locator(".bottom-nav-item")
    if items.count()!=5:
        raise AssertionError(f"{label}: expected 5 bottom items, got {items.count()}")
    labels=items.locator(".bottom-nav-label").all_inner_texts()
    if labels!=["Accueil","Pronostics","LIVE","Bonus","Menu"]:
        raise AssertionError(f"{label}: bad bottom labels {labels}")
    active=nav.locator(".bottom-nav-item.active")
    if active.count()!=1:
        raise AssertionError(f"{label}: expected one active bottom item, got {active.count()}")
    if active.locator(".bottom-nav-label").inner_text().strip()!=expected:
        raise AssertionError(f"{label}: active bottom is {active.locator('.bottom-nav-label').inner_text()!r}, expected {expected!r}")

    imgs=image_health(nav.locator("img.bottom-nav-icon"),label+" bottom")
    if len(imgs)!=5 or not all("assets/images/mobile-premium/" in x["src"] for x in imgs):
        raise AssertionError(f"{label}: bottom icons are not the generated local assets")

    boxes=items.evaluate_all("els => els.map(e => { const r=e.getBoundingClientRect(); return {w:r.width,h:r.height}; })")
    if any(b["h"] < 48 or b["w"] < 48 for b in boxes):
        raise AssertionError(f"{label}: touch target below 48px {boxes}")

    # Five equal 20% cells.
    widths=[round(b["w"],1) for b in boxes]
    if max(widths)-min(widths) > 1.5:
        raise AssertionError(f"{label}: bottom cells are not equal width {widths}")

    # Compact bar, not the oversized version from the previous screenshot.
    inner=page.locator("#bottom-nav .inner").bounding_box()
    if not inner or inner["height"] > 70 or inner["height"] < 64:
        raise AssertionError(f"{label}: unexpected bottom bar inner height {inner}")

    # Optical sizing: Pronostics/LIVE slightly larger, Menu deliberately smaller.
    sizes=page.locator("#bottom-nav .bottom-nav-icon").evaluate_all(
      "imgs => imgs.map(i => { const r=i.getBoundingClientRect(); return {w:r.width,h:r.height}; })"
    )
    expected=[31,32,32,31,26] if page.viewport_size["width"] <= 340 else [31,34,34,31,28]
    for index,(box,target) in enumerate(zip(sizes,expected)):
        if abs(box["w"]-target) > 1.5 or abs(box["h"]-target) > 1.5:
            raise AssertionError(f"{label}: icon {index} size {box}, expected about {target}px")

    # LIVE: no extra CSS circle/background around the already self-contained icon.
    live_wrap=page.locator("#bottom-nav .bottom-nav-item.live .bottom-nav-icon-wrap").evaluate(
      "(el) => ({border:getComputedStyle(el).borderStyle,bg:getComputedStyle(el).backgroundImage,shadow:getComputedStyle(el).boxShadow})"
    )
    if live_wrap["border"] != "none" or live_wrap["bg"] != "none" or live_wrap["shadow"] != "none":
        raise AssertionError(f"{label}: LIVE still has double wrapper styling {live_wrap}")

def open_menu(page, label, from_bottom=True):
    trigger=page.locator("#bottom-nav-menu" if from_bottom else "#burger-btn")
    trigger.wait_for(state="visible",timeout=10000)
    trigger.click()
    overlay=page.locator("#burger-overlay")
    overlay.wait_for(state="visible",timeout=5000)
    if "open" not in (overlay.get_attribute("class") or ""):
        raise AssertionError(f"{label}: drawer did not open")

    entries=overlay.locator(".burger-menu-item")
    if entries.count()!=9:
        raise AssertionError(f"{label}: expected 9 drawer entries, got {entries.count()}")

    imgs=image_health(overlay.locator("img.menu-icon-img"),label+" drawer")
    if len(imgs)!=9:
        raise AssertionError(f"{label}: expected 9 generated drawer icons")

    if page.locator("link[href*='font-awesome'],link[href*='fontawesome']").count():
        raise AssertionError(f"{label}: Font Awesome dependency still injected")
    return overlay

def close_menu(page):
    page.locator(".burger-close").click()
    page.locator("#burger-overlay").wait_for(state="hidden",timeout=5000)

def check_page(browser,path,width,height,expected_bottom,expected_drawer=None,screen=False):
    label=f"{path}@{width}"
    ctx=browser.new_context(viewport={"width":width,"height":height},service_workers="block")
    page=ctx.new_page()
    routes(page)
    page.goto(f"http://127.0.0.1:8000/{path}",wait_until="domcontentloaded",timeout=60000)
    page.wait_for_timeout(850)
    assert_bottom(page,expected_bottom,label)
    no_overflow(page,label)

    overlay=open_menu(page,label,from_bottom=True)
    if expected_drawer:
        active=overlay.locator(".burger-menu-item.active .menu-label")
        if active.count()!=1 or active.inner_text().strip()!=expected_drawer:
            got=active.inner_text().strip() if active.count() else ""
            raise AssertionError(f"{label}: active drawer is {got!r}, expected {expected_drawer!r}")
    close_menu(page)

    if path=="index.html":
        burger=page.locator("#burger-btn")
        burger.wait_for(state="visible",timeout=5000)
        bimg=image_health(burger.locator("img.mx-burger-icon"),label+" burger")
        if len(bimg)!=1 or "icon-menu.webp" not in bimg[0]["src"]:
            raise AssertionError(f"{label}: generated hamburger icon missing")
        open_menu(page,label,from_bottom=False)
        close_menu(page)

    if path=="live.html":
        if page.locator("#burger-btn").count()!=0:
            raise AssertionError(f"{label}: Live should keep its dedicated header controls without injected burger")

    if screen:
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(150)
        page.screenshot(path=str(OUT/f"{path.split('?')[0].replace('.html','')}-{width}.png"),full_page=False)

    ctx.close()
    print("PASS",label)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)

    # Standard 390px states
    check_page(browser,"index.html",390,844,"Accueil","Accueil",True)
    check_page(browser,"pronos.html",390,844,"Pronostics","Pronostics")
    check_page(browser,"bonus.html",390,844,"Bonus","Bonus & Promo")
    check_page(browser,"historique.html",390,844,"Menu","Historique",True)
    check_page(browser,"contact.html",390,844,"Menu","Contact")
    # Live intentionally keeps its own functional four-tab mobile navigation.
    ctx=browser.new_context(viewport={"width":390,"height":844},service_workers="block")
    page=ctx.new_page()
    page.goto("http://127.0.0.1:8000/live.html",wait_until="domcontentloaded",timeout=60000)
    page.locator(".mx-mobile-tabs").wait_for(state="visible",timeout=60000)
    page.wait_for_timeout(700)
    if page.locator("#bottom-nav").count()!=0:
        raise AssertionError("live.html@390: duplicate global bottom navigation should not be injected")
    if page.locator(".mx-mobile-tab").count()!=4:
        raise AssertionError("live.html@390: dedicated Live mobile tabs missing")
    no_overflow(page,"live.html@390")
    page.screenshot(path=str(OUT/"live-390.png"),full_page=False)
    ctx.close()
    print("PASS live.html@390 dedicated tabs")

    # Narrow phone stress-test
    check_page(browser,"index.html",320,720,"Accueil","Accueil",True)
    check_page(browser,"historique.html",320,720,"Menu","Historique",True)

    browser.close()
