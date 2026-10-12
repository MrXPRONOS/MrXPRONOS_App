#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/conseils-responsive")
OUT.mkdir(parents=True, exist_ok=True)

CONSEILS = [
    {
      "title":"Gérer sa bankroll sans se mettre en difficulté",
      "slug":"gerer-bankroll",
      "date":"2026-10-11",
      "active":True,
      "keywords":"bankroll budget mise",
      "excerpt":"Une méthode simple pour définir vos mises et protéger votre capital.",
      "image_url":"assets/images/conseils-premium/hero-conseils.webp",
      "content":"Guide de gestion de bankroll."
    },
    {
      "title":"Comprendre la value dans une cote",
      "slug":"comprendre-value",
      "date":"2026-10-10",
      "active":True,
      "keywords":"cote value valeur",
      "excerpt":"Apprendre à comparer probabilité estimée et cote proposée.",
      "image_url":"assets/images/conseils-premium/hero-conseils.webp",
      "content":"Guide value."
    },
    {
      "title":"Les erreurs qui détruisent une session",
      "slug":"erreurs-tilt",
      "date":"2026-10-09",
      "active":True,
      "keywords":"erreur piège danger tilt",
      "excerpt":"Les pièges à reconnaître avant qu'ils ne coûtent cher.",
      "image_url":"assets/images/conseils-premium/hero-conseils.webp",
      "content":"Guide erreurs."
    },
    {
      "title":"Discipline et limites : rester responsable",
      "slug":"discipline-limites",
      "date":"2026-10-08",
      "active":True,
      "keywords":"responsable discipline limite",
      "excerpt":"Construire une routine et des limites cohérentes.",
      "image_url":"assets/images/conseils-premium/hero-conseils.webp",
      "content":"Guide discipline."
    },
    {
      "title":"Analyser un match avec les statistiques",
      "slug":"analyse-match",
      "date":"2026-10-07",
      "active":True,
      "keywords":"analyse match statistique h2h xg",
      "excerpt":"Utiliser forme, xG, H2H et contexte avec méthode.",
      "image_url":"assets/images/conseils-premium/hero-conseils.webp",
      "content":"Guide analyse."
    },
    {
      "title":"Construire sa méthode étape par étape",
      "slug":"methode-guide",
      "date":"2026-10-06",
      "active":True,
      "keywords":"guide méthode apprentissage",
      "excerpt":"Un cadre progressif pour structurer votre approche.",
      "image_url":"assets/images/conseils-premium/hero-conseils.webp",
      "content":"Guide général."
    }
]

def no_overflow(page, label):
    values = page.evaluate("() => ({viewport: innerWidth, doc: document.documentElement.scrollWidth, body: document.body.scrollWidth})")
    maximum = max(values["doc"], values["body"])
    if maximum > values["viewport"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {maximum}px > {values['viewport']}px")

def install_routes(page):
    page.route("**/conseils.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(CONSEILS)))
    page.route("**/articles.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/data.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"matches":[],"conseils":[]})))

def assert_mobile_density(page, width, label):
    if width > 700:
        return

    hero_h = page.locator(".mx-conseils-hero").evaluate("(el) => el.getBoundingClientRect().height")
    if hero_h > 113:
        raise AssertionError(f"{label}: Conseils hero too tall ({hero_h}px)")

    hero_desc = page.locator(".mx-conseils-copy p")
    if hero_desc.count() and hero_desc.is_visible():
        raise AssertionError(f"{label}: secondary hero description should be hidden")

    pillars = page.locator(".mx-conseils-pillars")
    if pillars.count() and pillars.is_visible():
        raise AssertionError(f"{label}: redundant hero pillars should be hidden")

    first_card = page.locator(".conseil-premium-card").first
    first_top = first_card.evaluate("(el) => el.getBoundingClientRect().top")
    max_top = 280 if width >= 390 else 272
    if first_top > max_top:
        raise AssertionError(
            f"{label}: first guide starts too low ({first_top}px > {max_top}px); "
            "primary content must appear quickly"
        )

    excerpt = first_card.locator(".conseil-card-body p")
    if excerpt.count() and excerpt.is_visible():
        raise AssertionError(f"{label}: guide excerpt should remain hidden until opening the guide")

    nav = page.locator("#bottom-nav")
    nav.wait_for(state="visible", timeout=10000)
    items = page.locator("#bottom-nav .bottom-nav-item")
    if items.count() != 5:
        raise AssertionError(f"{label}: expected 5 bottom-nav items, got {items.count()}")

def run_view(browser, width, height, label):
    context = browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page = context.new_page()
    install_routes(page)
    page_errors=[]
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto("http://127.0.0.1:8000/conseils.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".conseil-premium-card").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(900)

    no_overflow(page, label)
    assert_mobile_density(page, width, label)

    cards = page.locator(".conseil-premium-card")
    if cards.count() != len(CONSEILS):
        raise AssertionError(f"{label}: expected {len(CONSEILS)} cards, got {cards.count()}")

    expected_types = {"Gestion","Value","Pièges","Discipline","Analyse","Guide"}
    rendered_types = set(cards.evaluate_all("(nodes) => nodes.map(n => n.dataset.conseilType)"))
    if rendered_types != expected_types:
        raise AssertionError(f"{label}: unexpected advice types {rendered_types}")

    required = [
      "icon-conseils-guide.webp",
      "icon-conseils-bankroll.webp",
      "icon-conseils-value.webp",
      "icon-conseils-danger.webp",
      "icon-conseils-discipline.webp",
      "icon-conseils-analysis.webp",
      "icon-conseils-academy.webp"
    ]
    health = page.locator("img[src*='conseils-premium/']").evaluate_all("""imgs => imgs.map(img => ({
      src: img.getAttribute('src'), ok: img.complete && img.naturalWidth > 0,
      width: img.naturalWidth, height: img.naturalHeight
    }))""")
    broken = [item for item in health if not item["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken premium assets {broken}")

    sources = [item["src"] for item in health]
    for asset in required:
        if not any(asset in src for src in sources):
            raise AssertionError(f"{label}: missing rendered asset {asset}")

    hero_bg = page.locator(".mx-conseils-hero-bg").evaluate("(el) => getComputedStyle(el).backgroundImage")
    if "hero-conseils.webp" not in hero_bg:
        raise AssertionError(f"{label}: generated hero not active")

    first = cards.first
    first.focus()
    page.keyboard.press("Enter")
    page.wait_for_url("**/conseil.html?slug=gerer-bankroll", timeout=5000)

    if page_errors:
        raise AssertionError(f"{label}: page errors {page_errors}")

    # Return to the listing and capture the final layout.
    page.goto("http://127.0.0.1:8000/conseils.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".conseil-premium-card").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(600)
    no_overflow(page, label)
    page.screenshot(path=str(OUT/f"conseils-{width}.png"), full_page=True)

    print(f"PASS {label}: {width}x{height}, content-first/cards/types/assets/navigation/overflow OK")
    context.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,1024,900,"desktop")
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
