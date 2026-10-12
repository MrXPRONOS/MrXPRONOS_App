#!/usr/bin/env python3
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT=Path("artifacts/detail-mobile")
OUT.mkdir(parents=True,exist_ok=True)

ARTICLE={
  "title":"Comment analyser un match avant de parier",
  "slug":"analyse-mobile-test",
  "date":"2026-10-12",
  "active":True,
  "meta_description":"Article de test mobile.",
  "content":"## Lire le contexte du match\nUn bon pronostic commence par la forme des équipes.\n\n### Vérifier les absences\nComparez les informations importantes avant toute décision.",
  "image_url":"assets/images/blog-premium/hero-blog.webp"
}
CONSEIL={
  "title":"Gérer sa bankroll avec discipline",
  "slug":"bankroll-mobile-test",
  "date":"2026-10-12",
  "active":True,
  "excerpt":"Conseil de test mobile.",
  "content":"## Définir une limite\nFixez un budget clair.\n\n### Garder une mise stable\nLa discipline protège votre bankroll.",
  "image_url":"assets/images/conseils-premium/hero-conseils.webp"
}

def install_routes(page):
    page.route("**/articles.json*",lambda r:r.fulfill(status=200,content_type="application/json",body=json.dumps([ARTICLE])))
    page.route("**/conseils.json*",lambda r:r.fulfill(status=200,content_type="application/json",body=json.dumps([CONSEIL])))
    page.route("**/data.json*",lambda r:r.fulfill(status=200,content_type="application/json",body=json.dumps({"articles":[ARTICLE],"conseils":[CONSEIL],"matches":[]})))
    for name in ["infos.json","footnews.json","bonus.json","bookmakers.json"]:
        page.route(f"**/{name}*",lambda r,_req=None:r.fulfill(status=200,content_type="application/json",body="[]"))

def no_overflow(page,label):
    d=page.evaluate("() => ({v:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})")
    if max(d["d"],d["b"])>d["v"]+1:
        raise AssertionError(f"{label}: horizontal overflow {d}")

def check_detail(browser,path,root,width,height,label):
    ctx=browser.new_context(viewport={"width":width,"height":height},service_workers="block")
    page=ctx.new_page()
    install_routes(page)
    page.goto(f"http://127.0.0.1:8000/{path}",wait_until="domcontentloaded",timeout=60000)
    page.locator(f"{root} .article-page-card").wait_for(state="visible",timeout=30000)
    page.wait_for_timeout(450)
    no_overflow(page,label)

    card=page.locator(f"{root} .article-page-card")
    h1=card.locator("h1")
    if not h1.inner_text().strip():
        raise AssertionError(f"{label}: detail title empty")

    image=card.locator("img.news-image")
    if image.count()!=1 or not image.evaluate("(i)=>i.complete && i.naturalWidth>0"):
        raise AssertionError(f"{label}: detail hero image broken")

    if width<=700:
        ih=image.bounding_box()["height"]
        if ih>115:
            raise AssertionError(f"{label}: detail image too tall {ih}")

    content=card.locator(".article-content")
    if width<=700:
        content_top=content.evaluate("(el)=>el.getBoundingClientRect().top")
        max_content_top=315 if width>=390 else 300
        if content_top>max_content_top:
            raise AssertionError(f"{label}: reading content starts too low ({content_top}px > {max_content_top}px)")
    if len(content.inner_text().strip())<20:
        raise AssertionError(f"{label}: detail content missing")

    page.screenshot(path=str(OUT/f"{label}.png"),full_page=True)
    ctx.close()
    print("PASS",label)

def check_bookmakers(browser,width,height,label):
    ctx=browser.new_context(viewport={"width":width,"height":height},service_workers="block")
    page=ctx.new_page()
    page.goto("http://127.0.0.1:8000/bookmakers.html",wait_until="domcontentloaded",timeout=60000)
    page.locator(".card").first.wait_for(state="visible",timeout=10000)
    page.wait_for_timeout(350)
    no_overflow(page,label)

    cards=page.locator(".card")
    if cards.count()!=6:
        raise AssertionError(f"{label}: expected 6 bookmakers, got {cards.count()}")

    imgs=page.locator(".logo-box img").evaluate_all("imgs=>imgs.map(i=>i.complete&&i.naturalWidth>0)")
    if not all(imgs):
        raise AssertionError(f"{label}: bookmaker logo broken")

    joins=page.locator(".join")
    if joins.count()!=6:
        raise AssertionError(f"{label}: bookmaker CTA count invalid")

    if width<=700:
        if cards.first.bounding_box()["height"]>135:
            raise AssertionError(f"{label}: bookmaker card still too tall")

    page.screenshot(path=str(OUT/f"{label}.png"),full_page=True)
    ctx.close()
    print("PASS",label)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width,height,suffix in [(390,844,"390"),(320,720,"320")]:
        check_detail(browser,"article.html?slug=analyse-mobile-test","#blog-post",width,height,f"article-{suffix}")
        check_detail(browser,"conseil.html?slug=bankroll-mobile-test","#conseil-post",width,height,f"conseil-{suffix}")
        check_bookmakers(browser,width,height,f"bookmakers-{suffix}")
    browser.close()
