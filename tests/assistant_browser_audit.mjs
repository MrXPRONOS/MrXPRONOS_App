import { chromium } from 'playwright';
import fs from 'node:fs';
const pages=['/','/pronos.html','/historique.html','/bonus.html','/contact.html','/live.html'];
const results=[];
const browser=await chromium.launch({headless:true});
for(const mobile of [false,true]){
 for(const path of pages){
  const ctx=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900}});
  const page=await ctx.newPage();
  const result={path,mobile,consoleErrors:[]};
  page.on('pageerror',err=>result.consoleErrors.push(String(err).slice(0,180)));
  try{
   await page.goto('https://mrxpronos.github.io/MrXPRONOS_App'+path,{waitUntil:'domcontentloaded',timeout:35000});
   await page.waitForTimeout(1900);
   const launcher=page.locator('.assistant-button');
   result.launcher=await launcher.count()>0;
   if(result.launcher){
     await launcher.click({timeout:8000});
     result.open=await page.locator('.assistant-window.open').count()>0;
     result.input=await page.locator('#assistant-input').isVisible();
     result.quickActions=await page.locator('#quick-actions button').allTextContents();
     await page.locator('#assistant-input').fill('Que signifie plus de 2,5 buts ?');
     await page.locator('#assistant-send').click();
     await page.waitForFunction(()=>document.querySelectorAll('.assistant-messages .message.assistant').length>1,{timeout:16000}).catch(()=>{});
     result.response=(await page.locator('.assistant-messages .message.assistant').allTextContents()).slice(-1)[0]?.slice(0,260)||'';
     result.feedbackButtons=await page.locator('.message.assistant .feedback-btn').count();
     result.horizontalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+3);
     await page.locator('.assistant-close').click();
     result.closed=await page.locator('.assistant-window.open').count()===0;
   }
  }catch(error){result.error=String(error).slice(0,250)}
  results.push(result);console.log('BROWSER',JSON.stringify(result));
  await ctx.close();
 }
}
await browser.close();
fs.mkdirSync('assistant-browser-out',{recursive:true});
fs.writeFileSync('assistant-browser-out/results.json',JSON.stringify(results,null,2));
console.log('BROWSER_COMPLETE',results.length);