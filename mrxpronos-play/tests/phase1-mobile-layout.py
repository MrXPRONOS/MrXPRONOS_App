#!/usr/bin/env python3
"""Phase 1 mobile layout smoke in Chromium, without using Telegram credentials."""
import base64
import json
from pathlib import Path
import re
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "worker.js").read_text(encoding="utf-8")
start = source.index('const html="') + len("const html=")
end = source.index(';\nconst page', start)
html = json.loads(source[start:end])
html = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="1024" height="1024" fill="#e9ca68"/></svg>'
big_icon = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

screens = [
    "screen-tap", "screen-wheel", "screen-missions",
    "screen-friends", "screen-profile", "screen-shop", "screen-nft"
]
widths = (320, 360, 375, 390, 430)

with sync_playwright() as p:
    system_browser = shutil.which('google-chrome') or shutil.which('chromium')
    browser = p.chromium.launch(headless=True, executable_path=system_browser if system_browser else None, args=['--no-sandbox'])
    try:
        for width in widths:
            page = browser.new_page(viewport={"width": width, "height": 780}, device_scale_factor=1)
            page.route("https://**/*", lambda route: route.abort())
            page.set_content(html, wait_until="domcontentloaded")
            page.evaluate("document.querySelector('#mrxp-launch-overlay')?.remove()")
            page.evaluate("""() => {for(const tab of document.querySelectorAll('.nav .tab .ico')) {const im=document.createElement('img');im.alt='';tab.append(im)}}""")
            page.evaluate("""(src) => {
                const row = document.createElement('div');
                row.className = 'mission';
                row.innerHTML = '<div class="empty-icon"></div>' +
                  '<div class="mission-body"><h4>Abonnement au canal football</h4>' +
                  '<p>Mission confirmée après vérification. Récompense obtenue.</p>' +
                  '<p class="mrxp-inline-status">Récompense obtenue</p>' +
                  '<div class="progress"><span style="width:100%"></span></div></div>' +
                  '<span class="reward"><img class="mrxp-v2-icon mrxp-mission-reward-check" alt="" />+10 XP</span>';
                row.querySelector('.reward img').src=src;
                document.querySelector('#missions-list').append(row);
                const daily=document.createElement('div');
                daily.className='mission mrxp-daily-mission';
                daily.innerHTML='<div class="mission-body"><h4>Bonus quotidien confirmé</h4><p>Récompense confirmée</p></div><span class="reward">+100 XP</span>';
                document.querySelector('#missions-list').append(daily);
                const promo=document.createElement('div');
                promo.className='mrxp-promo mrxp-promo-refined';
                promo.innerHTML='<img alt=""><span class="mrxp-promo-copy"><strong>Gagne des XP Points</strong><small>Progresse et débloque de nouveaux rangs.</small></span>';
                document.querySelector('#screen-tap').append(promo);
                document.querySelector('#mrxp-share-actions').hidden=false;
            }""", big_icon)
            for screen in screens:
                page.evaluate("""screen => {
                    document.querySelectorAll('.section').forEach(el=>el.classList.remove('current'));
                    document.getElementById(screen).classList.add('current');
                    window.scrollTo(0,0);
                }""", screen)
                page.wait_for_timeout(30)
                geom = page.evaluate("""() => ({
                    viewport: innerWidth,
                    rootWidth: document.documentElement.scrollWidth,
                    bodyWidth: document.body.scrollWidth,
                    appWidth: document.querySelector('.app').getBoundingClientRect().width
                })""")
                assert geom["rootWidth"] <= width + 2, f"Root overflow at {width}px {screen}: {geom}"
                assert geom["bodyWidth"] <= width + 2, f"Body overflow at {width}px {screen}: {geom}"
                if screen == "screen-missions":
                    parts = page.evaluate("""() => {
                      const row=document.querySelector('#missions-list .mission');
                      const icon=row.querySelector('.reward img');
                      const body=row.querySelector('.mission-body').getBoundingClientRect();
                      const reward=row.querySelector('.reward').getBoundingClientRect();
                      const pictogram=row.querySelector('.empty-icon').getBoundingClientRect();
                      const panel=row.getBoundingClientRect();
                      const banner=document.querySelector('#screen-missions>.banner').getBoundingClientRect();
                      return {iconW:icon.getBoundingClientRect().width,
                              iconH:icon.getBoundingClientRect().height,
                              textRight:body.right,rewardLeft:reward.left,
                              pictogramW:pictogram.width,
                              panelRight:panel.right,bannerRight:banner.right,
                              bannerButton:document.querySelector('#screen-missions>.banner .small-button').getBoundingClientRect().right};
                    }""")
                    assert parts["iconW"] <= 18 and parts["iconH"] <= 18, f"Giant reward icon: {width}: {parts}"
                    assert parts["pictogramW"] <= 38, f"Giant mission icon: {width}: {parts}"
                    assert parts["textRight"] <= parts["rewardLeft"] + 2, f"Text covers reward: {width}: {parts}"
                    assert parts["panelRight"] <= width + 1, f"Mission panel out of screen: {width}: {parts}"
                    assert parts["bannerRight"] <= width + 1 and parts["bannerButton"] <= width + 1, f"NFT banner overflow: {width}: {parts}"
                elif screen == "screen-profile":
                    panel = page.evaluate("""() => {
                       const x=document.querySelector('#mrxp-share-actions');
                       const art=document.querySelector('.mrxp-profile-hero-art');
                       const face=document.querySelector('#avatar').getBoundingClientRect();
                       const shield=document.querySelector('#mrxp-rank-badge').getBoundingClientRect();
                       const stars=document.querySelector('#mrxp-rank-stars').getBoundingClientRect();
                       const heading=document.querySelector('#profile-name').getBoundingClientRect();
                       const pct=document.querySelector('#mrxp-progress-percent');
                       const track=document.querySelector('.mrxp-v2-progress-track').getBoundingClientRect();
                       const pill=pct.getBoundingClientRect();
                       return {actionsRight:x.getBoundingClientRect().right,
                               artWidth:art.getBoundingClientRect().width, faceRight:face.right,
                               shieldLeft:shield.left, starsRight:stars.right,
                               faceBottom:face.bottom,headingTop:heading.top,
                               pillRight:pill.right,pillWidth:pill.width,
                               progressBackground:getComputedStyle(pct).backgroundImage,
                               trackRight:track.right,
                               progressTitle:document.querySelector('.mrxp-progression-card .section-title').textContent.trim()};
                    }""")
                    assert panel["actionsRight"] <= width + 1, f"Share controls overflow: {width}: {panel}"
                    assert panel["faceRight"]+8 <= panel["shieldLeft"], f"Portrait and rank shield touch: {width}: {panel}"
                    assert panel["faceBottom"] <= panel["headingTop"] + 1, f"Avatar overlaps player name: {width}: {panel}"
                    assert panel["pillWidth"] < 80 and panel["pillRight"] <= width + 1, f"Progress percentage does not fit: {width}: {panel}"
                    assert panel["progressBackground"] == "none", f"Decorative ring still overlaps percent: {width}: {panel}"
                    assert panel["progressTitle"] == "MA PROGRESSION", f"Technical jargon still in public progress: {panel}"
                elif screen == "screen-tap":
                    banner = page.evaluate("""() => {
                      const el=document.querySelector('#wheel-shortcut');
                      const c=el.querySelector('.small-button').getBoundingClientRect();
                      const d=el.getBoundingClientRect();
                      const wheel=el.querySelector('.banner-visual').getBoundingClientRect();
                      const title=el.querySelector('h3').getBoundingClientRect();
                      const promo=document.querySelector('.mrxp-promo-refined');
                      const promoTitle=promo.querySelector('strong');
                      const titleBounds=promoTitle.getBoundingClientRect();
                      const titleStyle=getComputedStyle(promoTitle);
                      return {cardRight:d.right,buttonRight:c.right,buttonBottom:c.bottom,cardBottom:d.bottom,
                              wheelBottom:wheel.bottom,buttonTop:c.top,
                              titleRight:title.right,promoRight:promo.getBoundingClientRect().right,
                              promoTitleRight:titleBounds.right,promoTitleWidth:titleBounds.width,
                              promoTitleScrollWidth:promoTitle.scrollWidth,
                              whiteSpace:titleStyle.whiteSpace};
                    }""")
                    assert banner["buttonRight"] <= width + 1 and banner["buttonBottom"] <= banner["cardBottom"] + 1, f"Lucky Wheel overflow: {width}: {banner}"
                    assert banner["buttonTop"] >= banner["wheelBottom"] - 2, f"Play button beside wheel, should be below: {width}: {banner}"
                    assert banner["whiteSpace"] == "nowrap", f"XP headline wraps: {width}: {banner}"
                    assert banner["promoTitleScrollWidth"] <= banner["promoTitleWidth"] + 2, f"XP title clipped: {width}: {banner}"
                    assert banner["promoRight"] <= width + 1, f"XP promo overflows: {width}: {banner}"
                if screen in ("screen-tap","screen-wheel","screen-profile"):
                    nav=page.evaluate("""() => {
                       const root=document.querySelector('.nav');
                       const tabs=Array.from(document.querySelectorAll('.nav .tab'));
                       return {background:getComputedStyle(root).backgroundColor,
                               tabs:tabs.map(t=>({width:t.getBoundingClientRect().width,
                                                   labelWidth:t.scrollWidth,
                                                   iconWidth:t.querySelector('.ico').getBoundingClientRect().width,
                                                   right:t.getBoundingClientRect().right}))};
                    }""")
                    assert len(nav["tabs"])==5
                    assert all(x["right"]<=width+1 and x["labelWidth"]<=x["width"]+2 for x in nav["tabs"]),f"Bottom navigation overflow at {width}: {nav}"
                    assert all(x["iconWidth"]<=35 for x in nav["tabs"]),f"Oversized navbar icons: {width}: {nav}"
            print(f"PASS {width}px: all {len(screens)} screens, giant icon and button overflow guards")
            page.close()
    finally:
        browser.close()
print("SUCCESS: Phase 1 + 2 + 3 mobile layout checks passed at all widths")
