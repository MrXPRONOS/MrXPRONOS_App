import test from 'node:test';
import assert from 'node:assert/strict';
import {recoverFormationSource} from '../formation-source-access-link.mjs';
const source='-1003761327294';
function fixture({unverified=false,denied=false}={}){
 let sent=0;
 const db={async query(){return {results:[{chat_id:source,owner_approved:1,
  bot_access_verified:unverified?0:1,enabled:0,rights_attested:0}]}}};
 const publisher={async verifyChannel(){if(denied)throw Error('forbidden');
  return {id:Number(source),title:'Stock formation existant'}},
  async api(method,payload){assert.equal(method,'sendMessage');
   assert.equal(payload.chat_id,source);sent++;return {message_id:27}}};
 const radar={async verifyChannel(){return {id:Number(source)}}};
 return {db,publisher,radar,stage:source,get sent(){return sent}};
}
test('returns actual existing channel title and message pointer',async()=>{
 const f=fixture();const r=await recoverFormationSource(f);
 assert.deepEqual(r,{title:'Stock formation existant',message_id:27,
  bots_verified:true,redistribution_enabled:false});
 assert.equal(f.sent,1);
});
test('cannot post when D1 verification is absent',async()=>{
 const f=fixture({unverified:true});
 await assert.rejects(recoverFormationSource(f),/registered_source_missing/);
 assert.equal(f.sent,0);
});
test('cannot post when Telegram bot does not have access',async()=>{
 const f=fixture({denied:true});
 await assert.rejects(recoverFormationSource(f));
 assert.equal(f.sent,0);
});
