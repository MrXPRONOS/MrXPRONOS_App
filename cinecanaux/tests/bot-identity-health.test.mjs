import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker.mjs';

test('health probe identifies the server-side Telegram bot without exposing its token',async()=>{
 const old=globalThis.fetch;
 const env={TELEGRAM_TOKEN:'123456:TEST_SECRET',DB:{prepare(){return {async first(){return {webhook:'ok',n:70}}}}}};
 let calls=0;
 globalThis.fetch=async url=>{
  calls++;
  assert.equal(String(url),'https://api.telegram.org/bot123456:TEST_SECRET/getMe');
  return Response.json({ok:true,result:{id:123456,username:'CineRadarFr_Bot'}});
 };
 try{
  const r=await worker.fetch(new Request('https://cinecanaux.test/health?telegram=1'),env);
  assert.equal(r.status,200);
  const body=await r.json();
  assert.equal(body.botIdentity.connected,true);
  assert.equal(body.botIdentity.matchesExpected,true);
  assert.equal(body.botIdentity.username,'CineRadarFr_Bot');
  assert.ok(!JSON.stringify(body).includes('123456:TEST_SECRET'));
  const r2=await worker.fetch(new Request('https://cinecanaux.test/health?telegram=1'),env);
  assert.equal((await r2.json()).botIdentity.matchesExpected,true);
  assert.equal(calls,1,'Bot API checks are cached in the Worker isolate');
  const normal=await worker.fetch(new Request('https://cinecanaux.test/health'),env);
  assert.ok(!Object.hasOwn(await normal.json(),'botIdentity'),'Normal health remains unchanged');
 }finally{globalThis.fetch=old}
});