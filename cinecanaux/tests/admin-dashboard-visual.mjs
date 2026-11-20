import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {ADMIN_HTML} from '../admin-page.mjs';

// Auth is mocked ONLY inside this isolated browser test; production remains
// guarded by the Telegram HMAC/Ed25519 checks and the owner role in D1.
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const errors=[];
const datasets={
 overview:{indexed:70,visible:67,hidden:3,reviews:12,open_reports:2,pending_suggestions:4,checks_24h:22,searches_today:27,empty_searches_today:2},
 reports:{reports:[]},reviews:{reviews:[]},suggestions:{suggestions:[]},jobs:{jobs:[]},
 broadcasts:{subscribers:{total:21,active:17},jobs:[]},
 "radar-ops":{missing:{items:[]},channels:[],digest:"Tendances : test d'interface"},
 pins:{items:[]},
 "launch-funnel":{counts:{bot_starts:12,app_opens:7}}
};
const origin='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
async function run(viewport,device){
 const page=await browser.newPage({viewport,isMobile:device,hasTouch:device});
 page.on('pageerror',e=>errors.push(String(e.message||e)));
 await page.route('https://telegram.org/js/**',r=>r.fulfill({status:200,contentType:'text/javascript',body:"window.Telegram={WebApp:{initData:'browser-test-signed',ready(){},expand(){}}}"}));
 await page.route('**/admin',r=>r.fulfill({status:200,contentType:'text/html; charset=utf-8',body:ADMIN_HTML}));
 await page.route('**/api/admin/**',r=>{
  const path=new URL(r.request().url()).pathname.split('/').at(-1);
  return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(datasets[path]||{})});
 });
 await page.goto(origin+'/admin',{waitUntil:'domcontentloaded',timeout:25000});
 await page.waitForFunction(()=>document.querySelector('#private')?.hidden===false,{timeout:8000});
 assert.equal(await page.locator('#ad-view-dashboard').isVisible(),true,'Dashboard must be visible by default');
 assert.equal(await page.locator('#ad-view-dashboard #stats .metric').count(),8,'Existing summary metrics must remain');
 const steps=[
  ['statistics','#ad-view-statistics .analytics-dashboard'],
  ['users','#ad-view-users #cine-launch-funnel'],
  ['channels','#ad-view-channels #channelId'],
  ['showcase','#ad-view-showcase #radar-ops-refresh'],
  ['pins','#ad-view-pins #owner-pins-items'],
  ['community','#ad-view-community #reports'],
  ['broadcast','#ad-view-broadcast #broadcast-save'],
  ['automations','#ad-view-automations #runChecks'],
  ['branding','#ad-view-branding #bot-brand-sync'],
  ['settings','#ad-view-settings .ad-note']
 ];
 if(device){
  await page.locator('#ad-menu-bottom').click();
  assert.equal(await page.locator('#ad-nav').evaluate(x=>x.classList.contains('ad-open')),true,'Mobile drawer must open');
  await page.screenshot({path:'/tmp/cineradar-admin-v11-menu.png'});
 }
 for(const [id,target] of steps){
  if(device)await page.locator('#ad-menu-toggle').click();
  await page.locator('#ad-nav [data-admin-go="'+id+'"]').click();
  assert.equal(await page.locator('#ad-view-'+id).isVisible(),true,'Expected view '+id);
  assert.equal(await page.locator(target).count()>0,true,'Legacy module missing '+target);
 }
 await page.locator('[data-admin-go="dashboard"]').last().click();
 assert.equal(await page.locator('#ad-view-dashboard').isVisible(),true);
 await page.screenshot({path:'/tmp/cineradar-admin-v11-'+(device?'mobile':'desktop')+'.png'});
 const horizontal=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
 assert.ok(horizontal<8,'Admin screen should not overflow horizontally by '+horizontal+'px');
 await page.close();
}
try{
 await run({width:390,height:844},true);
 await run({width:1280,height:850},false);
 assert.deepEqual(errors,[],'No uncaught browser exceptions');
 console.log('CINE_ADMIN_V11_VISUAL_OK mobile+desktop, all existing modules preserved');
}finally{await browser.close()}
