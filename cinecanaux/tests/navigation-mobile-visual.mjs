import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {APP_HTML} from '../app-page.mjs';

// This test checks what the mobile user actually sees and can tap.
// It intentionally loads production, not a mocked HTML string.
const URL='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app';
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
const errors=[];
const source=process.env.CINERADAR_VISUAL_SOURCE||'candidate';
if(source==='candidate'){
 // Test the PR's HTML before it is deployed; same public data API and assets.
 await page.route('**/app',route=>route.fulfill({status:200,contentType:'text/html',body:APP_HTML}));
}
console.log('NAVIGATION_VISUAL_SOURCE',source);
page.on('pageerror',e=>errors.push(String(e.message||e)));
async function state(stage){
 const snapshot=await page.evaluate((stage)=>{
  const vis=el=>!!el&&getComputedStyle(el).display!=='none'&&!el.closest('[hidden]')&&el.getBoundingClientRect().width>0;
  const names=['Accueil','Explorer','Favoris','Menu'];
  const bar=document.querySelector('.cine-bottom-nav');
  const tabs=[...bar?.querySelectorAll('button')||[]];
  const panelNames=['accueil','explorer','favoris','historique'];
  const panels=Object.fromEntries(panelNames.map(name=>{
   const el=document.querySelector('#cine-page-'+name);
   return [name,{exists:!!el,hidden:el?.hidden,visible:vis(el),length:el?.textContent?.trim().length||0}];
  }));
  return {stage,href:location.href,brand:!!document.querySelector('main.page .brand'),hero:!!document.querySelector('main.page .hero'),tabsRoot:!!document.querySelector('#tabs'),search:!!document.querySelector('label.search'),tools:!!document.querySelector('main.page .v2-tools'),heading:!!document.querySelector('main.page .heading'),cards:!!document.querySelector('#cards'),footer:!!document.querySelector('main.page .footer'),bottomBar:vis(bar),tabs:tabs.map(e=>({label:e.textContent.trim(),visible:vis(e),width:Math.round(e.getBoundingClientRect().width)})),
   panels,homeHero:vis(document.querySelector('#cine-page-accueil .cine-hero')),
   explorerSearch:vis(document.querySelector('#cine-page-explorer .cine-home-search, #cine-page-explorer label.search')),
   explorerCards:document.querySelectorAll('#cine-page-explorer article[data-channel-id]:not([hidden])').length,
   favoritesText:document.querySelector('#cine-page-favoris')?.textContent?.slice(0,150)};
 },stage);
 console.log('NAVIGATION_VISUAL_STATE',JSON.stringify(snapshot));
 console.log('NAVIGATION_BROWSER_ERRORS',JSON.stringify(errors));
 await page.screenshot({path:'/tmp/cineradar-navigation-'+stage+'.png',fullPage:false});
 return snapshot;
}
try{
 const response=await page.goto(URL,{waitUntil:'domcontentloaded',timeout:25000});
 assert.equal(response?.status(),200,'App must load');
 await page.waitForTimeout(3500);
 let s=await state('home');
 assert.equal(s.bottomBar,true,'Bottom navigation must be visible on first load');
 for(const label of ['Accueil','Explorer','Favoris','Menu'])assert.ok(s.tabs.find(x=>x.label===label&&x.visible),'Missing mobile tab: '+label);
 assert.equal(s.panels.accueil.visible,true,'Accueil panel must show on first load');
 await page.locator('.cine-bottom-nav button').filter({hasText:'Explorer'}).click();
 await page.waitForTimeout(600);
 s=await state('explorer');
 assert.equal(s.panels.explorer.visible,true,'Explorer panel is not visible after tap');
 assert.equal(s.panels.accueil.visible,false,'Accueil should hide after Explorer');
 assert.equal(s.explorerSearch,true,'Explorer search is missing');
 assert.ok(s.explorerCards>0,'Explorer must display at least one real channel');
 await page.locator('.cine-bottom-nav button').filter({hasText:'Favoris'}).click();
 await page.waitForTimeout(400);
 s=await state('favorites');
 assert.equal(s.panels.favoris.visible,true,'Favorites panel is not visible');
 await page.locator('.cine-bottom-nav button').filter({hasText:'Accueil'}).click();
 await page.waitForTimeout(400);
 s=await state('back-home');
 assert.equal(s.panels.accueil.visible,true,'Accueil is not restored after navigation');
 await page.locator('.cine-bottom-nav button').filter({hasText:'Menu'}).click();
 await page.waitForTimeout(200);
 const drawer=await page.locator('.cine-drawer').isVisible();
 assert.equal(drawer,true,'The menu button is not usable');
 console.log('NAVIGATION_VISUAL_ERRORS',JSON.stringify(errors));
 assert.deepEqual(errors,[],'Unexpected browser JS errors');
 console.log('NAVIGATION_MOBILE_VISUAL_OK');
}finally{await browser.close();}
