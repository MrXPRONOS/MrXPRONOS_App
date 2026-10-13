#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/popup-responsive")
OUT.mkdir(parents=True, exist_ok=True)

def no_horizontal_overflow(page, label):
    size = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(size["d"], size["b"]) > size["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {size}")

def assert_box_in_viewport(box, width, height, label, name):
    if not box:
        raise AssertionError(f"{label}: {name} has no geometry")
    if box["x"] < -1 or box["y"] < -1:
        raise AssertionError(f"{label}: {name} begins outside viewport {box}")
    if box["x"] + box["width"] > width + 2:
        raise AssertionError(f"{label}: {name} overflows horizontally {box}")
    if box["y"] + box["height"] > height + 3:
        raise AssertionError(f"{label}: {name} overflows vertically {box}")

def run_index_case(browser, width, height, label):
    ctx = browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page = ctx.new_page()
    page.goto("http://127.0.0.1:8000/index.html", wait_until="domcontentloaded", timeout=60000)
    page.locator("#article-modal").wait_for(state="attached", timeout=10000)
    page.wait_for_timeout(700)

    no_horizontal_overflow(page,label)

    # Generic content modal.
    page.evaluate("""() => {
      const modal=document.getElementById('article-modal');
      document.getElementById('article-modal-title').textContent='Analyse du match';
      document.getElementById('article-modal-content').innerHTML='<p>Lecture rapide du contexte, des statistiques et du pronostic.</p><p><strong>Confiance : 82%</strong></p>';
      const img=document.getElementById('article-modal-image');
      img.style.display='none';
      modal.style.display='flex';
    }""")
    modal = page.locator("#article-modal")
    content = modal.locator(".modal-content")
    content.wait_for(state="visible",timeout=3000)
    box=content.bounding_box()
    assert_box_in_viewport(box,width,height,label,"article modal")
    if width <= 700:
        if abs((box["y"]+box["height"]) - height) > 4:
            raise AssertionError(f"{label}: mobile article modal is not bottom-sheet anchored {box}")
    else:
        if box["width"] > 725:
            raise AssertionError(f"{label}: desktop/tablet article modal too wide {box}")
    close=modal.locator(".close")
    if close.get_attribute("aria-label") != "Fermer":
        raise AssertionError(f"{label}: article modal close control lacks aria label")
    page.screenshot(path=str(OUT/f"article-modal-{width}.png"),full_page=True)
    close.click()
    page.wait_for_timeout(100)
    if modal.is_visible():
        raise AssertionError(f"{label}: article modal did not close")

    # iOS install helper.
    guide=page.locator("#ios-guide-popup")
    page.evaluate("document.getElementById('ios-guide-popup').style.display='flex'")
    guide.locator(".ios-guide-content").wait_for(state="visible",timeout=3000)
    gbox=guide.locator(".ios-guide-content").bounding_box()
    assert_box_in_viewport(gbox,width,height,label,"iOS guide")
    if guide.get_attribute("role") != "dialog":
        raise AssertionError(f"{label}: iOS guide should expose dialog role")
    if width <= 700 and abs((gbox["y"]+gbox["height"]) - height) > 4:
        raise AssertionError(f"{label}: mobile iOS guide is not bottom-sheet anchored {gbox}")
    steps=guide.locator(".ios-guide-step")
    if steps.count()!=3:
        raise AssertionError(f"{label}: expected 3 install steps")
    page.screenshot(path=str(OUT/f"ios-guide-{width}.png"),full_page=True)
    page.locator("#close-ios-guide").click()
    page.wait_for_timeout(100)
    if guide.is_visible():
        raise AssertionError(f"{label}: iOS guide did not close")

    # Shared toast, truth-based win popup and push prompt geometry.
    page.evaluate("""() => {
      const toast=document.createElement('div');
      toast.id='smoke-toast';
      toast.className='mx-toast mx-toast--success';
      toast.textContent='Code XPVIP copié';
      document.body.appendChild(toast);

      const win=document.getElementById('win-popup');
      win.innerHTML='✅ <b>Résultat validé</b> · Arsenal 2-1 Chelsea · <b>Over 1.5</b>';
      win.classList.add('show');

      const push=document.createElement('div');
      push.id='push-permission';
      push.style.display='block';
      push.innerHTML='<div class="mx-push-card"><div class="mx-push-kicker">MR XPRONOS · ALERTES</div><div class="mx-push-title">Activer les notifications ?</div><div class="mx-push-text">Recevez une alerte lorsqu’un nouveau coupon est disponible.</div><div class="mx-popup-actions"><button class="btn btn-primary">Activer</button><button class="btn btn-secondary">Plus tard</button></div></div>';
      document.body.appendChild(push);
    }""")
    for selector,name in [("#smoke-toast","toast"),("#win-popup","win popup"),("#push-permission","push prompt")]:
        el=page.locator(selector)
        el.wait_for(state="visible",timeout=3000)
        assert_box_in_viewport(el.bounding_box(),width,height,label,name)

    # Ensure dynamic popup code was migrated away from inline styling.
    main_text=ctx.request.get("http://127.0.0.1:8000/assets/js/main.js").text()
    pwa_text=ctx.request.get("http://127.0.0.1:8000/assets/js/pwa.js").text()
    if "mx-push-card" not in main_text or "mx-toast mx-toast--" not in main_text:
        raise AssertionError(f"{label}: main.js premium popup classes missing")
    if "mx-toast mx-toast--update" not in pwa_text or "mx-toast mx-toast--success" not in pwa_text:
        raise AssertionError(f"{label}: pwa.js premium toast classes missing")

    no_horizontal_overflow(page,label)
    print(f"PASS {label}: {width}x{height}, modal/iOS/toast/win/push popup system OK")
    ctx.close()

def run_bookmakers_case(browser):
    ctx=browser.new_context(viewport={"width":390,"height":844},service_workers="block")
    page=ctx.new_page()
    page.goto("http://127.0.0.1:8000/bookmakers.html",wait_until="domcontentloaded",timeout=60000)
    toast=page.locator("#toast")
    toast.wait_for(state="attached",timeout=5000)
    page.evaluate("document.getElementById('toast').classList.add('show')")
    toast.wait_for(state="visible",timeout=2000)
    box=toast.bounding_box()
    assert_box_in_viewport(box,390,844,"bookmakers-mobile","bookmakers toast")
    border=toast.evaluate("(el)=>getComputedStyle(el).borderLeftColor")
    if not border:
        raise AssertionError("bookmakers-mobile: toast accent missing")
    page.screenshot(path=str(OUT/"bookmakers-toast-390.png"),full_page=True)
    print("PASS bookmakers-mobile: premium copy toast OK")
    ctx.close()

def assert_live_sources(browser):
    ctx=browser.new_context()
    html=ctx.request.get("http://127.0.0.1:8000/live.html").text()
    css=ctx.request.get("http://127.0.0.1:8000/assets/css/live-premium.css").text()
    if html.count("mx-live-modal-backdrop") < 2:
        raise AssertionError("LIVE: premium modal backdrops missing")
    if "mx-live-toast" not in html or "PRONO LIVE — premium modal + realtime toast system" not in css:
        raise AssertionError("LIVE: premium popup styling not wired")
    print("PASS LIVE sources: modal/toast premium classes wired")
    ctx.close()

with sync_playwright() as p:
    browser= p.chromium.launch(headless=True)
    run_index_case(browser,1024,900,"desktop")
    run_index_case(browser,768,1024,"tablet")
    run_index_case(browser,390,844,"mobile")
    run_index_case(browser,320,720,"small-mobile")
    run_bookmakers_case(browser)
    assert_live_sources(browser)
    browser.close()
