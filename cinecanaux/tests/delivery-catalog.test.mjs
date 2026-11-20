import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyLibraryBotAccess,auditCineRadarLibraryMembership} from '../delivery-catalog.mjs';
test('only actual admin membership of the exact private channel passes',()=>{
 const id=-1004455497484,bot={ok:true,result:{id:17}};
 const chat={ok:true,result:{id}};
 assert.equal(classifyLibraryBotAccess(bot,chat,{ok:true,result:{status:'administrator'}},id),'verified');
 assert.equal(classifyLibraryBotAccess(bot,chat,{ok:true,result:{status:'member'}},id),'not_member');
 assert.equal(classifyLibraryBotAccess(bot,chat,{ok:false},id),'not_member');
 assert.equal(classifyLibraryBotAccess(bot,{ok:true,result:{id:-1004462439590}},{ok:true,result:{status:'administrator'}},id),'not_member');
});
test('missing libraries is an entirely read-only no-op',async()=>{
 let queries=0;
 const env={TELEGRAM_TOKEN:'never-sent',DB:{prepare(){queries++;return{all:async()=>({results:[]})}}}};
 assert.deepEqual(await auditCineRadarLibraryMembership(env),{checked:0,verified:0,blocked:0});
 assert.equal(queries,1);
});
test('bot check updates only access flag, never copies or approves media',async()=>{
 const calls=[],old=globalThis.fetch;
 globalThis.fetch=async(url,{body})=>{
   const op=String(url).split('/').at(-1);
   calls.push(op);
   const data=JSON.parse(body);
   return {ok:true,json:async()=>({ok:true,result:op==='getMe'?{id:19}:op==='getChat'?{id:-1004455497484}:{status:'administrator'}})};
 };
 const updates=[];
 const DB={prepare(sql){if(sql.includes('SELECT'))return{all:async()=>({results:[{category:'series',private_chat_id:'-1004455497484'}]})};
    return{bind(...params){updates.push({sql,params});return{run:async()=>({success:true})}}}}};
 try{
   assert.deepEqual(await auditCineRadarLibraryMembership({DB,TELEGRAM_TOKEN:'fake'}),{checked:1,verified:1,blocked:0});
   assert.deepEqual(calls,['getMe','getChat','getChatMember']);
   assert.equal(updates[0].params[0],'verified');
   assert.ok(!updates[0].sql.includes('cine_delivery_media'));
 }finally{globalThis.fetch=old}
});
