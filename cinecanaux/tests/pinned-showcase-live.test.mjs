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
 assert.equal(embedded.length,data.items.length);
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
  assert.ok(checks.every(x=>x.status===200&&/^image\/(?:jpeg|png|webp)/.test(String(x.type))), 'Every pinned poster must load successfully');
 }
});
