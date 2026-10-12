#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/infos-responsive")
OUT.mkdir(parents=True, exist_ok=True)

INFOS = [
  {
    "title":"Football : l'info principale du jour",
    "date":"2026-10-12T09:15:00Z",
    "active":True,
    "category":"Football",
    "content":"Le point essentiel à retenir aujourd'hui sur le football.",
    "image_url":None
  }
]

FOOTNEWS = [
  {"title":"Analyse européenne du soir","summary":"Une grande soirée européenne se prépare.","published":"2026-10-12T08:00:00Z","category":"Champions League","image":None,"link":"https://example.com/champions"},
  {"title":"Mercato uniquemarkerzz : un transfert se précise","summary":"Le marché des transferts continue de bouger.","published":"2026-10-12T07:30:00Z","category":"Mercato","image":None,"link":"https://example.com/mercato"},
  {"title":"Point blessures avant le week-end","summary":"Plusieurs joueurs sont suivis médicalement.","published":"2026-10-12T07:00:00Z","category":"Blessures","image":None,"link":"https://example.com/injuries"},
  {"title":"Angleterre : les enjeux de la prochaine journée","summary":"Les clubs anglais préparent leur prochain rendez-vous.","published":"2026-10-12T06:30:00Z","category":"Premier League","image":None,"link":"https://example.com/pl"},
  {"title":"France : les tendances du championnat","summary":"Les équipes françaises se préparent pour la suite.","published":"2026-10-12T06:00:00Z","category":"Ligue 1","image":None,"link":"https://example.com/l1"},
  {"title":"Espagne : une journée décisive","summary":"La course en Espagne reste serrée.","published":"2026-10-12T05:30:00Z","category":"Liga","image":None,"link":"https://example.com/liga"},
  {"title":"Italie : les affiches à suivre","summary":"Les clubs italiens jouent gros cette semaine.","published":"2026-10-12T05:00:00Z","category":"Serie A","image":None,"link":"https://example.com/seriea"}
]

def no_overflow(page, label):
    values = page.evaluate("() => ({viewport: innerWidth, doc: document.documentElement.scrollWidth, body: document.body.scrollWidth})")
    maximum = max(values["doc"], values["body"])
    if maximum > values["viewport"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {maximum}px > {values['viewport']}px")

def install_routes(page):
    page.route("**/infos.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(INFOS)))
    page.route("**/footnews.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(FOOTNEWS)))
    page.route("**/bookmakers.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/bonus.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/articles.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/conseils.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/data.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"matches":[]})))

def assert_mobile_density(page, width, label):
    if width > 700:
        return

    hero_h = page.locator(".mx-infos-hero").evaluate("(el) => el.getBoundingClientRect().height")
    if hero_h > 142:
        raise AssertionError(f"{label}: Infos hero too tall ({hero_h}px)")

    if page.locator(".mx-infos-copy p").is_visible():
        raise AssertionError(f"{label}: secondary hero description should be hidden")
    if page.locator(".mx-infos-pillars").is_visible():
        raise AssertionError(f"{label}: redundant hero pillars should be hidden")

    explorer_h = page.locator(".mx-infos-explorer").evaluate("(el) => el.getBoundingClientRect().height")
    if explorer_h > 82:
        raise AssertionError(f"{label}: Infos explorer too tall ({explorer_h}px)")

    first_card = page.locator(".news-premium-card").first
    first_top = first_card.evaluate("(el) => el.getBoundingClientRect().top")
    max_top = 345 if width >= 390 else 335
    if first_top > max_top:
        raise AssertionError(
            f"{label}: first news card starts too low ({first_top}px > {max_top}px); "
            "primary content must appear quickly"
        )

    excerpt = first_card.locator(".news-premium-body p")
    if excerpt.count() and excerpt.is_visible():
        raise AssertionError(f"{label}: news summary should remain hidden until opening the news")

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

    page.goto("http://127.0.0.1:8000/infos.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".news-premium-card").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(1000)

    no_overflow(page, label)
    assert_mobile_density(page, width, label)

    cards = page.locator(".news-premium-card")
    if cards.count() != len(INFOS) + len(FOOTNEWS):
        raise AssertionError(f"{label}: expected {len(INFOS)+len(FOOTNEWS)} cards, got {cards.count()}")

    if page.locator(".news-premium-card.featured").count() != 1:
        raise AssertionError(f"{label}: featured news card missing")

    required = [
      "icon-infos-latest.webp","icon-infos-football.webp","icon-infos-champions.webp",
      "icon-infos-mercato.webp","icon-infos-injuries.webp","icon-infos-premierleague.webp",
      "icon-infos-ligue1.webp","icon-infos-liga.webp","icon-infos-seriea.webp","icon-infos-clock.webp"
    ]
    health = page.locator("img[src*='infos-premium/']").evaluate_all("""imgs => imgs.map(img => ({
      src: img.getAttribute('src'), ok: img.complete && img.naturalWidth > 0,
      width: img.naturalWidth, height: img.naturalHeight
    }))""")
    broken=[item for item in health if not item["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken premium assets {broken}")
    sources=[item["src"] for item in health]
    for asset in required:
        if not any(asset in src for src in sources):
            raise AssertionError(f"{label}: missing rendered asset {asset}")

    hero_bg = page.locator(".mx-infos-hero-bg").evaluate("(el)=>getComputedStyle(el).backgroundImage")
    if "hero-infos.webp" not in hero_bg:
        raise AssertionError(f"{label}: generated hero background not active")

    page.get_by_role("button", name="Mercato", exact=True).click()
    page.wait_for_timeout(120)
    mercato_cards = page.locator(".news-premium-card")
    if mercato_cards.count() != 1:
        raise AssertionError(f"{label}: Mercato filter expected 1 card, got {mercato_cards.count()}")
    if mercato_cards.first.get_attribute("data-news-category") != "Mercato":
        raise AssertionError(f"{label}: Mercato filter returned wrong category")

    page.get_by_role("button", name="Tous", exact=True).click()
    search=page.locator("#infos-search")
    search.fill("uniquemarkerzz")
    page.wait_for_timeout(120)
    if page.locator(".news-premium-card").count() != 1:
        raise AssertionError(f"{label}: search filter failed")
    search.fill("")
    page.wait_for_timeout(120)

    page.locator(".news-premium-card").first.click()
    page.locator("#news-modal").wait_for(state="visible", timeout=5000)
    if not page.locator("#news-modal-title").inner_text().strip():
        raise AssertionError(f"{label}: news modal title is empty")
    page.locator("#news-modal .close").click()
    page.locator("#news-modal").wait_for(state="hidden", timeout=5000)

    no_overflow(page, label)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(250)
    page.screenshot(path=str(OUT/f"infos-{width}.png"), full_page=True)

    if page_errors:
        raise AssertionError(f"{label}: page errors {page_errors}")

    print(f"PASS {label}: {width}x{height}, content-first/cards/assets/filter/search/modal/overflow OK")
    context.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,1024,900,"desktop")
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
