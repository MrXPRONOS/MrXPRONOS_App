#!/usr/bin/env python3
"""Viewport + interaction smoke tests for pronos.html. Produces real browser screenshots."""
from __future__ import annotations
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

SIZES = (1440, 1024, 768, 390, 320)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/pronos.html")
    ap.add_argument("--out", default="artifacts/pronos-responsive")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        for width in SIZES:
            page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            try:
                page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
                page.locator("#pronos-page-title").wait_for(timeout=12000)
                page.locator("#matches-container .match-card, #matches-container .no-events, #matches-container .error").first.wait_for(timeout=25000)
                page.screenshot(path=str(out / f"pronos-{width}.png"), full_page=True, animations="disabled")
                measurements = page.evaluate("""() => ({
                    viewport: document.documentElement.clientWidth,
                    full: document.documentElement.scrollWidth,
                    cards: document.querySelectorAll('#matches-container .match-card').length,
                    logo: (() => { const i=document.querySelector('.mx-site-header .logo img'); return !!i && i.complete && i.naturalWidth > 0; })(),
                    heading: !!document.querySelector('#pronos-page-title'),
                    tabs: document.querySelectorAll('.pronostic-category-tabs .tab-btn').length
                })""")
                print(width, measurements)
                if measurements["full"] > measurements["viewport"] + 2:
                    failures.append(f"{width}px: horizontal overflow {measurements['full']} > {measurements['viewport']}")
                if measurements["cards"] == 0 and page.locator("#matches-container .no-events, #matches-container .error").count() == 0:
                    failures.append(f"{width}px: blank match results despite ready page")

                # matches-first mobile layout: remove reading load before the actual picks.
                if width <= 590:
                    hero_h = page.locator(".mx-pronos-hero").evaluate("(el) => el.getBoundingClientRect().height")
                    hero_limit = 135 if width >= 390 else 122
                    if hero_h > hero_limit:
                        failures.append(f"{width}px: hero too tall for matches-first mobile layout ({hero_h}px)")

                    hero_desc = page.locator(".mx-pronos-hero-copy p")
                    if hero_desc.count() and hero_desc.is_visible():
                        failures.append(f"{width}px: secondary hero description should be hidden")

                    category_copy = page.locator(".category-copy")
                    if category_copy.count() and category_copy.is_visible():
                        failures.append(f"{width}px: redundant category copy should be hidden")

                    tabs_h = page.locator(".pronostic-category-tabs").evaluate("(el) => el.getBoundingClientRect().height")
                    if tabs_h > 42:
                        failures.append(f"{width}px: category tabs too tall ({tabs_h}px)")

                    filter_h = page.locator(".pronos-filter-shell").evaluate("(el) => el.getBoundingClientRect().height")
                    if filter_h > 70:
                        failures.append(f"{width}px: search/date controls too tall ({filter_h}px)")

                    if measurements["cards"] > 0:
                        first_card_top = page.locator("#matches-container .match-card").first.evaluate("(el) => el.getBoundingClientRect().top")
                        max_top = 355 if width >= 390 else 340
                        if first_card_top > max_top:
                            failures.append(
                                f"{width}px: first match starts too low ({first_card_top}px > {max_top}px)"
                            )

                    nav = page.locator("#bottom-nav")
                    nav.wait_for(state="visible", timeout=10000)
                    nav_items = page.locator("#bottom-nav .bottom-nav-item")
                    if nav_items.count() != 5:
                        failures.append(f"{width}px: expected 5 mobile nav items, got {nav_items.count()}")
                if not measurements["logo"] or not measurements["heading"] or measurements["tabs"] != 3:
                    failures.append(f"{width}px: missing essential component")
                if width == 390:
                    for category in ("pro", "vip", "simple"):
                        tab = page.locator(f'[data-cat="{category}"]')
                        tab.click()
                        if "active" not in (tab.get_attribute("class") or ""):
                            failures.append(f"tab {category} did not activate")
                    for day in ("tomorrow", "yesterday", "today"):
                        btn = page.locator(f'.day-btn[data-day="{day}"]')
                        btn.click()
                        if "active" not in (btn.get_attribute("class") or ""):
                            failures.append(f"day filter {day} did not activate")
                if errors:
                    failures.append(f"{width}px: JS page errors: {errors[:3]}")
            except Exception as exc:
                failures.append(f"{width}px: {type(exc).__name__} {exc}")
            finally:
                page.close()
        browser.close()
    if failures:
        print("FAILED:")
        for failure in failures:
            print(" -", failure)
        raise SystemExit(1)
    print("PASS: 5 viewport screenshots, matches-first mobile density, no overflow, tabs/date filters/navigation responsive")

if __name__ == "__main__":
    main()
