import test from 'node:test';
import assert from 'node:assert/strict';
import {deletionDecision,cleanupDeliveredCopies} from '../cinex-expiry.mjs';
const now=new Date('2026-11-20T12:00:00Z');
const prior=h=>new Date(now.getTime()-h*3600000).toISOString();

test('only explicit success or confirmed missing messages mark cleanup complete',()=>{
 assert.equal(deletionDecision({ok:true,result:true},{sentAt:prior(25),now:now.getTime()}).state,'deleted');
 assert.equal(deletionDecision({ok:false,error_code:400,description:'Bad Request: message to delete not found'},{sentAt:prior(25),now:now.getTime()}).state,'already_gone');
 assert.equal(deletionDecision({ok:false,error_code:400,description:"message can\'t be deleted"},{sentAt:prior(25),now:now.getTime()}).state,'manual_review');
});
test('not before 24 hours, 48h safety deadline and retry budget',()=>{
 assert.equal(deletionDecision({ok:true,result:true},{sentAt:prior(23),now:now.getTime()}).state,'retry');
 assert.equal(deletionDecision({ok:true,result:true},{sentAt:prior(47.2),now:now.getTime()}).state,'manual_review');
 assert.equal(deletionDecision({networkError:true},{sentAt:prior(25),now:now.getTime(),attempt:30}).state,'manual_review');
 const r=deletionDecision({ok:false,error_code:429,parameters:{retry_after:300}},{sentAt:prior(25),now:now.getTime(),attempt:1});
 assert.equal(r.state,'retry');assert.equal(r.retrySeconds,300);
});
test('disabled distribution does not disable cleanup, but zero due copies send no requests',async()=>{
 let methods=[],queries=[];
 const orig=globalThis.fetch;
 globalThis.fetch=async(url)=>{methods.push(String(url).split('/').at(-1));return Response.json({ok:true,result:true})};
 const DB={prepare(sql){queries.push(sql);return{
   async run(){return{meta:{changes:0}}},
   bind(){return this},async all(){return{results:[]}}
 }}};
 try{
  const result=await cleanupDeliveredCopies({DB,TELEGRAM_TOKEN:'test'},{now});
  assert.deepEqual(result,{checked:0,deleted:0,already_gone:0,retried:0,manual_review:0,failed:0});
  assert.equal(methods.length,0);
  assert.ok(queries.some(q=>q.includes("cine_delivery_job_items")));
  assert.ok(!queries.some(q=>/DELETE FROM/i.test(q)));
 }finally{globalThis.fetch=orig}
});
test('one verified private copy expires; never a library/public message',async()=>{
 const seen=[],updates=[];
 const old=globalThis.fetch;
 globalThis.fetch=async(url,opt)=>{
  seen.push({method:String(url).split('/').at(-1),body:JSON.parse(opt.body)});
  return Response.json({ok:true,result:true});
 };
 const row={job_id:3,ordinal:1,delivered_message_id:80,sent_at:prior(25),delete_attempts:0,telegram_chat_id:456};
 const DB={prepare(sql){const rec={sql,bind(...args){this.params=args;return this},async all(){return {results:[row]}},async run(){
    updates.push({sql:this.sql,params:this.params||[]});
    return {meta:{changes:1}};
   }};return rec;}};
 try{
  const res=await cleanupDeliveredCopies({DB,TELEGRAM_TOKEN:'fake'},{now});
  assert.equal(res.deleted,1);
  assert.equal(seen.length,1);
  assert.deepEqual(seen[0],{method:'deleteMessage',body:{chat_id:456,message_id:80}});
  assert.ok(updates.some(x=>x.sql.includes("delete_state=?")&&x.params[0]==='deleted'));
  assert.ok(!updates.some(x=>/DELETE FROM\s+cine_delivery/i.test(x.sql)));
 }finally{globalThis.fetch=old}
});
test('never send deleteMessage to source channel, even with corrupted job',async()=>{
 const called=[],old=globalThis.fetch;
 globalThis.fetch=async url=>{called.push(url);return Response.json({ok:true,result:true})};
 const row={job_id:4,ordinal:2,delivered_message_id:30,sent_at:prior(25),delete_attempts:0,telegram_chat_id:-1004455497484};
 const DB={prepare(sql){return {bind(){return this},async all(){return{results:[row]}},async run(){return{meta:{changes:1}}}}}};
 try{const out=await cleanupDeliveredCopies({DB,TELEGRAM_TOKEN:'fake'},{now});assert.equal(called.length,0);assert.equal(out.manual_review,1)}finally{globalThis.fetch=old}
});
test('transient Telegram errors stay pending; ambiguous failures are not marked deleted',()=>{
 assert.equal(deletionDecision({networkError:true},{sentAt:prior(25),now:now.getTime(),attempt:1}).state,'retry');
 assert.equal(deletionDecision({ok:false,error_code:403,description:'Forbidden'},{sentAt:prior(25),now:now.getTime()}).state,'manual_review');
});
