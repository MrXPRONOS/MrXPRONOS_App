import {chromium} from 'playwright';
const URL='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app';
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
const errors=[],failed=[];
page.on('pageerror',e=>errors.push(String(e.message||e).slice(0,200)));
page.on('requestfailed',r=>failed.push({url:r.url().slice(0,110),reason:String(r.failure()?.errorText||'').slice(0,120)}));
try{
 const response=await page.goto(URL,{waitUntil:'domcontentloaded',timeout:25000});
 console.log('HTML status:',response?.status());
 await page.waitForTimeout(11500);
 const state=await page.evaluate(()=>{
  const selectors=['.hero','.cine-poster-section','.cine-home-search','.cine-quick','#cine-home-picks'];
  const rects=selectors.map(s=>{const e=document.querySelector('#cine-page-accueil '+s);return {selector:s,present:!!e,y:Math.round(e?.getBoundingClientRect()?.top||0),height:Math.round(e?.getBoundingClientRect()?.height||0)}});
  return {posterButtons:document.querySelectorAll('#cine-poster-strip button.cine-film-poster').length,posterNote:document.querySelector('#cine-poster-note')?.textContent,quick:document.querySelector('.cine-quick')?.getBoundingClientRect().height,legacyPanel:document.querySelectorAll('.radar-available').length,rects,strip:document.querySelector('#cine-poster-strip')?.innerHTML.slice(0,500),count:document.querySelector('#count')?.textContent};
 });
 console.log('Mobile browser state:',JSON.stringify(state));
 console.log('Page errors:',JSON.stringify(errors));
 console.log('Failed requests:',JSON.stringify(failed.slice(0,15)));
 await page.screenshot({path:'/tmp/cineradar-mobile.png',fullPage:false});
 if(!response?.ok())throw Error('Homepage unavailable');
 if(state.posterButtons<1)throw Error('Pinned poster cards did not render despite 9 live indexed pins');
 if(state.legacyPanel!==0)throw Error('Deprecated nouveautés panel remains visible');
 if(state.quick>51)throw Error('Mobile category controls still too tall');
 if(!state.rects.every(x=>x.present))throw Error('One or more requested home blocks are missing');
 if(!state.rects.every((x,i)=>i===0||x.y>=state.rects[i-1].y))throw Error('Home blocks are out of order');
 if(errors.length)throw Error('Browser JavaScript errors: '+errors.join(' | '));
 console.log('MOBILE_VISUAL_SMOKE_OK');
}finally{await browser.close()}
