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

# More than one page of records proves the new progressive pagination.
for i, article in enumerate(ARTICLES):
    article["slug"] = "smoke-article-" + str(i)
    article["category"] = "Compétitions" if i == 6 else "Décryptages"
    if i == 0:
        article["type"] = "match"
for i in range(8, 23):
    ARTICLES.append({
        "slug": "smoke-extra-" + str(i), "title": f"Analyse {i} : Togo vs Ghana",
        "date": "2026-10-03", "type": "match", "league": "Compétition test",
        "active": True, "excerpt": "Résumé vérifiable d'une rencontre.",
        "content": "Aperçu de la rencontre.", "image_url": "assets/images/blog-premium/hero-blog.webp",
    })

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
    if hero_h > 240:
        raise AssertionError(f"{label}: hero too large ({hero_h}px)")
    featured = page.locator("#blog-featured")
    featured.wait_for(state="visible", timeout=10000)
    top = featured.evaluate("(el) => el.getBoundingClientRect().top")
    if top > 360:
        raise AssertionError(f"{label}: main analysis starts too low ({top}px)")
    search = page.locator("#blog-search")
    font = search.evaluate("(el) => parseFloat(getComputedStyle(el).fontSize)")
    if font < 12:
        raise AssertionError(f"{label}: search font too small ({font}px)")
    excerpt = page.locator(".blog-premium-card .blog-card-body p").first
    excerpt.wait_for(state="visible", timeout=10000)
    text_font = excerpt.evaluate("(el) => parseFloat(getComputedStyle(el).fontSize)")
    if text_font < 12:
        raise AssertionError(f"{label}: excerpt unreadable ({text_font}px)")
    nav = page.locator("#bottom-nav")
    nav.wait_for(state="visible", timeout=10000)
    items = page.locator("#bottom-nav .bottom-nav-item")
    if items.count() != 5:
        raise AssertionError(f"{label}: expected 5 quick links, got {items.count()}")
    widths = items.evaluate_all("(nodes) => nodes.map(n => n.getBoundingClientRect().width)")
    if max(widths) - min(widths) > 1.5:
        raise AssertionError(f"{label}: unequal bottom navigation cells {widths}")
    page.locator("#bottom-nav-menu").click()
    groups = page.locator(".burger-menu-group")
    if groups.count() != 3:
        raise AssertionError(f"{label}: mobile navigation must have three groups")
    page.locator(".burger-close").click()

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

    if not page.locator("#blog-featured").is_visible():
        raise AssertionError(f"{label}: featured analysis missing")
    cards = page.locator(".blog-premium-card").count()
    if cards != 9:
        raise AssertionError(f"{label}: expected first page of 9 cards, got {cards}")
    page.locator("#blog-load-more").click()
    if page.locator(".blog-premium-card").count() != 18:
        raise AssertionError(f"{label}: incremental pagination failed")
    if page.locator(".mx-footer-group").count() != 3:
        raise AssertionError(f"{label}: visitor footer not organized into three groups")

    required = [
      "icon-blog-news.webp", "icon-blog-analysis.webp", "icon-blog-tips.webp",
      "icon-blog-competitions.webp", "icon-blog-search.webp", "icon-blog-category.webp"
    ]
    # Browsers intentionally defer loading off-screen images (loading="lazy").
    # Request their decode explicitly before asserting whether an asset is broken.
    image_health = page.locator("img[src*='blog-premium/']").evaluate_all("""async imgs => await Promise.all(imgs.map(async img => {
      img.loading = 'eager';
      try { await img.decode(); } catch (_) {}
      return {src: img.getAttribute('src'), ok: img.complete && img.naturalWidth > 0,
        width: img.naturalWidth, height: img.naturalHeight};
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

    competition = page.get_by_role("button", name="Compétitions", exact=True)
    competition.click()
    page.wait_for_timeout(120)
    competition_cards = page.locator(".blog-premium-card")
    if competition_cards.count() < 1:
        raise AssertionError(f"{label}: competition filter empty")
    if any(x != "Compétitions" for x in
           competition_cards.evaluate_all("(nodes) => nodes.map(n => n.dataset.blogCategory)")):
        raise AssertionError(f"{label}: competitions mixed with other categories")
    page.get_by_role("button", name="Toutes", exact=True).click()
    if page.locator(".blog-premium-card").count() != 9:
        raise AssertionError(f"{label}: category reset did not reset pagination")
    page.locator("#blog-sort").select_option("competition")
    page.wait_for_timeout(100)
    if page.locator("#blog-featured").is_visible():
        raise AssertionError(f"{label}: featured should not duplicate sorted result")
    page.locator("#blog-sort").select_option("recent")
    search=page.locator("#blog-search")
    search.fill("uniquemarkerzz")
    page.wait_for_timeout(100)
    if page.locator(".blog-premium-card").count() != 1:
        raise AssertionError(f"{label}: search filter failed")
    search.fill("")
    page.wait_for_timeout(100)

    page.locator(".blog-premium-card").first.click(position={"x": 14, "y": 95})
    page.locator("#article-modal").wait_for(state="visible", timeout=5000)
    if not page.locator("#article-modal-title").inner_text().strip():
        raise AssertionError(f"{label}: article modal title empty")
    page.locator("#article-modal .close").click()
    page.locator("#article-modal").wait_for(state="hidden", timeout=5000)

    no_overflow(page, label)
    page.screenshot(path=str(OUT/f"blog-{width}.png"), full_page=True)

    if page_errors:
        raise AssertionError(f"{label}: page errors {page_errors}")

    print(f"PASS {label}: viewport={width}x{height}, cards={cards}, featured/filter/sort/search/pagination/reading/mobile-nav/assets/overflow OK")
    context.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,1024,900,"desktop")
    run_view(browser,768,1024,"tablet")
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
