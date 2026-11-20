import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {allowPublicEvent,publicRateLimited,purgeOldPublicEventBuckets} from '../public-event-limiter.mjs';

function fixture(){
 const sqlite=new DatabaseSync(':memory:');
 sqlite.exec(readFileSync(new URL('../migrations/022_cinex_public_event_buckets.sql',import.meta.url),'utf8'));
 const DB={prepare(sql){
  let args=[];
  return {
   bind(...params){args=params;return this},
   async run(){const r=sqlite.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}}}
  };
 }};
 return {sqlite,env:{DB,TELEGRAM_WEBHOOK_SECRET:'private-test-pepper'}};
}
test('anonymous analytics bucket caps hits atomically without persisting client IP',async()=>{
 const {sqlite,env}=fixture();
 try{
  const request=new Request('https://cine.example/api/analytics/event',{headers:{'CF-Connecting-IP':'203.0.113.17'}});
  for(let i=0;i<10;i++)assert.equal(await allowPublicEvent(env,request,'analytics',{cap:10,now:1763647200000}),true);
  assert.equal(await allowPublicEvent(env,request,'analytics',{cap:10,now:1763647200000}),false);
  assert.equal((await publicRateLimited().json()).error,'Trop de requêtes. Réessaie dans une minute.');
  assert.equal(publicRateLimited().status,429);
  const row=sqlite.prepare('SELECT bucket_hash,hits FROM cine_public_event_buckets').get();
  assert.equal(row.hits,10);
  assert.match(row.bucket_hash,/^[a-f0-9]{64}$/);
  assert.ok(!JSON.stringify(row).includes('203.0.113.17'));
  assert.equal(await allowPublicEvent(env,request,'analytics',{cap:10,now:1763647260000}),true,'Next minute new bucket');
  assert.equal(await allowPublicEvent(env,request,'pin_click',{cap:10,now:1763647200000}),true,'Independent route');
  const other=new Request(request.url,{headers:{'CF-Connecting-IP':'203.0.113.18'}});
  assert.equal(await allowPublicEvent(env,other,'analytics',{cap:10,now:1763647200000}),true,'Independent client');
  sqlite.exec("UPDATE cine_public_event_buckets SET expires_at=datetime('now','-1 minute')");
  assert.equal((await purgeOldPublicEventBuckets(env)).purged,4);
  assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM cine_public_event_buckets').get().n,0);
 }finally{sqlite.close()}
});
test('absent trusted Cloudflare IP, local development and D1 migration gap remain non-blocking',async()=>{
 const {sqlite,env}=fixture();
 try{
  assert.equal(await allowPublicEvent(env,new Request('https://cine.example/api/engagement'),'engagement',{cap:10}),true);
  assert.equal(await allowPublicEvent({DB:env.DB},new Request('https://cine.example',{headers:{'CF-Connecting-IP':'203.0.113.17'}}),'analytics'),true);
  const unavailable={DB:{prepare(){throw Error('not yet installed')}},TELEGRAM_WEBHOOK_SECRET:'pepper'};
  assert.equal(await allowPublicEvent(unavailable,new Request('https://cine.example',{headers:{'CF-Connecting-IP':'203.0.113.17'}}),'analytics'),true);
 }finally{sqlite.close()}
});
test('all public click/analytics/engagement paths call the same capped D1 helper',()=>{
 const root=new URL('../',import.meta.url);
 for(const [file,category] of [
  ['worker.mjs','engagement'],
  ['analytics.mjs','analytics'],
  ['pinned-showcase.mjs','pin_click']]){
  const code=readFileSync(new URL(file,root),'utf8');
  assert.ok(code.includes("allowPublicEvent(env,request,'"+category+"'"),file);
 }
 const worker=readFileSync(new URL('worker.mjs',root),'utf8');
 assert.ok(worker.includes('purgeOldPublicEventBuckets(env)'));
});
