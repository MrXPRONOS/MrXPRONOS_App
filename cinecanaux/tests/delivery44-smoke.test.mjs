import test from 'node:test';
import assert from 'node:assert/strict';
import {runDelivery44SmokeOnce} from '../delivery44-smoke.mjs';

test('one-shot probe does not send or mutate without explicit flag',async()=>{
 const queries=[];
 const env={DB:{prepare(sql){
  queries.push(sql);
  if(sql==='SELECT value FROM bot_settings WHERE setting_key=?')return {bind(key){assert.equal(key,'cine_delivery44_smoke_once');return {first:async()=>null}}};
  throw Error('unexpected query or attempted delivery');
 }}};
 assert.deepEqual(await runDelivery44SmokeOnce(env),{status:'skipped'});
 assert.equal(queries.length,1);
});
test('probe has no side effects when flag is not active',async()=>{
 const env={DB:{prepare(){
  return {bind(){return {first:async()=>({value:'finished'})}}};
 }}};
 assert.deepEqual(await runDelivery44SmokeOnce(env),{status:'skipped'});
});
