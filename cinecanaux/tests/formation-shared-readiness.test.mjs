import test from 'node:test';
import assert from 'node:assert/strict';
import {formationDestinations,auditSharedFormation}
 from '../formation-shared-readiness.mjs';
const source='-1001111111111';
const destinations={
 general:'@formations_officielles',business:'-1002222222222',
 finance:'-1003333333333',digitale:'-1004444444444',
 mindset:'-1005555555555'
};
function fixtures(overrides={}){
 const routes=['general','business','finance','digitale','mindset'].map(cat=>({
  category:'formation_'+cat,bot_access_verified:1,owner_approved:1,
  enabled:0,rights_attested:0
 }));
 const db={async query(sql){
  if(sql.includes("WHERE category='formation_general'"))
   return {results:overrides.sourceRows||[
    {chat_id:source,bot_access_verified:1,owner_approved:1}]};
  return {results:overrides.routes||routes};
 }};
 const accesses=[];
 const bot={
  async identity(){return {id:123456,is_bot:true}},
  async verifyChannel(id){
   accesses.push(id);
   return {id:Number(id)||'-1007777777777',type:'channel',
    username:id===destinations.general?'formations_officielles':null};
  }
 };
 const radar={async verifyChannel(id){
  accesses.push(id);
  return {id:Number(id),type:'channel',username:null};
 }};
 return {db,bot,radar,accesses};
}
test('five verified distinct destinations with exactly one private source',async()=>{
 const f=fixtures();
 const result=await auditSharedFormation({...f,stage:source,destinations});
 assert.deepEqual(result,{
  private_inboxes:1,destinations_verified:5,
  routes_verified:5,redistribution_routes_active:0
 });
 assert.equal(f.accesses.length,7);
});
test('destination configuration must be complete and not ambiguous',()=>{
 assert.deepEqual(formationDestinations(JSON.stringify(destinations)),destinations);
 assert.throws(()=>formationDestinations('{}'));
 assert.throws(()=>formationDestinations('not json'));
 assert.throws(()=>formationDestinations(JSON.stringify({
  ...destinations,business:destinations.finance
 })));
});
test('legacy Formation configuration with a bare @username is safely repaired',()=>{
 const raw='{"general":@formations_officielles,"business":"-1002222222222",'+
  '"finance":"-1003333333333","digitale":"-1004444444444",'+
  '"mindset":"-1005555555555"}';
 assert.deepEqual(formationDestinations(raw),destinations);
 assert.throws(()=>formationDestinations(raw.replace(
  '@formations_officielles','@'));
});
test('shared source must be IDENTICAL to existing stage channel',async()=>{
 const f=fixtures();
 await assert.rejects(auditSharedFormation({
  ...f,stage:'-1009999999999',destinations
 }));
 assert.equal(f.accesses.length,0);
});
test('a missing bot-verified destination route blocks publication',async()=>{
 const f=fixtures({routes:[{category:'formation_general',
  bot_access_verified:1,owner_approved:1}]});
 await assert.rejects(auditSharedFormation({...f,stage:source,destinations}));
});
test('public specialty destination is rejected',async()=>{
 const f=fixtures();
 const original=f.bot.verifyChannel;
 f.bot.verifyChannel=async id=>{
  const x=await original(id);
  if(id===destinations.business)x.username='mistaken_public';
  return x;
 };
 await assert.rejects(auditSharedFormation({...f,stage:source,destinations}));
});
