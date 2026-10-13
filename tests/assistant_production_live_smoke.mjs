import {chromium} from 'playwright';
const root='https://mrxpronos.github.io/MrXPRONOS_App/live.html';
let published=false;
for(let attempt=1;attempt<=10;attempt++){
 const response=await fetch(root+'?assistant_qa50='+Date.now(),{signal:AbortSignal.timeout(10000)});
 const html=await response.text();
 published=response.status===200 && html.includes('assistant.js?v=20261013-qa50-live');
 console.log('PROD_ASSET '+JSON.stringify({attempt,status:response.status,assistantScript:published,htmlBytes:html.length}));
 if(published)break;
 await new Promise(resolve=>setTimeout(resolve,7000));
}
if(!published)throw Error('The published LIVE HTML has not received the assistant integration');
const browser=await chromium.launch();
for(const mobile of [false,true]){
 const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900}});
 const page=await context.newPage();
 await page.goto(root+'?qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:40000});
 await page.locator('.assistant-button').waitFor({timeout:20000});
 await page.locator('.assistant-button').click();
 await page.locator('#assistant-input').fill('Le LIVE est-il gratuit ?');
 await page.locator('#assistant-send').click();
 await page.waitForFunction(()=>Array.from(document.querySelectorAll('.message.assistant .message-content')).some(n=>n.textContent.includes('gratuitement')||n.textContent.includes('gratuit')),{timeout:25000});
 const answer=(await page.locator('.message.assistant .message-content').allTextContents()).slice(-1)[0]||'';
 if(/5[\s.]*000|abonnement VIP payant exigé/i.test(answer))throw Error('Obsolete VIP charge found in actual answer');
 console.log('PROD_BROWSER '+JSON.stringify({mobile,assistantVisible:true,answer:answer.slice(0,290)}));
 await context.close();
}
await browser.close();