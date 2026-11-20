#!/usr/bin/env python3
"""Phase 4–5: render official square/story Canvas cards and verify compact social/mission UI.
Tests are fully local: synthetic portrait and labels; no Telegram tokens or API writes.
"""
import base64
import json
import re
import shutil
import struct
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "worker.js").read_text(encoding="utf-8")
START = SRC.index('const html="') + len('const html="')
END = SRC.index(';\nconst page', START)
HTML = json.loads(SRC[START:END])
SHARE_START = HTML.index("function mrxpCanvasRound(")
SHARE_END = HTML.index("function mrxpCanvasBlob(", SHARE_START)
SHARE_JS = HTML[SHARE_START:SHARE_END]
STATIC_HTML = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", HTML, flags=re.I)

WIDTHS = (320, 360, 375, 390, 430)
OUT = ROOT / "tests" / "visual-previews-phase45"
OUT.mkdir(exist_ok=True)

def rect_check(r, width, what):
    assert r["width"] > 1 and r["left"] >= -1 and r["right"] <= width+1, (
        f"{what}: viewport={width} bounds={r}")

with sync_playwright() as p:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    browser = p.chromium.launch(headless=True, executable_path=executable if executable else None, args=["--no-sandbox"])
    try:
        for width in WIDTHS:
            page = browser.new_page(viewport={"width":width,"height":800},device_scale_factor=1)
            page.route("https://**/*", lambda route: route.abort())
            page.set_content(STATIC_HTML,wait_until="domcontentloaded")
            page.evaluate("document.querySelector('#mrxp-launch-overlay')?.remove()")
            page.evaluate("""() => {
              const goals=document.querySelector('#mrxp-credit-daily-goals');
              goals.innerHTML=Array.from({length:3},(_,i)=>'<div class="mrxp-credit-goal">' +
                 '<span><span class="mrxp-pending-dot"></span>'+['Bonus quotidien','Roue confirmée','50 tapotages synchronisés'][i]+'</span>' +
                 '<strong>+5 MRXP</strong></div>').join('');
              const weekly=document.querySelector('#mrxp-credit-weekly');
              weekly.innerHTML='<span class="mrxp-weekly-caption">Bonus semaine : 2 / 4 jours confirmés · +30 MRXP</span>' +
                 '<span class="mrxp-weekly-track"><span style="width:50%"></span></span>';
              document.querySelector('#missions-list').innerHTML=
                '<div class="mission"><div class="empty-icon"></div><div class="mission-body"><h4>Abonne-toi au canal football</h4>' +
                '<p>Abonnement confirmé, récompense validée par le serveur.</p>' +
                '<p class="mrxp-inline-status">Récompense obtenue</p></div>' +
                '<span class="reward"><img class="mrxp-mission-reward-check" alt="">+10 XP</span></div>';
              document.querySelector('#mrxp-share-actions').hidden=false;
              document.querySelector('#mrxp-share-preview').dataset.ready='yes';
            }""")
            for screen in ("screen-friends","screen-missions","screen-profile"):
                page.evaluate("""id => {
                  document.querySelectorAll('.section').forEach(el=>el.classList.toggle('current',el.id===id));
                  window.scrollTo(0,0);
                }""",screen)
                data=page.evaluate("""() => {
                  const r = node => {const b=node.getBoundingClientRect();return {left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width,height:b.height}};
                  return {
                    scroll:document.documentElement.scrollWidth,
                    body:document.body.scrollWidth,
                    friends:document.querySelector('#screen-friends').classList.contains('current')?{
                      card:r(document.querySelector('.mrxp-friends-card')),
                      share:r(document.querySelector('#share-button')),
                      copy:r(document.querySelector('#mrxp-friends-copy')),
                      grid:getComputedStyle(document.querySelector('.mrxp-friends-actions')).gridTemplateColumns,
                      oldDashboard:document.querySelector('#screen-friends').textContent.includes('TABLEAU DE BORD')
                    }:null,
                    missions:document.querySelector('#screen-missions').classList.contains('current')?{
                      goals:Array.from(document.querySelectorAll('.mrxp-credit-goal')).map(r),
                      reward:r(document.querySelector('#missions-list .reward img')),
                      wallet:r(document.querySelector('#screen-missions .mrxp-credit-card')),
                      legends:r(document.querySelector('.mrxp-legends-teaser')),
                      legendButton:r(document.querySelector('.mrxp-legends-teaser .small-button')),
                      legendArt:r(document.querySelector('.mrxp-legends-teaser .banner-visual')),
                      weekly:r(document.querySelector('#mrxp-credit-weekly .mrxp-weekly-track'))
                    }:null,
                    profile:document.querySelector('#screen-profile').classList.contains('current')?{
                      panel:r(document.querySelector('#screen-profile .mrxp-share-panel')),
                      title:r(document.querySelector('#screen-profile .mrxp-share-panel h3')),
                      create:r(document.querySelector('#mrxp-share-create')),
                      camera:Array.from(document.querySelectorAll('#screen-profile .mrxp-camera-icon')).map(r),
                      controls:Array.from(document.querySelectorAll('#mrxp-share-actions button')).map(r)
                    }:null
                  };
                }""")
                assert data["scroll"] <= width+2 and data["body"] <= width+2, (width,screen,data)
                if screen=="screen-friends":
                    friend=data["friends"]
                    assert not friend["oldDashboard"],"Old fake friend statistics still shown"
                    for k in ("card","share","copy"):rect_check(friend[k],width,"Friends "+k)
                    if width<=350:assert friend["copy"]["top"] >= friend["share"]["bottom"]-2,(width,friend)
                elif screen=="screen-missions":
                    mission=data["missions"]
                    for k in ("wallet","legends","legendButton","weekly"):rect_check(mission[k],width,"Missions "+k)
                    assert mission["reward"]["width"]<=18 and mission["reward"]["height"]<=18,(width,mission)
                    assert mission["legendButton"]["top"]>=mission["legendArt"]["bottom"]-2,(width,mission)
                    for goal in mission["goals"]:rect_check(goal,width,"Daily MRXP goal")
                else:
                    profile=data["profile"]
                    for k in ("panel","title","create"):rect_check(profile[k],width,"Profile "+k)
                    assert len(profile["camera"])==2
                    assert all(i["width"]<=25 for i in profile["camera"]),(width,profile)
                    assert all(i["right"]<=width+1 for i in profile["controls"]),(width,profile)
                if width==375:
                    page.screenshot(path=str(OUT/(screen+"-375.png")),full_page=False)
            print(f"PASS {width}px: Friends, Missions, Share panel: no horizontal overflow or misleading content")
            page.close()

        page=browser.new_page(viewport={"width":430,"height":860})
        page.set_content("<html><body></body></html>")
        page.add_script_tag(content=SHARE_JS)
        results=page.evaluate("""async () => {
          const source=document.createElement('canvas');source.width=560;source.height=560;
          const k=source.getContext('2d');
          k.fillStyle='#2e72ad';k.fillRect(0,0,560,560);
          k.fillStyle='#f1c56d';k.beginPath();k.arc(280,248,130,0,Math.PI*2);k.fill();
          k.fillStyle='#0b2450';k.fillRect(144,380,272,160);
          k.fillStyle='#fff';k.font='900 50px system-ui';k.textAlign='center';k.fillText('MX',280,460);
          const im=new Image();im.src=source.toDataURL('image/png');await im.decode();
          const badgeCanvas=document.createElement('canvas');badgeCanvas.width=150;badgeCanvas.height=150;
          const bc=badgeCanvas.getContext('2d');bc.fillStyle='#f2c66d';bc.fillRect(0,0,150,150);
          bc.fillStyle='#06172e';bc.font='900 60px system-ui';bc.textAlign='center';bc.fillText('MX',75,99);
          const official=new Image();official.src=badgeCanvas.toDataURL('image/png');await official.decode();
          im.mrxpOfficialBadge=official;
          const data={display_name:'Monsieur XPRONOS — Joueur MRXP confirmé au long pseudonyme',
           level:37,rank:'Légende',xp:123456789,missions:42,mastery:29,issued_ms:1795147200000};
          const original=CanvasRenderingContext2D.prototype.fillText, records=[];
          CanvasRenderingContext2D.prototype.fillText=function(value,x,y,maxWidth){
             records.push({value:String(value),x,y,maxWidth:maxWidth??0,font:this.font});
             return original.apply(this,arguments);
          };
          const out=[];
          try{
            for(const vertical of [false,true]){
               records.length=0;
               const card=mrxpDrawShareImage(data,vertical,im);
               const png=card.toDataURL('image/png');
               out.push({vertical,width:card.width,height:card.height,png,
                 labels:records.map(x=>({...x})),middle:records.filter(x=>x.value.includes('NIVEAU')||x.value.includes('CONFIRMÉS')),
                 ends:records.filter(x=>x.value.startsWith('@MrXpronos'))});
            }
          }finally{CanvasRenderingContext2D.prototype.fillText=original}
          return out;
        }""")
        for card in results:
            label="story" if card["vertical"] else "square"
            expectHeight=1920 if card["vertical"] else 1080
            assert (card["width"],card["height"])==(1080,expectHeight),label
            raw=base64.b64decode(card["png"].split(",",1)[1])
            assert raw[:8]==b'\x89PNG\r\n\x1a\n',label
            assert struct.unpack(">II",raw[16:24])==(1080,expectHeight),label
            assert len(raw)>20000,(label,len(raw))
            assert len(card["ends"])==1,label
            for item in card["labels"]:
                assert 20 < item["y"] < expectHeight-28,(label,item)
            assert sum(1 for x in card["labels"] if x["value"].startswith("NIVEAU "))==1,label
            assert sum(1 for x in card["labels"] if x["value"]=="XP CONFIRMÉS")==1,label
            assert card["ends"][0]["y"]<expectHeight-35,label
            path=OUT/("official-"+label+"-1080x"+str(expectHeight)+".png")
            path.write_bytes(raw)
            print(f"PASS official {label} PNG: 1080x{expectHeight}, {len(raw)} bytes, {len(card['labels'])} separated text labels")
        page.close()
    finally:
        browser.close()
print("SUCCESS phase 4-5: actual Canvas PNG exports and 15 responsive page checks")
