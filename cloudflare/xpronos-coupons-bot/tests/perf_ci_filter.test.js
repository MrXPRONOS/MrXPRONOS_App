import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';

test('Production smoke probes are excluded from regional user measurements',async()=>{
 let writes=0;
 const env={DB:{prepare:()=>({bind:()=>({run:async()=>{writes++;return {}}})})}};
 const promises=[];
 const ctx={waitUntil:p=>promises.push(p)};
 for(const ua of ['FreePronos-Production-SmokeTest/1.0','FreePronos-Latency-Audit/1.0']){
  const r=await worker.fetch(new Request('https://worker.test/api/me',{headers:{'user-agent':ua}}),env,ctx);
  assert.equal(r.status,401);
 }
 await Promise.all(promises);
 assert.equal(promises.length,0);
 assert.equal(writes,0);
});
test('Real Telegram Mini App request is sampled without storing personal headers',async()=>{
 const captured=[];const promises=[];
 const env={DB:{prepare:sql=>({bind:(...args)=>({run:async()=>{captured.push({sql,args});return {}}})})}};
 const req=new Request('https://worker.test/api/me',{headers:{'user-agent':'Telegram-Android/11'}});
 const r=await worker.fetch(req,env,{waitUntil:p=>promises.push(p)});
 assert.equal(r.status,401);
 await Promise.all(promises);
 assert.equal(captured.length,1);
 assert.deepEqual(captured[0].args.slice(0,3),['miniapp','/me','UNK']);
 assert.equal(captured[0].args.includes('Telegram-Android/11'),false);
});
