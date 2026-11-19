import test from 'node:test';
import assert from 'node:assert/strict';
const ORIGIN='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
const EXPECTED=['actufoot_mrxp','ActuCrypto24H','mrxpronosfr'];
test('live cross-promotion API returns three user-authorized channels with actual public metadata',async()=>{
 const r=await fetch(ORIGIN+'/api/partner-promos',{signal:AbortSignal.timeout(25000)});
 assert.equal(r.status,200);
 const data=await r.json();
 assert.deepEqual(data.items.map(c=>c.handle),EXPECTED);
 for(const item of data.items){
  assert.equal(item.url,'https://t.me/'+item.handle);
  assert.ok(item.name.length>1);
  assert.ok(item.description.length>7);
  assert.equal(item.avatar,'/assets/promo-avatar/'+item.handle+'.jpg');
 }
 console.log('Live partner titles/descriptions:',JSON.stringify(data.items.map(x=>({handle:x.handle,title:x.name,description:x.description.slice(0,105)}))));
});
test('all three real Telegram avatar proxy URLs respond with actual image bytes',async()=>{
 const results=await Promise.all(EXPECTED.map(async handle=>{
  const res=await fetch(ORIGIN+'/assets/promo-avatar/'+handle+'.jpg',{signal:AbortSignal.timeout(20000)});
  const body=res.status===200?new Uint8Array(await res.arrayBuffer()):null;
  const error=res.status===200?'':(await res.text()).slice(0,80);
  return {handle,status:res.status,mime:res.headers.get('content-type'),size:body?.length||0,error};
 }));
 console.log('Live partner avatar checks:',JSON.stringify(results));
 assert.ok(results.every(x=>x.status===200&&/^image\/(?:jpeg|png|webp)$/.test(String(x.mime))&&x.size>20),'All three promotional channels need a verified profile photo');
});
