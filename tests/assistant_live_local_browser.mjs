import {chromium} from 'playwright';
const browser=await chromium.launch({headless:true});
for(const mobile of [false,true]){
 const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900}});
 const page=await context.newPage();
 const errors=[]; page.on('pageerror',e=>errors.push(String(e).slice(0,150)));
 await page.goto('http://127.0.0.1:8765/live.html',{waitUntil:'domcontentloaded',timeout:40000});
 await page.locator('.assistant-button').waitFor({timeout:30000});
 await page.locator('.assistant-button').click();
 await page.locator('.assistant-window.open').waitFor({timeout:7000});
 await page.route('**/functions/v1/assistant',async route=>{
  await route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify({answer:'<p>Réponse test interface LIVE.</p>',from_cache:false})});
 });
 await page.locator('#assistant-input').fill('Message de test sur le LIVE');
 await page.locator('#assistant-send').click();
 await page.getByText('Réponse test interface LIVE.').waitFor({timeout:12000});
 const horizontal=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+3);
 const out={mobile,launcher:true,response:true,horizontalOverflow:horizontal,errors};
 console.log('LIVE_FRONTEND_QA '+JSON.stringify(out));
 if(horizontal)throw Error('Horizontal overflow in assistant');
 await context.close();
}
await browser.close();