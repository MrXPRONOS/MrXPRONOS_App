import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {acquireManualReceipt,performJournaledCopy,readManualReceipt,
 completeManualReceipt,uncertainManualReceipt,ManualReceiptBlocked,
 summarizeManualReceipts} from '../manual-fallback-journal.mjs';

function store(){
 const db=new DatabaseSync(':memory:');
 const DB={prepare(sql){
  let args=[];
  return {
   bind(...params){args=params;return this;},
   async first(){return db.prepare(sql).get(...args)||null;},
   async all(){return {results:db.prepare(sql).all(...args)};},
   async run(){return {meta:{changes:db.prepare(sql).run(...args).changes}}},
  };
 }};
 return {db,env:{DB}};
}
const intent={
 category:'films',content_key:'films:sample movie:2025',
 stage:'private_video',source_chat_id:'-1001111111111',
 source_message_id:12,target_chat_id:'-1002222222222'
};
test('one remote copy gets one complete durable receipt',async()=>{
 const {env}=store();let sends=0;
 const send=async()=>{sends++;return {message_id:42}};
 const first=await performJournaledCopy(env,intent,send);
 const second=await performJournaledCopy(env,intent,send);
 assert.equal(first.message_id,42);
 assert.equal(second.skipped,true);
 assert.equal(sends,1);
});
test('a timed out copy remains uncertain and never retries',async()=>{
 const {env}=store();let sends=0;
 await assert.rejects(
  performJournaledCopy(env,intent,async()=>{sends++;throw Error('network-timeout')}),
  /network-timeout/
 );
 const previous=await readManualReceipt(env,intent);
 assert.equal(previous.status,'uncertain');
 await assert.rejects(
  performJournaledCopy(env,intent,async()=>{sends++;return {message_id:99}}),
  ManualReceiptBlocked
 );
 assert.equal(sends,1);
});
test('inflight operation due to worker crash blocks retry',async()=>{
 const {env}=store();
 assert.equal((await acquireManualReceipt(env,intent)).status,'inflight');
 await assert.rejects(acquireManualReceipt(env,intent),ManualReceiptBlocked);
 const receipt=await readManualReceipt(env,intent);
 assert.equal(receipt.status,'inflight');
});
test('completed stage can never be redirected to a different target',async()=>{
 const {env}=store();
 await performJournaledCopy(env,intent,async()=>55);
 await assert.rejects(
  performJournaledCopy(env,{...intent,target_chat_id:'-1009999999999'},
   async()=>999),ManualReceiptBlocked);
});
test('cannot substitute source message after receipt reserved',async()=>{
 const {env}=store();
 await acquireManualReceipt(env,intent);
 await assert.rejects(
  acquireManualReceipt(env,{...intent,source_message_id:13}),
  ManualReceiptBlocked);
});
test('receipt must contain real positive Telegram message ID',async()=>{
 const {env}=store();
 await assert.rejects(
  performJournaledCopy(env,intent,async()=>({message_id:0})),
  ManualReceiptBlocked);
 assert.equal((await readManualReceipt(env,intent)).status,'uncertain');
});
test('only inflight receipts can complete and uncertain cannot auto-resume',async()=>{
 const {env}=store();
 await acquireManualReceipt(env,intent);
 await uncertainManualReceipt(env,intent);
 await assert.rejects(completeManualReceipt(env,intent,123),ManualReceiptBlocked);
 assert.equal((await readManualReceipt(env,intent)).status,'uncertain');
});
test('two independent stages remain separate while sharing content identity',async()=>{
 const {env}=store();
 await performJournaledCopy(env,intent,async()=>101);
 await performJournaledCopy(env,{...intent,stage:'public_video',
  target_chat_id:'-1003333333333'},async()=>202);
 const receipt=await summarizeManualReceipts(env);
 assert.equal(receipt.length,2);
 assert.ok(receipt.every(x=>x.status==='complete'));
});
test('bad/unrecognized category, forged peer or content key rejected',async()=>{
 const {env}=store();
 for(const item of [
  {...intent,category:'unknown'},
  {...intent,source_chat_id:'@public'},
  {...intent,content_key:'<payload>'},
  {...intent,source_message_id:0},
 ]){
  await assert.rejects(acquireManualReceipt(env,item),ManualReceiptBlocked);
 }
});
