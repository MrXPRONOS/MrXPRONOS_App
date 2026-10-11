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

    required_assets = ["icon-stopwatch.webp", "icon-ball.webp", "icon-corner.webp", "icon-whistle.webp", "icon-target.webp", "icon-pie.webp", "icon-bars.webp"]
    sources = page.locator("img").evaluate_all("(imgs) => imgs.map(i => i.getAttribute('src') || '')")
    missing = [asset for asset in required_assets if not any(asset in src for src in sources)]
    if missing:
        raise AssertionError(f"{name}: premium assets missing from rendered interface: {missing}")

    score = page.locator(".mx-live-row__score-center").first
    score.wait_for(state="visible")
    if not score.inner_text().strip():
        raise AssertionError(f"{name}: central score is empty")

    page.locator(".mx-market-filter").filter(has_text="Tirs").click()
    page.locator(".mx-live-row").first.wait_for(state="visible")
    page.locator(".mx-market-filter").filter(has_text="Tous").click()

    check_tabs(page, mobile=width <= 640)
    assert_no_overflow(page, name)
    page.screenshot(path=str(OUT / f"live-{width}.png"), full_page=True)

    fatal_console = [e for e in console_errors if "Failed to load resource" not in e and "favicon" not in e.lower()]
    if page_errors:
        raise AssertionError(f"{name}: page errors: {page_errors}")
    if fatal_console:
        raise AssertionError(f"{name}: console errors: {fatal_console}")

    print(f"PASS {name}: viewport={width}x{height}, overflow=none, tabs=ok, premium-assets=ok")
    page.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    run_view(browser, 1024, 900, "desktop")
    run_view(browser, 390, 844, "mobile")
    browser.close()
