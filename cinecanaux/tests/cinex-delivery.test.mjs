import test from 'node:test';
import assert from 'node:assert/strict';
import {downloadUrl,validSequence,handleDeliveryStart,handleSaveHelp,processDeliveryQueue,adminDeliveryAction} from '../cinex-delivery.mjs';
const TOKEN='ABCDEFGHIJKLMNOPQRSTUVWX';
const message=(text,chat=123,update_id=45)=>({update_id,message:{chat:{id:chat,type:'private'},from:{id:chat},text}});
test('deep links contain exactly a 24-character opaque token, never a channel ID',()=>{
 assert.equal(downloadUrl(TOKEN),'https://t.me/CineRadarFr_Bot?start=d_'+TOKEN);
 assert.equal(downloadUrl('-1004455497484'),null);
 assert.equal(downloadUrl(''),null);
});
test('a season is complete only if all numbered episodes are contiguous',()=>{
 const seq=[1,2,3].map(n=>({season_number:1,episode_number:n}));
 assert.equal(validSequence('series',1,seq),true);
 assert.equal(validSequence('series',1,[seq[0],seq[2]]),false);
 assert.equal(validSequence('series',1,[seq[0],seq[0]]),false);
 assert.equal(validSequence('series',2,seq),false);
 assert.equal(validSequence('film',0,[{season_number:null,episode_number:null}]),true);
 assert.equal(validSequence('film',0,seq),false);
 assert.equal(validSequence('series',1,Array(101).fill(seq[0])),false);
});
test('a disabled download never copies media or creates a job',async()=>{
 const calls=[];
 const old=globalThis.fetch;
 globalThis.fetch=async(url,opt)=>{calls.push(String(url).split('/').pop());return Response.json({ok:true,result:{message_id:3}})};
 let sql=[];
 const DB={prepare(query){sql.push(query);return{first:async()=>({value:'0'})}}};
 try{
  const result=await handleDeliveryStart({DB,TELEGRAM_TOKEN:'fake'},message('/start d_'+TOKEN));
  assert.equal(result.handled,true);assert.equal(result.accepted,false);
  assert.deepEqual(calls,['sendMessage']);
  assert.ok(!sql.some(q=>q.includes('cine_delivery_jobs')));
 }finally{globalThis.fetch=old;}
});
test('unrelated /start still uses existing CineRadar welcome screen',async()=>{
 const result=await handleDeliveryStart({DB:null},message('/start'));
 assert.equal(result.handled,false);
});
test('save-help callback only gives instructions, cannot forward user files silently',async()=>{
 const methods=[],old=globalThis.fetch;
 globalThis.fetch=async(url,opt)=>{methods.push(String(url).split('/').at(-1));return Response.json({ok:true,result:true})};
 try{
  assert.equal(await handleSaveHelp({TELEGRAM_TOKEN:'fake'},{callback_query:{id:'a',data:'cinex:save_help'}}),true);
  assert.deepEqual(methods,['answerCallbackQuery']);
  assert.equal(await handleSaveHelp({TELEGRAM_TOKEN:'fake'},{callback_query:{id:'b',data:'category:series:2'}}),false);
 }finally{globalThis.fetch=old;}
});
test('approval blocks missing or incomplete media, even if rights_confirmed=true',async()=>{
 const DB={prepare(q){return {bind(){return this},first:async()=>{
  if(q.includes('FROM cine_delivery_titles'))return{title_key:'a'.repeat(32),category:'series',content_kind:'series',bot_access:'verified',owner_access:'verified',rights_attested:1};
  return null;
 },all:async()=>({results:[{source_message_id:51,season_number:1,episode_number:2}]})}}};
 const r=await adminDeliveryAction({DB},'/api/admin/cinex/approve',{title_key:'a'.repeat(32),season:1,rights_confirmed:true});
 assert.equal(r.status,409);
});
test('worker cron stops without even touching Telegram when disabled',async()=>{
 const DB={prepare(sql){return{first:async()=>({value:'0'})}}};
 assert.deepEqual(await processDeliveryQueue({DB,TELEGRAM_TOKEN:'fake'}),{processed:0,errors:0,disabled:true});
});
