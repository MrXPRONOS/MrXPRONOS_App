#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlparse
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/live-responsive")
OUT.mkdir(parents=True, exist_ok=True)

LIVE_MATCHES = [
    {
        "id": "live-corners", "home_team": "Manchester City", "away_team": "Arsenal",
        "home_score": 1, "away_score": 1, "current_minute": 67,
        "league": {"name": "Premier League"}, "freshness_seconds": 8,
        "reliability_score": 91, "value_score": 84,
        "live_stats": {"home": {"corner_kicks": 4, "fouls": 6, "total_shots": 10}, "away": {"corner_kicks": 3, "fouls": 7, "total_shots": 8}},
        "predictions": [{"id": "p-corners", "type": "total_corners", "badge": "Corners", "title": "Over 8.5 corners", "probability": 0.84, "reliability": 91, "pronostic": 8.5, "threshold": 8.5, "current": 7, "signal_value": 6, "message": "Rythme élevé sur les côtés.", "reasons": ["Pression offensive continue", "Volume de corners régulier"]}]
    },
    {
        "id": "live-shots", "home_team": "Real Madrid", "away_team": "Barcelona",
        "home_score": 2, "away_score": 1, "current_minute": 72,
        "league": {"name": "LaLiga"}, "freshness_seconds": 13,
        "reliability_score": 86, "value_score": 77,
        "live_stats": {"home": {"corner_kicks": 5, "fouls": 8, "total_shots": 13}, "away": {"corner_kicks": 4, "fouls": 9, "total_shots": 11}},
        "predictions": [{"id": "p-shots", "type": "total_shots", "badge": "Tirs", "title": "Over 26.5 tirs", "probability": 0.78, "reliability": 86, "pronostic": 26.5, "threshold": 26.5, "current": 24, "signal_value": 21, "message": "Le volume de tirs reste soutenu.", "reasons": ["Deux équipes très actives"]}]
    },
    {
        "id": "live-fouls", "home_team": "Inter", "away_team": "Juventus",
        "home_score": 0, "away_score": 0, "current_minute": 58,
        "league": {"name": "Serie A"}, "freshness_seconds": 18,
        "reliability_score": 79, "value_score": 72,
        "live_stats": {"home": {"corner_kicks": 2, "fouls": 10, "total_shots": 7}, "away": {"corner_kicks": 1, "fouls": 9, "total_shots": 6}},
        "predictions": [{"id": "p-fouls", "type": "total_fouls", "badge": "Fautes", "title": "Over 24.5 fautes", "probability": 0.74, "reliability": 79, "pronostic": 24.5, "threshold": 24.5, "current": 19, "signal_value": 17, "message": "Intensité élevée au milieu.", "reasons": ["Duels fréquents"]}]
    }
]

SCHEDULED = [
    {"id": "up-1", "home_team": "Liverpool", "away_team": "Chelsea", "event_date": "2026-10-11T18:30:00Z", "league": {"name": "Premier League"}},
    {"id": "up-2", "home_team": "PSG", "away_team": "Marseille", "event_date": "2026-10-11T20:00:00Z", "league": {"name": "Ligue 1"}}
]

HISTORY = [
    {"id": "hist-1", "home_team": "Bayern", "away_team": "Dortmund", "home_score": 2, "away_score": 1, "current_minute": 61, "league": {"name": "Bundesliga"}, "type": "total_corners", "pronostic": 8.5, "threshold": 8.5, "probability": 0.82, "signal_value": 6, "current": 10, "validated": True, "outcome": "success", "validation_type": "instant", "timestamp": 1791726000000},
    {"id": "hist-2", "home_team": "Milan", "away_team": "Napoli", "home_score": 1, "away_score": 0, "current_minute": 70, "league": {"name": "Serie A"}, "type": "total_shots", "pronostic": 22.5, "threshold": 22.5, "probability": 0.73, "signal_value": 18, "current": 20, "validated": True, "outcome": "failure", "timestamp": 1791722400000}
]

NOTIFICATIONS = [
    {"id": "notif-1", "type": "prediction_reached", "title": "Pronostic atteint", "message": "✅ Le seuil du pronostic a été atteint.", "timestamp": 1791726000000, "read": False, "related_prediction_id": "hist-1"}
]

def api_payload(path):
    if path.endswith("/matches"): return {"matches": LIVE_MATCHES}
    if path.endswith("/opportunities"): return {"opportunities": LIVE_MATCHES[:2]}
    if path.endswith("/notifications"): return {"notifications": NOTIFICATIONS}
    if path.endswith("/predictions/history"): return {"history": HISTORY}
    if path.endswith("/today"): return {"data": {"scheduled": {"matches": SCHEDULED}}}
    if path.endswith("/predictions/by-id"): return {"prediction": HISTORY[0]}
    return None

def install_routes(page):
    def handler(route, request):
        parsed = urlparse(request.url)
        if "/functions/v1/live/" not in parsed.path:
            route.continue_()
            return
        payload = api_payload(parsed.path)
        if payload is None:
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": "mock not found"}))
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
    page.route("**/functions/v1/live/**", handler)

def assert_no_overflow(page, label):
    values = page.evaluate("""() => ({viewport: window.innerWidth, doc: document.documentElement.scrollWidth, body: document.body.scrollWidth})""")
    maximum = max(values["doc"], values["body"])
    if maximum > values["viewport"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {maximum}px > {values['viewport']}px")

def check_tabs(page, mobile):
    if mobile:
        nav = page.locator(".mx-mobile-tabs")
        nav.wait_for(state="visible")
        for label, selector in [("À venir", ".mx-upcoming-card"), ("Historique", ".mx-history-live-card"), ("Notifs", ".mx-notification-card")]:
            nav.get_by_role("button", name=label, exact=False).click()
            page.locator(selector).first.wait_for(state="visible")
        nav.get_by_role("button", name="Live", exact=False).click()
    else:
        tabs = page.locator(".mx-live-tabs")
        tabs.wait_for(state="visible")
        for label, selector in [("À venir", ".mx-upcoming-card"), ("Historique", ".mx-history-live-card"), ("Notifications", ".mx-notification-card")]:
            tabs.get_by_role("button", name=label, exact=False).click()
            page.locator(selector).first.wait_for(state="visible")
        tabs.get_by_role("button", name="Live", exact=False).click()

def assert_secondary_mobile_tabs(page, width, name):
    if width > 640:
        return

    nav = page.locator(".mx-mobile-tabs")
    cases = [
        ("À venir", ".mx-upcoming-card", 145, 125, "upcoming"),
        ("Historique", ".mx-history-live-card", 145, 190, "history"),
        ("Notifs", ".mx-notification-card", 155, 115, "notifications"),
    ]

    for label, selector, max_top, max_height, slug in cases:
        nav.get_by_role("button", name=label, exact=False).click()
        card = page.locator(selector).first
        card.wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(120)

        if page.locator(".mx-live-hero").is_visible():
            raise AssertionError(f"{name}/{slug}: LIVE hero should be hidden on secondary mobile tabs")
        if page.locator(".mx-live-overview").is_visible():
            raise AssertionError(f"{name}/{slug}: LIVE stats band should be hidden on secondary mobile tabs")

        top = card.evaluate("(el) => el.getBoundingClientRect().top")
        height = card.evaluate("(el) => el.getBoundingClientRect().height")
        if top > max_top:
            raise AssertionError(f"{name}/{slug}: first card starts too low ({top}px > {max_top}px)")
        if height > max_height:
            raise AssertionError(f"{name}/{slug}: first card remains too tall ({height}px > {max_height}px)")
        assert_no_overflow(page, f"{name}/{slug}")
        page.screenshot(path=str(OUT / f"live-{slug}-{width}.png"), full_page=True)

    nav.get_by_role("button", name="Live", exact=False).click()
    page.locator(".mx-live-hero").wait_for(state="visible", timeout=5000)

def run_view(browser, width, height, name):
    page = browser.new_page(viewport={"width": width, "height": height})
    install_routes(page)
    page_errors, console_errors = [], []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    page.goto("http://127.0.0.1:8000/live.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".mx-live-row").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(1200)

    if page.locator("#boot-screen").count() and page.locator("#boot-screen").is_visible():
        raise AssertionError(f"{name}: boot screen still visible")

    assert_no_overflow(page, name)

    # signals-first mobile density: live opportunities must surface before decorative copy.
    if width <= 640:
        hero_h = page.locator(".mx-live-hero").evaluate("(el) => el.getBoundingClientRect().height")
        hero_limit = 120 if width >= 390 else 110
        if hero_h > hero_limit:
            raise AssertionError(f"{name}: LIVE hero too tall ({hero_h}px > {hero_limit}px)")

        hero_lead = page.locator(".mx-live-hero__lead")
        if hero_lead.count() and hero_lead.is_visible():
            raise AssertionError(f"{name}: secondary LIVE hero description should be hidden")

        benefits = page.locator(".mx-live-benefits")
        if benefits.count() and benefits.is_visible():
            raise AssertionError(f"{name}: secondary LIVE benefit cards should be hidden")

        overview_h = page.locator(".mx-live-overview").evaluate("(el) => el.getBoundingClientRect().height")
        if overview_h > 54:
            raise AssertionError(f"{name}: LIVE stats band too tall ({overview_h}px)")

        filters_h = page.locator(".mx-market-filters").evaluate("(el) => el.getBoundingClientRect().height")
        if filters_h > 38:
            raise AssertionError(f"{name}: LIVE filters too tall ({filters_h}px)")

        first_row_top = page.locator(".mx-live-row").first.evaluate("(el) => el.getBoundingClientRect().top")
        max_top = 330 if width >= 390 else 315
        if first_row_top > max_top:
            raise AssertionError(f"{name}: first LIVE signal starts too low ({first_row_top}px > {max_top}px)")

        how_section = page.locator(".mx-live-how")
        if how_section.count() and how_section.is_visible():
            raise AssertionError(f"{name}: explanatory LIVE section should not add mobile reading load")

    required_assets = ["icon-stopwatch.webp", "icon-ball.webp", "icon-corner.webp", "icon-whistle.webp", "icon-target.webp", "icon-pie.webp", "icon-bars.webp"]
    sources = page.locator("img").evaluate_all("(imgs) => imgs.map(i => i.getAttribute('src') || '')")
    missing = [asset for asset in required_assets if not any(asset in src for src in sources)]
    if missing:
        raise AssertionError(f"{name}: premium assets missing from rendered interface: {missing}")

    image_health = page.locator("img[src*='live-premium/']").evaluate_all("""imgs => imgs.map(img => ({
        src: img.getAttribute('src'), loaded: img.complete && img.naturalWidth > 0,
        width: img.naturalWidth, height: img.naturalHeight
    }))""")
    broken = [item for item in image_health if not item["loaded"]]
    if broken:
        raise AssertionError(f"{name}: missing or broken premium WebP images: {broken}")
    if not any("player-back.webp" in item["src"] for item in image_health):
        raise AssertionError(f"{name}: hero player asset missing")
    hero_background = page.locator(".mx-live-hero").evaluate("(el) => getComputedStyle(el).backgroundImage")
    if "hero-stadium.webp" not in hero_background:
        raise AssertionError(f"{name}: premium stadium background missing")

    score = page.locator(".mx-live-row__score-center").first
    score.wait_for(state="visible")
    if not score.inner_text().strip():
        raise AssertionError(f"{name}: central score is empty")

    page.locator(".mx-market-filter").filter(has_text="Tirs").click()
    page.locator(".mx-live-row").first.wait_for(state="visible")
    page.locator(".mx-market-filter").filter(has_text="Tous").click()

    check_tabs(page, mobile=width <= 640)
    assert_secondary_mobile_tabs(page, width, name)
    tabs = page.locator(".mx-mobile-tabs" if width <= 640 else ".mx-live-tabs")
    tabs.get_by_role("button", name="Historique", exact=False).click()
    page.locator(".mx-history-premium__score").first.wait_for(state="visible")
    page.locator(".mx-history-live-card").first.click()
    page.locator(".mx-live-modal").first.wait_for(state="visible")
    page.locator(".mx-live-modal button").first.click()
    tabs.get_by_role("button", name="Notifs" if width <= 640 else "Notifications", exact=False).click()
    page.locator(".mx-notification-premium__title").first.wait_for(state="visible")
    page.locator(".mx-notification-card").first.click()
    page.locator(".mx-live-modal").first.wait_for(state="visible")
    page.locator(".mx-live-modal button").first.click()
    tabs.get_by_role("button", name="Live", exact=False).click()
    assert_no_overflow(page, name)
    page.screenshot(path=str(OUT / f"live-{width}.png"), full_page=True)

    fatal_console = [e for e in console_errors if "Failed to load resource" not in e and "favicon" not in e.lower()]
    if page_errors:
        raise AssertionError(f"{name}: page errors: {page_errors}")
    if fatal_console:
        raise AssertionError(f"{name}: console errors: {fatal_console}")

    print(f"PASS {name}: viewport={width}x{height}, live/upcoming/history/notifications density + overflow + interactions OK")
    page.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_view(browser, 1024, 900, "desktop")
    run_view(browser, 390, 844, "mobile")
    run_view(browser, 320, 720, "small-mobile")
    browser.close()
