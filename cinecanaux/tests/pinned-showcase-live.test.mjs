import test from 'node:test';
import assert from 'node:assert/strict';
const ORIGIN='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
test('pinned showcase is live, uses trusted channel message URLs, and can serve a cover',async()=>{
 const res=await fetch(ORIGIN+'/api/pinned-showcase',{headers:{accept:'application/json'},signal:AbortSignal.timeout(25000)});
 assert.equal(res.status,200);
 const data=await res.json();
 assert.ok(Array.isArray(data.items));
 assert.ok(Number.isInteger(data.total));
 console.log('Pinned showcase live:',data.total,'items; per category:',data.items.reduce((x,p)=>(x[p.type]=(x[p.type]||0)+1,x),{}));
 const home=await fetch(ORIGIN+'/app',{signal:AbortSignal.timeout(15000)});
 assert.equal(home.status,200);
 const html=await home.text();
 const initial=/const PRELOADED_PINS=(\[[^\n]*\]);/.exec(html);
 assert.ok(initial,'Pinned items should be embedded in initial HTML');
 const embedded=JSON.parse(initial[1]);
 // The home page intentionally preloads at most 24 cards, whereas the
 // full pinned-showcase API can return 25 or more. Compare the same window.
 assert.equal(embedded.length,Math.min(24,data.items.length));
 console.log('Initial HTML pin preload:',embedded.length,'cards');
 for(const item of data.items){
  assert.match(item.link,/^https:\/\/t\.me\/(?:CineXFilms_vf|seriesvf_cinex|CineXAnimeFR)\/[1-9][0-9]{0,12}$/i);
  assert.match(item.poster,/^\/assets\/pin-cover\/(films|series|animes)\/[1-9][0-9]{0,12}\.jpg$/);
  assert.ok(item.title);
 }
 if(data.items.length){
  const checks=await Promise.all(data.items.slice(0,24).map(async (item)=>{
   const img=await fetch(ORIGIN+item.poster,{signal:AbortSignal.timeout(14000)});
   const status=img.status,type=img.headers.get('content-type');
   const reason=status!==200?(await img.text()).slice(0,120):'';
   await img.body?.cancel().catch(()=>{});
   return {kind:item.type,id:item.message_id,status,type,reason};
  }));
  console.log('Pinned thumbnail results:',checks);
  // A single Telegram CDN/network outage is not a Worker regression and
  // must not prevent deploying unrelated, fully-tested code. Fail on all
  // other unexpected responses and on widespread network unavailability.
  // The failure remains explicit in CI logs for follow-up.
  const missing=checks.filter(x=>!(x.status===200&&/^image\/(?:jpeg|png|webp)/.test(String(x.type))));
  const unavailable=missing.filter(x=>x.status===503&&x.reason==='Cover unavailable (network_unavailable)');
  assert.ok(missing.length===unavailable.length,
    'Pinned covers must not fail for reasons other than temporary Telegram network unavailability');
  assert.ok(unavailable.length<=1,
    'At most one external Telegram cover may be temporarily unavailable in the smoke window');
  if(unavailable.length)console.warn('EXTERNAL_PIN_COVER_DEGRADED',unavailable);

 }
});
