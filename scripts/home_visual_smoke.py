#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/home-responsive")
OUT.mkdir(parents=True, exist_ok=True)

def no_overflow(page, label):
    size = page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    maximum = max(size["d"], size["b"])
    if maximum > size["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {maximum}px > {size['v']}px")

def run_view(browser, width, height, label):
    context = browser.new_context(viewport={"width":width,"height":height}, service_workers="block")
    page = context.new_page()
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto("http://127.0.0.1:8000/index.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".mx-feature-card").first.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(900)

    no_overflow(page, label)

    showcase = page.locator(".mx-home-showcase")
    if showcase.count() != 1 or not showcase.is_visible():
        raise AssertionError(f"{label}: home showcase missing")

    page.wait_for_function("""() => {
      const top=document.querySelector('#top-today-picks');
      const verified=document.querySelector('#verified-picks');
      const settled=(el)=>el && (el.querySelector('.pick-card') || el.querySelector('.no-events'));
      return settled(top) && settled(verified);
    }""", timeout=10000)

    top_cards = page.locator("#top-today-picks .pick-card")
    verified_cards = page.locator("#verified-picks .pick-card")
    if top_cards.count() > 3:
        raise AssertionError(f"{label}: too many highlighted daily selections ({top_cards.count()})")
    if verified_cards.count() > 3:
        raise AssertionError(f"{label}: too many verified result cards ({verified_cards.count()})")
    # L'accueil est une vitrine des derniers gagnants ; l'historique reste complet.
    if page.locator("#verified-picks .pick-card--lost").count():
        raise AssertionError(f"{label}: losing predictions leaked into the winner showcase")
    badges = verified_cards.locator(".pick-badge").all_text_contents()
    if any(badge.strip() != "GAGNÉ" for badge in badges):
        raise AssertionError(f"{label}: home result not marked as a winner: {badges}")
    if page.locator("#mx-hero-title").evaluate("(el)=>getComputedStyle(el).textTransform") != "uppercase":
        raise AssertionError(f"{label}: homepage main title is not uppercase")

    proofbar = page.locator(".mx-home-proofbar")
    if proofbar.count() != 1 or not proofbar.is_visible():
        raise AssertionError(f"{label}: performance proof bar missing")

    cards = page.locator(".mx-feature-card")
    if cards.count() != 3:
        raise AssertionError(f"{label}: expected 3 primary action cards, got {cards.count()}")

    hrefs = cards.evaluate_all("els => els.map(e => e.getAttribute('href'))")
    expected = ["pronos.html", "historique.html", "blog.html"]
    if hrefs != expected:
        raise AssertionError(f"{label}: primary action links changed: {hrefs}")

    images = page.locator(".mx-feature-card img").evaluate_all(
        "imgs => imgs.map(i => ({src:i.getAttribute('src'), ok:i.complete && i.naturalWidth>0}))"
    )
    broken = [item for item in images if not item["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken primary action assets {broken}")

    if width <= 700:
        hero_h = page.locator(".mx-hero").evaluate("(el)=>el.getBoundingClientRect().height")
        max_hero = 350 if width >= 390 else 335
        if hero_h > max_hero:
            raise AssertionError(f"{label}: hero too tall ({hero_h}px > {max_hero}px)")

        hero_desc = page.locator(".mx-hero-copy > p")
        if hero_desc.count() and hero_desc.is_visible():
            raise AssertionError(f"{label}: secondary hero description should be hidden")

        # Le parcours direct doit être visible en priorité, avant les rubriques secondaires.
        actions = page.locator(".mx-hero-actions a")
        action_links = actions.evaluate_all("els => els.map(e => e.getAttribute('href'))")
        if action_links != ["pronos.html", "historique.html"]:
            raise AssertionError(f"{label}: expected two direct actions, got {action_links}")
        action_heights = actions.evaluate_all("(els) => els.map(el => el.getBoundingClientRect().height)")
        if min(action_heights) < 44:
            raise AssertionError(f"{label}: action too small for mobile {action_heights}")

        grid = page.locator(".mx-feature-grid")
        showcase_top = showcase.evaluate("(el)=>el.getBoundingClientRect().top")
        grid_top = grid.evaluate("(el)=>el.getBoundingClientRect().top")
        if showcase_top >= grid_top:
            raise AssertionError(f"{label}: selections/results must precede secondary cards")

        card_desc = cards.first.locator("p")
        if card_desc.count() and card_desc.is_visible():
            raise AssertionError(f"{label}: primary action descriptions should be hidden")

        details = page.locator(".mx-home-detail")
        if details.count() != 2:
            raise AssertionError(f"{label}: expected two secondary detail sections")
        for i in range(details.count()):
            if details.nth(i).get_attribute("open") is not None:
                raise AssertionError(f"{label}: secondary detail section {i} should be collapsed")

        details.first.locator("summary").click()
        if details.first.get_attribute("open") is None:
            raise AssertionError(f"{label}: collapsed secondary section cannot be opened")
        details.first.locator("summary").click()

        for group_name, group in [("daily", top_cards), ("verified", verified_cards)]:
            if group.count():
                heights = group.evaluate_all("(nodes)=>nodes.map(n=>n.getBoundingClientRect().height)")
                if max(heights) > 270:
                    raise AssertionError(f"{label}: {group_name} home card too tall: {heights}")

        proof_h = proofbar.evaluate("(el)=>el.getBoundingClientRect().height")
        if proof_h > 58:
            raise AssertionError(f"{label}: compact proof bar too tall ({proof_h}px)")

        # Mesurer depuis le vrai haut de page, et non apres le clic sur les
        # panneaux secondaires qui peut faire defiler la page automatiquement.
        page.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
        page.wait_for_timeout(200)
        # Test the compact layout with THREE full-height cards even when the
        # live feed is empty: no misleading match/test data is published.
        geometry = page.evaluate("""() => {
            const rails = [...document.querySelectorAll('.mx-home-picks')];
            const original = rails.map((el) => el.innerHTML);
            const sample = `<a class="pick-card" href="pronos.html">
              <div class="pick-badge">SÉLECTION</div><div class="pick-category">PRO</div>
              <div class="pick-head"><span class="pick-league">Premier League</span><span class="pick-time">Aujourd'hui</span></div>
              <div class="pick-teams">
                <div class="pick-team"><img class="pick-logo" alt="" src="assets/images/default-logo.webp"><span class="pick-team-name">Arsenal</span></div>
                <div class="pick-vs"><strong>VS</strong><small>18:00</small></div>
                <div class="pick-team pick-team--right"><img class="pick-logo" alt="" src="assets/images/default-logo.webp"><span class="pick-team-name">Chelsea</span></div>
              </div>
              <div class="pick-highlight"><span>Pronostic</span><strong>Plus de 1,5 but</strong></div>
              <div class="pick-confidence"><span>Confiance</span><div class="pick-confidence-bar"><i style="width:84%"></i></div><b>84%</b></div>
            </a>`;
            const result = [];
            try {
              rails.forEach((rail) => {
                if (rail.querySelectorAll('.pick-card').length < 2) {
                  rail.innerHTML = sample.repeat(3);
                }
                const cards = [...rail.querySelectorAll('.pick-card')];
                const railRect = rail.getBoundingClientRect();
                const second = cards[1].getBoundingClientRect();
                result.push({
                  railWidth: railRect.width, cardWidth: cards[0].getBoundingClientRect().width,
                  cardHeight: cards[0].getBoundingClientRect().height,
                  visibleSecond: Math.max(0, Math.min(railRect.right, second.right) - Math.max(railRect.left, second.left)),
                  secondWidth: second.width,
                  scrollWidth: rail.scrollWidth,
                  clientWidth: rail.clientWidth
                });
              });
              const proof = document.querySelector('.mx-home-proofbar').getBoundingClientRect();
              const nav = document.querySelector('#bottom-nav').getBoundingClientRect();
              return {rails:result, proofBottom:proof.bottom, navTop:nav.top, viewport:innerHeight,
                      scrollY:scrollY, hero:document.querySelector('.mx-hero').getBoundingClientRect().height};
            } finally {
              rails.forEach((rail,i)=>rail.innerHTML=original[i]);
            }
        }""")
        print(f"COMPACT {label}: {geometry}", flush=True)
        for index, rail in enumerate(geometry["rails"]):
            if rail["cardHeight"] > 112:
                raise AssertionError(f"{label}: rail {index} cards remain too tall: {rail}")
            if rail["secondWidth"] and rail["visibleSecond"]/rail["secondWidth"] < 0.50:
                raise AssertionError(f"{label}: rail {index} needs a larger peek of the next coupon: {rail}")
            if rail["scrollWidth"] <= rail["clientWidth"]:
                raise AssertionError(f"{label}: rail {index} must remain horizontally scrollable")
        if geometry["proofBottom"] > min(geometry["viewport"],geometry["navTop"]-5):
            raise AssertionError(f"{label}: win rate requires vertical scrolling: {geometry}")

        support_desc = page.locator(".mx-support p")
        if support_desc.count() and support_desc.is_visible():
            raise AssertionError(f"{label}: support description should not add mobile reading load")

        nav = page.locator("#bottom-nav")
        nav.wait_for(state="visible", timeout=10000)
        nav_items = page.locator("#bottom-nav .bottom-nav-item")
        if nav_items.count() != 5:
            raise AssertionError(f"{label}: expected 5 bottom navigation items, got {nav_items.count()}")
    else:
        details = page.locator(".mx-home-detail")
        for i in range(details.count()):
            if details.nth(i).get_attribute("open") is not None:
                raise AssertionError(f"{label}: optional sections must start collapsed on desktop")

    no_overflow(page, label)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(150)
    page.screenshot(path=str(OUT/f"home-{width}.png"), full_page=True)

    if page_errors:
        raise AssertionError(f"{label}: page errors {page_errors}")

    print(f"PASS {label}: {width}x{height}, content-first/actions/selections/results/proof/details/navigation/overflow OK")
    context.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_view(browser, 1024, 900, "desktop")
    run_view(browser, 390, 844, "mobile")
    run_view(browser, 320, 720, "small-mobile")
    browser.close()
