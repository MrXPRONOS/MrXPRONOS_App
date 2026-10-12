#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/public-pages-audit")
OUT.mkdir(parents=True, exist_ok=True)

ARTICLE = {
  "title":"Analyse premium de test",
  "slug":"analyse-premium-test",
  "date":"2026-10-12",
  "active":True,
  "meta_description":"Article de test pour le smoke test.",
  "content":"## Introduction\nContenu de test.",
  "image_url":"assets/images/blog-premium/hero-blog.webp"
}
CONSEIL = {
  "title":"Conseil premium de test",
  "slug":"conseil-premium-test",
  "date":"2026-10-12",
  "active":True,
  "excerpt":"Conseil de test.",
  "content":"## Méthode\nContenu de conseil.",
  "image_url":"assets/images/conseils-premium/hero-conseils.webp"
}

STANDARD = [
  ("index.html", "Accueil"),
  ("pronos.html", "Pronostics"),
  ("historique.html", "Historique"),
  ("blog.html", "Blog"),
  ("conseils.html", "Conseils"),
  ("conseil.html?slug=conseil-premium-test", "Conseils"),
  ("article.html?slug=analyse-premium-test", "Blog"),
  ("infos.html", "Infos sport"),
  ("bonus.html", "Bonus & Promo"),
  ("contact.html", "Contact"),
  ("bookmakers.html", "Bonus & Promo"),
]

def install_routes(page):
    page.route("**/articles.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps([ARTICLE])))
    page.route("**/conseils.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps([CONSEIL])))
    page.route("**/infos.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/footnews.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/bonus.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/bookmakers.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/data.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"matches":[],"articles":[ARTICLE],"conseils":[CONSEIL]})))

def no_overflow(page, label):
    values = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(values["d"], values["b"]) > values["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {values}")

def check_standard(browser, path, active_label, width, height):
    label=f"{path}@{width}"
    context=browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page=context.new_page()
    install_routes(page)
    errors=[]
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"http://127.0.0.1:8000/{path}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(900)
    no_overflow(page,label)

    header=page.locator(".mx-site-header")
    if header.count()!=1:
        raise AssertionError(f"{label}: missing standard premium header")
    h=round(header.bounding_box()["height"])
    expected=76 if width>700 else 65
    if abs(h-expected)>1:
        raise AssertionError(f"{label}: header height {h}, expected {expected}")

    logo=page.locator(".mx-site-header .logo img")
    if logo.count()!=1 or not logo.evaluate("(i)=>i.complete && i.naturalWidth>0"):
        raise AssertionError(f"{label}: official header logo missing/broken")

    nav=page.locator(".mx-desktop-nav")
    if nav.count()!=1:
        raise AssertionError(f"{label}: desktop nav missing")

    active=page.locator(".mx-desktop-nav a.active")
    if active.count()!=1:
        raise AssertionError(f"{label}: expected exactly one active nav item")
    if active.inner_text().strip()!=active_label:
        raise AssertionError(f"{label}: active nav {active.inner_text()!r}, expected {active_label!r}")

    promo=page.locator(".mx-code-button")
    if promo.count()!=1:
        raise AssertionError(f"{label}: promo button missing")

    if width<=700:
        logo_box=page.locator(".mx-site-header .logo a").bounding_box()
        promo_box=promo.bounding_box()
        if not logo_box or not promo_box:
            raise AssertionError(f"{label}: missing mobile header geometry")
        if logo_box["x"] + logo_box["width"] > promo_box["x"] + 2:
            raise AssertionError(f"{label}: logo overlaps promo button")

    if width<=900:
        # menu.js injects the burger after DOM load.
        burger=page.locator("#burger-btn")
        burger.wait_for(state="visible", timeout=5000)
        if not burger.is_visible():
            raise AssertionError(f"{label}: burger not visible on mobile")
    else:
        if not nav.is_visible():
            raise AssertionError(f"{label}: desktop nav not visible")

    if errors:
        # Ignore harmless external failures; real JS page errors are still surfaced.
        meaningful=[e for e in errors if "ResizeObserver" not in e]
        if meaningful:
            raise AssertionError(f"{label}: page errors {meaningful}")

    context.close()
    print("PASS",label)

def check_live(browser,width,height):
    label=f"live.html@{width}"
    context=browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page=context.new_page()
    page.route("**/live*", lambda route: route.continue_())
    page.goto("http://127.0.0.1:8000/live.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".mx-live-header").wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(1200)
    no_overflow(page,label)
    h=round(page.locator(".mx-live-header__inner").bounding_box()["height"])
    expected=76 if width>900 else 65
    if abs(h-expected)>1:
        raise AssertionError(f"{label}: live header inner height {h}, expected {expected}")
    logo=page.locator(".mx-live-brand img")
    if logo.count()!=1 or not logo.evaluate("(i)=>i.complete && i.naturalWidth>0"):
        raise AssertionError(f"{label}: live logo missing/broken")
    if width<=900:
        if page.locator(".mx-mobile-only").count()<2:
            raise AssertionError(f"{label}: live mobile controls missing")
    else:
        if not page.locator(".mx-live-desktop-nav").is_visible():
            raise AssertionError(f"{label}: live desktop nav missing")
    context.close()
    print("PASS",label)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width,height in [(1024,900),(390,844),(320,720)]:
        for path,label in STANDARD:
            check_standard(browser,path,label,width,height)
        check_live(browser,width,height)
    browser.close()
