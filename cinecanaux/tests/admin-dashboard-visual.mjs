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
 pins:{items:[{kind:"films",message_id:123,title:"Affiche de test",active:true,source:"owner",url:"https://t.me/ExempleFilmVF/123"}]},
 "channel-list":{channels:[
  {id:12,title:"Films VF",link:"https://t.me/ExempleFilmVF",description:"Cinéma français",content_type:"films",genre:"general",language:"VF",status:"approved",listing_status:"listed"},
  {id:13,title:"Animés Manga",link:"https://t.me/AnimeExempleVF",description:"Animés japonais",content_type:"animes",genre:"action",language:"VOSTFR",status:"approved",listing_status:"hidden"}
 ]},
 "launch-funnel":{counts:{bot_starts:12,app_opens:7}},
 operations:{alerts:[{title:"Contrôle de test",detail:"Une tâche nécessite une vérification"}],jobs:[{job_name:"link_check",status:"ok",started_at:"2026-11-20",errors:0}],actions:[{action:"channel.update",target:"12",created_at:"2026-11-20"}],checked_at:new Date().toISOString()}
};
const origin='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
async function run(viewport,device){
 const page=await browser.newPage({viewport,isMobile:device,hasTouch:device});
 const posted=[];
 page.on('pageerror',e=>errors.push(String(e.message||e)));
 page.on('dialog',dialog=>dialog.accept());
 await page.route('https://telegram.org/js/**',r=>r.fulfill({status:200,contentType:'text/javascript',body:"window.Telegram={WebApp:{initData:'browser-test-signed',ready(){},expand(){}}}"}));
 await page.route('**/admin',r=>r.fulfill({status:200,contentType:'text/html; charset=utf-8',body:ADMIN_HTML}));
 await page.route('**/api/admin/**',r=>{
  const path=new URL(r.request().url()).pathname.split('/').at(-1);
  if(r.request().method()==='POST'){
   const data=JSON.parse(r.request().postData()||'{}');
   posted.push({path,data});
   return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,id:44})});
  }
  return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(datasets[path]||{})});
 });
 await page.route('**/assets/pin-cover/**',r=>r.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jkXcAAAAASUVORK5CYII=','base64')}));
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
  await page.locator('#ad-nav-close').click();
 }
 for(const [id,target] of steps){
  if(device)await page.locator('#ad-menu-toggle').click();
  await page.locator('#ad-nav [data-admin-go="'+id+'"]').click();
  assert.equal(await page.locator('#ad-view-'+id).isVisible(),true,'Expected view '+id);
  assert.equal(await page.locator(target).count()>0,true,'Legacy module missing '+target);
  if(id==='channels'){
   await page.waitForFunction(()=>document.querySelector('#ad-channel-list')?.querySelectorAll('.ad-channel-card').length===2);
   await page.locator('#ad-channel-search').fill('Manga');
   assert.equal(await page.locator('#ad-channel-list .ad-channel-card').count(),1,'Search must filter channels');
   await page.locator('#ad-channel-search').fill('');
   await page.locator('#ad-channel-create').click();
   assert.equal(await page.locator('#ad-channel-form').isVisible(),true,'New channel form must open');
   await page.locator('#ad-channel-title').fill('Cinéma test validé');
   await page.locator('#ad-channel-link').fill('https://t.me/FilmTestVF');
   await page.locator('#ad-channel-rights').check();
   await page.locator('#ad-channel-save').click();
   await page.waitForFunction(()=>document.querySelector('#ad-channel-message')?.textContent?.includes('enregistré'));
   assert.ok(posted.some(p=>p.path==='channels'&&p.data.action==='add'&&p.data.rights_confirmed===true),'Creating channel must use owner API and rights acknowledgement');
  }
  if(id==='pins'){
   await page.waitForFunction(()=>document.querySelector('#owner-pins-items')?.querySelector('.ad-pin-thumb'));
   assert.equal(await page.locator('#ad-view-pins .ad-pin-thumb').count(),1,'Pinned poster gallery must render a thumbnail');
  }
  if(id==='broadcast'){
   await page.locator('#broadcast-text').fill('Bonjour Ciné Radar');
   await page.locator('#broadcast-save').click();
   await page.waitForFunction(()=>!document.querySelector('#broadcast-preview-send')?.disabled);
   const date=new Date(Date.now()+3600000);
   const inputDate=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
   await page.locator('#broadcast-schedule-at').fill(inputDate);
   await page.locator('#broadcast-schedule').click();
   await page.waitForFunction(()=>document.querySelector('#ad-broadcast-schedule-status')?.textContent?.includes('programmée'));
   assert.ok(posted.some(p=>p.path==='schedule'&&p.data.send_at?.endsWith('Z')),'Broadcast must schedule with a UTC timestamp');
  }
  if(id==='automations'){
   await page.waitForFunction(()=>document.querySelector('#ad-ops-history')?.querySelector('.ad-ops-row'));
   assert.equal(await page.locator('#ad-ops-alerts .ad-ops-alert').count(),1,'Automation alerts must be visible');
  }
 }
 await page.locator(device?'#ad-bottom-tabs [data-admin-go="dashboard"]':'#ad-nav [data-admin-go="dashboard"]').click();
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
