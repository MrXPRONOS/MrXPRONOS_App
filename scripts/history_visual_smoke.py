#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/history-responsive")
OUT.mkdir(parents=True, exist_ok=True)

DATA = {
  "matches": [
    {
      "id":"h1","event_date":"2026-10-09T19:00:00Z","league":"Premier League",
      "home_team":"Arsenal","away_team":"Chelsea","home_score":2,"away_score":1,
      "is_finished":True,"combo_only":False,
      "predictions":[{"selection_key":"1","type":"Victoire Arsenal","confidence":0.84,"odds":1.72}]
    },
    {
      "id":"h2","event_date":"2026-10-08T18:30:00Z","league":"LaLiga",
      "home_team":"Real Madrid","away_team":"Barcelona","home_score":0,"away_score":1,
      "is_finished":True,"combo_only":False,
      "predictions":[{"selection_key":"1","type":"Victoire Real Madrid","confidence":0.77,"odds":1.94}]
    },
    {
      "id":"h3","event_date":"2026-10-07T20:00:00Z","league":"Ligue 1",
      "home_team":"PSG","away_team":"Monaco","home_score":1,"away_score":1,
      "is_finished":True,"combo_only":False,
      "predictions":[{"selection_key":"1X","type":"Double chance 1X","confidence":0.81,"odds":1.42}]
    }
  ]
}

def no_overflow(page, label):
    size = page.evaluate("() => ({v: innerWidth, d: document.documentElement.scrollWidth, b: document.body.scrollWidth})")
    if max(size["d"], size["b"]) > size["v"] + 1:
        raise AssertionError(f"{label}: horizontal overflow {size}")

def assert_mobile_layout(page, width, label):
    if width > 700:
        return

    hero_h = page.locator(".mx-history-hero").evaluate("(el) => el.getBoundingClientRect().height")
    if hero_h > 170:
        raise AssertionError(f"{label}: hero too tall for content-first mobile UX ({hero_h}px)")

    stats = page.locator(".mx-history-stat")
    if stats.count() != 3:
        raise AssertionError(f"{label}: expected 3 stat cards, got {stats.count()}")
    tops = stats.evaluate_all("(nodes) => nodes.map(n => Math.round(n.getBoundingClientRect().top))")
    if max(tops) - min(tops) > 2:
        raise AssertionError(f"{label}: stat cards are not on one compact row: {tops}")

    toolbar_h = page.locator(".mx-history-toolbar").evaluate("(el) => el.getBoundingClientRect().height")
    if toolbar_h > 34:
        raise AssertionError(f"{label}: results toolbar too tall ({toolbar_h}px)")

    stat_heights = stats.evaluate_all("(nodes) => nodes.map(n => n.getBoundingClientRect().height)")
    if max(stat_heights) > 60:
        raise AssertionError(f"{label}: summary cards consume too much vertical space: {stat_heights}")

    first_row_top = page.locator(".history-row").first.evaluate("(el) => el.getBoundingClientRect().top")
    max_first_row_top = 335 if width >= 390 else 330
    if first_row_top > max_first_row_top:
        raise AssertionError(
            f"{label}: first match starts too low ({first_row_top}px > {max_first_row_top}px); "
            "mobile pages must surface primary content before excessive scrolling"
        )

    rows = page.locator(".history-row")
    geometry = rows.evaluate_all("""(nodes) => nodes.map(row => {
      const rr = row.getBoundingClientRect();
      const badge = row.querySelector('.history-result-badge')?.getBoundingClientRect();
      const meta = row.querySelector('.history-competition')?.getBoundingClientRect();
      return {
        row:{left:rr.left,right:rr.right,top:rr.top,bottom:rr.bottom},
        badge: badge && {left:badge.left,right:badge.right,top:badge.top,bottom:badge.bottom},
        meta: meta && {left:meta.left,right:meta.right,top:meta.top,bottom:meta.bottom}
      };
    })""")
    for g in geometry:
        if not g["badge"] or not g["meta"]:
            raise AssertionError(f"{label}: missing badge/meta geometry")
        if g["badge"]["left"] < g["row"]["left"] - 1 or g["badge"]["right"] > g["row"]["right"] + 1:
            raise AssertionError(f"{label}: result badge escapes card bounds: {g}")
        overlaps_meta = not (
            g["badge"]["bottom"] <= g["meta"]["top"] or
            g["badge"]["top"] >= g["meta"]["bottom"] or
            g["badge"]["right"] <= g["meta"]["left"] or
            g["badge"]["left"] >= g["meta"]["right"]
        )
        if overlaps_meta:
            raise AssertionError(f"{label}: result badge overlaps metadata: {g}")

    nav = page.locator("#bottom-nav")
    nav.wait_for(state="visible", timeout=10000)
    items = page.locator("#bottom-nav .bottom-nav-item")
    if items.count() != 5:
        raise AssertionError(f"{label}: expected 5 bottom-nav items, got {items.count()}")
    widths = items.evaluate_all("(nodes) => nodes.map(n => n.getBoundingClientRect().width)")
    if max(widths) - min(widths) > 1.5:
        raise AssertionError(f"{label}: bottom-nav cells are not equal: {widths}")

    assistant = page.locator(".assistant-button")
    if assistant.count() and assistant.is_visible():
        overlap = page.evaluate("""() => {
          const a=document.querySelector('.assistant-button')?.getBoundingClientRect();
          const n=document.querySelector('#bottom-nav')?.getBoundingClientRect();
          if(!a || !n) return false;
          return !(a.bottom <= n.top || a.top >= n.bottom || a.right <= n.left || a.left >= n.right);
        }""")
        if overlap:
            raise AssertionError(f"{label}: assistant overlaps bottom navigation")

def run_view(browser, width, height, label):
    page = browser.new_page(viewport={"width":width,"height":height})
    page.route("**/data.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(DATA)))
    page.goto("http://127.0.0.1:8000/historique.html", wait_until="domcontentloaded", timeout=60000)
    page.locator(".history-row").first.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(900)

    no_overflow(page, label)
    assert_mobile_layout(page, width, label)

    row_count = page.locator(".history-row").count()
    if row_count < 1:
        raise AssertionError(f"{label}: no history row rendered")

    total_text = page.locator("#history-total-count").inner_text().strip()
    wins_text = page.locator("#history-win-count").inner_text().strip()
    rate_text = page.locator("#history-success-rate").inner_text().strip()
    if not total_text.isdigit() or int(total_text) < 1:
        raise AssertionError(f"{label}: invalid total counter {total_text!r}")
    if not wins_text.isdigit() or int(wins_text) < 0:
        raise AssertionError(f"{label}: invalid win counter {wins_text!r}")
    if rate_text != "—" and not rate_text.endswith("%"):
        raise AssertionError(f"{label}: invalid success rate {rate_text!r}")

    imgs = page.locator("img[src*='history-premium/']").evaluate_all(
      "(nodes) => nodes.map(i => ({src:i.getAttribute('src'), ok:i.complete && i.naturalWidth>0, w:i.naturalWidth, h:i.naturalHeight}))"
    )
    broken=[x for x in imgs if not x["ok"]]
    if broken:
        raise AssertionError(f"{label}: broken history premium images {broken}")
    required=["icon-history-published.webp","icon-history-wins.webp","icon-history-rate.webp"]
    sources=[x["src"] for x in imgs]
    for asset in required:
        if not any(asset in s for s in sources):
            raise AssertionError(f"{label}: missing rendered asset {asset}")

    hero_bg = page.locator(".mx-history-hero-atmosphere").evaluate("(el)=>getComputedStyle(el).backgroundImage")
    if "hero-history-stadium.webp" not in hero_bg:
        raise AssertionError(f"{label}: generated stadium background not active")

    page.screenshot(path=str(OUT/f"history-{width}.png"), full_page=True)
    print(f"PASS {label}: {width}x{height}, data, assets, mobile geometry and overflow OK")
    page.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    run_view(browser,1024,900,"desktop")
    run_view(browser,390,844,"mobile")
    run_view(browser,320,720,"small-mobile")
    browser.close()
