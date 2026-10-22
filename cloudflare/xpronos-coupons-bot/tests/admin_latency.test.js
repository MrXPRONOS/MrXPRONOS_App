import test from 'node:test';
import assert from 'node:assert/strict';
import {adminApi} from '../src/admin-ui.js';

test('Admin overview starts coupon lookup while summary counters still await D1',async()=>{
 let resolveStats,notifyCoupons;
 const gate=new Promise(resolve=>{resolveStats=resolve});
 const hit=new Promise(resolve=>{notifyCoupons=resolve});
 const sql=[];
 const db={prepare(query){
  sql.push(query);
  return {bind(){return {
   first:async()=>query.includes('(SELECT count(*) FROM users)')?gate:null,
   all:async()=>{if(query.includes('FROM coupons ORDER BY id DESC'))notifyCoupons();return {results:[]}}
  }}};
 }};
 const env={DB:db,CF_BOT_ADMIN_IDS:'80599'};
 const pending=adminApi(new Request('https://test.invalid/api/admin/overview'),env,80599);
 await Promise.race([hit,new Promise((_,reject)=>setTimeout(()=>reject(Error('Sequential admin D1 detected')),300))]);
 resolveStats({users:4,verified:2,coupons:0,redemptions:0,coupon_subscribers:1,open_tickets:0,alerts_sent:0});
 const response=await pending;
 assert.equal(response.status,200);
 const body=await response.json();
 assert.equal(body.stats.users,4);
 assert.deepEqual(body.coupons,[]);
 assert.equal(sql.length,2);
});
test('Admin performance improvements retain strict role check',async()=>{
 const r=await adminApi(new Request('https://test.invalid/api/admin/overview'),{CF_BOT_ADMIN_IDS:'80599'},77);
 assert.equal(r.status,403);
});
