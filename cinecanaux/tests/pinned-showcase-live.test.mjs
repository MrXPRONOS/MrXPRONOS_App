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
 for(const item of data.items){
  assert.match(item.link,/^https:\/\/t\.me\/(?:CineXFilms_vf|seriesvf_cinex|CineXAnimeFR)\/[1-9][0-9]{0,12}$/i);
  assert.match(item.poster,/^\/assets\/pin-cover\/(films|series|animes)\/[1-9][0-9]{0,12}\.jpg$/);
  assert.ok(item.title);
 }
 if(data.items.length){
  const img=await fetch(ORIGIN+data.items[0].poster,{signal:AbortSignal.timeout(14000)});
  console.log('First pinned thumbnail status:',img.status,'type:',img.headers.get('content-type'));
  assert.equal(img.status,200);
  assert.match(String(img.headers.get('content-type')), /^image\/(?:jpeg|png|webp)/);
  await img.body?.cancel();
 }
});
