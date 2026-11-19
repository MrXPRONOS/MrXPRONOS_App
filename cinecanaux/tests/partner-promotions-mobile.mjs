import {chromium} from 'playwright';
import assert from 'node:assert/strict';
const url='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app';
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
const errors=[];
page.on('pageerror',e=>errors.push(String(e.message||e).slice(0,200)));
try{
 const r=await page.goto(url,{waitUntil:'domcontentloaded',timeout:25000});
 assert.equal(r?.status(),200);
 const promo=page.locator('#cine-home-picks .cine-promo-slot');
 await promo.waitFor({state:'visible',timeout:18000});
 await page.waitForTimeout(2800);
 await page.evaluate(()=>document.querySelector("#cine-home-picks .cine-promo-slot")?.scrollIntoView({block:"center",inline:"center"}));
 await page.waitForTimeout(2600);
 const state=await page.evaluate(()=>{
  const root=document.querySelector('#cine-home-picks');
  const children=[...root.children];
  const index=children.findIndex(c=>c.classList.contains('cine-promo-slot'));
  const promo=children[index],cards=[...promo.querySelectorAll('.cine-promo-card')];
  return {
   index,precedingChannels:children.slice(0,index).filter(c=>c.classList.contains('cine-pick')).length,
   followingChannels:children.slice(index+1).filter(c=>c.classList.contains('cine-pick')).length,
   cardCount:cards.length,
   urls:cards.map(c=>c.href),
   names:cards.map(c=>c.querySelector('.cine-promo-name')?.textContent||''),
   descriptions:cards.map(c=>c.querySelector('.cine-promo-description')?.textContent||''),
   avatars:cards.map(c=>({loaded:c.querySelector('img')?.naturalWidth>0,hasFallback:!!c.querySelector('.cine-promo-avatar')})),
   sectionHeight:Math.round(promo.getBoundingClientRect().height),
   windowWidth:innerWidth,scrollTrackWidth:Math.round(promo.querySelector('.cine-promo-track').scrollWidth),
   scrollClientWidth:Math.round(promo.querySelector('.cine-promo-track').clientWidth),
   label:promo.querySelector('.cine-promo-head')?.textContent,
   promoOtherPlaces:document.querySelectorAll('.cine-promo-slot').length
  };
 });
 console.log('MOBILE_CROSS_PROMO_STATE:',JSON.stringify(state));
 console.log('MOBILE_CROSS_PROMO_JS_ERRORS:',JSON.stringify(errors));
 await page.screenshot({path:'/tmp/cineradar-cross-promo-mobile.png'});
 assert.equal(state.precedingChannels,4,'Promotion should appear after the first four suggestions');
 assert.equal(state.cardCount,3);
 assert.equal(state.promoOtherPlaces,1);
 assert.deepEqual(state.urls,[
  'https://t.me/actufoot_mrxp',
  'https://t.me/ActuCrypto24H',
  'https://t.me/mrxpronosfr'
 ]);
 assert.ok(state.descriptions.every(x=>x.length>8));
 assert.ok(state.label.includes('Promotion'));
 assert.ok(state.sectionHeight<180,'Mobile cross-promotion must remain compact');
 assert.ok(state.scrollTrackWidth>state.scrollClientWidth,'Cards should scroll horizontally on narrow screens');
 assert.ok(state.avatars.every(x=>x.hasFallback),'Avatar fallback must exist for each card');
 assert.ok(state.descriptions[2].length>10);
 assert.equal(errors.length,0);
 console.log('MOBILE_CROSS_PROMO_OK');
}finally{await browser.close()}
