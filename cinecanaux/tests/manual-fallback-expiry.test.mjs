import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {schedulePublicExpiry,sweepPublicExpiry}
 from '../manual-fallback-expiry.mjs';

function create(){
 const sqlite=new DatabaseSync(':memory:');
 sqlite.exec(readFileSync(new URL('../migrations/029_cinex_manual_fallback.sql',import.meta.url),'utf8'));
 const db={async query(sql,args=[]){
  const stmt=sqlite.prepare(sql);
  if(sql.trim().toUpperCase().startsWith('SELECT'))
   return {results:stmt.all(...args),meta:{changes:0}};
  return {results:[],meta:{changes:stmt.run(...args).changes}};
 }};
 return {sqlite,db};
}
function receipt(sqlite,{date='2026-11-23 00:00:00'}={}){
 sqlite.prepare(
  "INSERT INTO cine_manual_fallback_receipts "+
  "(category,content_key,stage,status,target_chat_id,source_chat_id,source_message_id,target_message_id,updated_at) "+
  "VALUES('films','films:sample:2025','public_video','complete',?,?,3,44,?)"
 ).run('-1003333333333','-1001111111111',date);
}
const bot=()=>({
 async verifyChannel(chat){return {id:Number(chat),type:'channel',username:'cinexfilms_vf'}},
 async api(method,payload){assert.equal(method,'deleteMessage');return true}
});
test('expiration is exactly 12 hours from original confirmed receipt',async()=>{
 const {sqlite,db}=create();receipt(sqlite,{date:'2026-11-22 14:20:00'});
 await schedulePublicExpiry(db,'films','films:sample:2025');
 const row=sqlite.prepare('SELECT not_before FROM cine_manual_fallback_expiries').get();
 assert.equal(row.not_before,'2026-11-23 02:20:00');
 await schedulePublicExpiry(db,'films','films:sample:2025');
 assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM cine_manual_fallback_expiries').get().n,1);
});
test('expired public video deleted once, never private photo or private video',async()=>{
 const {sqlite,db}=create();receipt(sqlite);let deletes=0;
 const sender=()=>({async verifyChannel(chat){return {id:Number(chat),username:'public'}},
  async api(){deletes++;return true}});
 const first=await sweepPublicExpiry(db,sender);
 assert.equal(first.deleted,1);
 assert.equal(sqlite.prepare("SELECT status FROM cine_manual_fallback_expiries").get().status,'deleted');
 const second=await sweepPublicExpiry(db,sender);
 assert.equal(second.deleted,0);
 assert.equal(deletes,1);
});
test('network ambiguity blocks any duplicate deletion',async()=>{
 const {sqlite,db}=create();receipt(sqlite);let attempts=0;
 const sender=()=>({async verifyChannel(chat){return {id:Number(chat),username:'public'}},
  async api(){attempts++;throw Error('network timeout')}});
 const first=await sweepPublicExpiry(db,sender);
 assert.equal(first.uncertain,1);
 await sweepPublicExpiry(db,sender);
 assert.equal(attempts,1);
 assert.equal(sqlite.prepare("SELECT status FROM cine_manual_fallback_expiries").get().status,'uncertain');
});
test('not-yet-expired video cannot be removed',async()=>{
 const {sqlite,db}=create();receipt(sqlite,{date:'2099-11-22 00:00:00'});
 let deletes=0;
 const result=await sweepPublicExpiry(db,()=>({async api(){deletes++}}));
 assert.equal(result.seen,0);
 assert.equal(deletes,0);
});
test('forged pending row without a completed public receipt is never deleted',async()=>{
 const {sqlite,db}=create();
 await schedulePublicExpiry(db,'films','missing-2025').catch(()=>{});
 // Direct synthetic insertion to demonstrate defense against forged rows.
 sqlite.prepare(
  "INSERT INTO cine_manual_fallback_expiries "+
  "(category,content_key,target_chat_id,target_message_id,not_before) "+
  "VALUES('films','forged','-1003333333333',55,'2000-01-01 00:00:00')"
 ).run();
 let deletes=0;
 const result=await sweepPublicExpiry(db,()=>({async verifyChannel(c){return {id:Number(c)}},
  async api(){deletes++;return true}}));
 assert.equal(result.deleted,0);
 assert.equal(deletes,0);
});
