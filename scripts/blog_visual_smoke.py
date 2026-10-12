#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/blog-responsive")
OUT.mkdir(parents=True, exist_ok=True)

ARTICLES = [
    {"title":"Actualité football : les nouvelles du jour","date":"2026-10-11","active":True,"keywords":"actualité news football","meta_description":"Les informations importantes du football aujourd'hui.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Actualités football."},
    {"title":"Analyse xG : comprendre les occasions","date":"2026-10-10","active":True,"keywords":"analyse xG statistique uniquemarkerzz","meta_description":"Une analyse statistique des occasions et des xG. uniquemarkerzz","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Analyse xG détaillée."},
    {"title":"5 conseils pour mieux gérer sa bankroll","date":"2026-10-09","active":True,"keywords":"conseil bankroll gestion mise","meta_description":"Conseils pratiques pour mieux gérer son budget.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Conseils bankroll."},
    {"title":"Les tendances de la saison","date":"2026-10-08","active":True,"keywords":"tendance saison forme","meta_description":"Les tendances à suivre cette saison.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Tendances de saison."},
    {"title":"Calendrier des grands matchs du week-end","date":"2026-10-07","active":True,"keywords":"calendrier programmation horaire","meta_description":"Le programme des principales rencontres.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Calendrier football."},
    {"title":"Mercato : les transferts à suivre","date":"2026-10-06","active":True,"keywords":"mercato transfert signature","meta_description":"Les mouvements importants du mercato.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Transferts football."},
    {"title":"Compétitions : Ligue des champions","date":"2026-10-05","active":True,"keywords":"compétition coupe tournoi","meta_description":"Décryptage des grandes compétitions.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Compétitions football."},
    {"title":"Règlement VAR : ce qu'il faut savoir","date":"2026-10-04","active":True,"keywords":"règlement règle VAR arbitrage","meta_description":"Les règles essentielles autour de la VAR.","image_url":"assets/images/blog-premium/hero-blog.webp","content":"Règlement et arbitrage."}
]

def no_overflow(page, label):
    values = page.evaluate("() => ({viewport: innerWidth, doc: document.documentElement.scrollWidth, body: document.body.scrollWidth})")
    maximum = max(values["doc"], values["body"])
    if maximum > values["viewport"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {maximum}px > {values['viewport']}px")

def install_routes(page):
    page.route("**/articles.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(ARTICLES)))
    page.route("**/conseils.json*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/data.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"matches":[],"blog":[]})))

def assert_mobile_density(page, width, label):
    if width > 700:
        return

    hero_h = page.locator(".mx-blog-hero").evaluate("(el) => el.getBoundingClientRect().height")
    if hero_h > 115:
        raise AssertionError(f"{label}: blog hero too tall ({hero_h}px)")

    hero_desc = page.locator(".mx-blog-copy p")
    if hero_desc.count() and hero_desc.is_visible():
        raise AssertionError(f"{label}: secondary hero description should be hidden on mobile")

    pillars = page.locator(".mx-blog-hero-pillars")
    if pillars.count() and pillars.is_visible():
        raise AssertionError(f"{label}: redundant hero pillars should be hidden on mobile")

    explorer_h = page.locator(".mx-blog-explorer").evaluate("(el) => el.getBoundingClientRect().height")
    if explorer_h > 82:
        raise AssertionError(f"{label}: blog explorer too tall ({explorer_h}px)")

    first_card = page.locator(".blog-premium-card").first
    first_top = first_card.evaluate("(el) => el.getBoundingClientRect().top")
    max_top = 325 if width >= 390 else 318
    if first_top > max_top:
        raise AssertionError(
            f"{label}: first article starts too low ({first_top}px > {max_top}px); "
            "mobile content must appear before excessive scrolling"
        )

    excerpt = first_card.locator(".blog-card-body p")
    if excerpt.count() and excerpt.is_visible():
        raise AssertionError(f"{label}: article excerpt should stay hidden until the user opens the article")

    nav = page.locator("#bottom-nav")
    nav.wait_for(state="visible", timeout=10000)
    items = page.locator("#bottom-nav .bottom-nav-item")
    if items.count() != 5:
        raise AssertionError(f"{label}: expected 5 bottom-nav items, got {items.count()}")

    widths = items.evaluate_all("(nodes) => nodes.map(n => n.getBoundingClientRect().width)")
    if max(widths) - min(widths) > 1.5:
        raise AssertionError(f"{label}: bottom-nav cells are not equal: {widths}")

def run_view(browser, width, height, label):
    context = browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page = context.new_page()
    install_routes(page)
    page_errors=[]
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto("http://127.0.0.1:8000/blog.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".blog-premium-card").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(900)

    no_overflow(page, label)
    assert_mobile_density(page, width, label)

    cards = page.locator(".blog-premium-card").count()
    if cards < len(ARTICLES):
        raise AssertionError(f"{label}: expected at least {len(ARTICLES)} cards, got {cards}")

    required = [
      "icon-blog-news.webp","icon-blog-analysis.webp","icon-blog-tips.webp",
      "icon-blog-trending.webp","icon-blog-schedule.webp","icon-blog-transfers.webp",
      "icon-blog-competitions.webp","icon-blog-rules.webp","icon-blog-search.webp","icon-blog-category.webp"
    ]
    image_health = page.locator("img[src*='blog-premium/']").evaluate_all("""imgs => imgs.map(img => ({
      src: img.getAttribute('src'), ok: img.complete && img.naturalWidth > 0,
      width: img.naturalWidth, height: img.naturalHeight
    }))""")
    broken=[item for item in image_health if not item["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken blog assets {broken}")
    sources=[item["src"] for item in image_health]
    for asset in required:
        if not any(asset in src for src in sources):
            raise AssertionError(f"{label}: missing rendered asset {asset}")

    hero_bg = page.locator(".mx-blog-hero-bg").evaluate("(el) => getComputedStyle(el).backgroundImage")
    if "hero-blog.webp" not in hero_bg:
        raise AssertionError(f"{label}: generated hero background not active")

    transfer = page.get_by_role("button", name="Transferts", exact=True)
    transfer.click()
    page.wait_for_timeout(100)
    transfer_cards = page.locator(".blog-premium-card")
    if transfer_cards.count() < 1:
        raise AssertionError(f"{label}: transfer filter returned no article")
    categories = transfer_cards.evaluate_all("(nodes) => nodes.map(n => n.dataset.blogCategory)")
    if any(category != "Transferts" for category in categories):
        raise AssertionError(f"{label}: transfer filter leaked categories {categories}")

    page.get_by_role("button", name="Tous", exact=True).click()
    search=page.locator("#blog-search")
    search.fill("uniquemarkerzz")
    page.wait_for_timeout(100)
    if page.locator(".blog-premium-card").count() != 1:
        raise AssertionError(f"{label}: search filter failed")
    search.fill("")
    page.wait_for_timeout(100)

    page.locator(".blog-premium-card").first.click()
    page.locator("#article-modal").wait_for(state="visible", timeout=5000)
    if not page.locator("#article-modal-title").inner_text().strip():
        raise AssertionError(f"{label}: article modal title empty")
    page.locator("#article-modal .close").click()
    page.locator("#article-modal").wait_for(state="hidden", timeout=5000)

    no_overflow(page, label)
    page.screenshot(path=str(OUT/f"blog-{width}.png"), full_page=True)

    if page_errors:
        raise AssertionError(f"{label}: page errors {page_errors}")

    print(f"PASS {label}: viewport={width}x{height}, cards={cards}, content-first density/filters/search/modal/assets/overflow OK")
    context.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,1024,900,"desktop")
    run_view(browser,768,1024,"tablet")
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
