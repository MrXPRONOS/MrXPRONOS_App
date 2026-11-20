import test from 'node:test';
import assert from 'node:assert/strict';
import {enqueueOwnerVaultUpdate,captureOwnerForwardInVault,processOwnerVaultQueue} from '../owner-chat-vault.mjs';

const SERIES=-1001234567890;
const OWNER=424242;
function fakeDb({gate=true,queue=[],existing=null}={}){
 const writes=[];
 const db={prepare(sql){
  let params=[];
  const statement={
   bind(...v){params=v;return statement},
   async first(){
    if(sql.includes('FROM cine_series_config'))return {setting_value:gate?'true':'false'};
    if(sql.includes('AS series_rights'))return {series_rights:1,library_rights:null,classic_link:0};
    if(sql.includes('FROM cine_series_posters'))return {ok:1};
    if(sql.includes('SELECT status FROM cine_owner_vault'))return existing;
    return null;
   },
   async all(){
    if(sql.includes('FROM admin_users'))return {results:[{user_id:OWNER}]};
    if(sql.includes('FROM cine_owner_vault'))return {results:queue};
    return {results:[]};
   },
   async run(){writes.push({sql,params});return {meta:{changes:1}}}
  };return statement;
 }};
 return {DB:db,writes};
}

test('new private series video is mirrored only when feature is enabled',async()=>{
 const disabled=fakeDb({gate:false});
 assert.equal((await enqueueOwnerVaultUpdate(disabled,{channel_post:{chat:{type:'channel',id:SERIES},message_id:4,video:{file_id:'a'},caption:'S01E01'}})).queued,false);
 assert.equal(disabled.writes.length,0);
 const active=fakeDb();
 const result=await enqueueOwnerVaultUpdate(active,{channel_post:{chat:{type:'channel',id:SERIES},message_id:4,video:{file_id:'a'},caption:'S01E01'}});
 assert.equal(result.queued,true);
 assert.ok(active.writes.some(w=>w.sql.includes('INSERT OR IGNORE INTO cine_owner_vault')&&w.params[1]===4));
});
test('only verified owner forwarding creates an owner-chat receipt, no copyMessage',async()=>{
 const d=fakeDb();
 const origin={type:'channel',chat:{id:SERIES},message_id:6};
 const message={chat:{id:OWNER,type:'private'},from:{id:OWNER},message_id:100,forward_origin:origin,
  video:{file_id:'a'},caption:'S01E03'};
 assert.equal((await captureOwnerForwardInVault(d,message)).captured,true);
 assert.ok(d.writes.some(x=>x.sql.includes("status='stored'")&&x.params[4]===100));
 const notOwner=fakeDb();
 assert.equal((await captureOwnerForwardInVault(notOwner,{...message,from:{id:999}})).captured,false);
 assert.equal(notOwner.writes.length,0);
});
test('owner media copying stores a receipt and never deletes private owner originals',async()=>{
 const row={source_chat_id:String(SERIES),source_message_id:6,media_kind:'video'};
 const d=fakeDb({queue:[row]});
 const old=globalThis.fetch;
 let called=0;
 globalThis.fetch=async (_url,opt)=>{
  called++;
  const body=JSON.parse(opt.body);
  assert.equal(body.chat_id,OWNER);
  assert.equal(body.from_chat_id,String(SERIES));
  assert.equal(body.message_id,6);
  return new Response(JSON.stringify({ok:true,result:{message_id:110}}),{status:200});
 };
 try{
  const output=await processOwnerVaultQueue({DB:d.DB,TELEGRAM_TOKEN:'test:secret'});
  assert.deepEqual(output,{processed:1,errors:0});
  assert.equal(called,1);
  assert.ok(d.writes.some(x=>x.sql.includes("status='stored'")&&x.params[1]===110));
  assert.ok(!d.writes.some(x=>/deleteMessage|delete_after/i.test(x.sql)));
 }finally{globalThis.fetch=old;}
});
test('indeterminate copy response goes to manual review to avoid duplicates',async()=>{
 const row={source_chat_id:String(SERIES),source_message_id:7,media_kind:'video'};
 const d=fakeDb({queue:[row]});
 const old=globalThis.fetch;
 globalThis.fetch=async ()=>{throw Error('fake timeout')};
 try{
  const output=await processOwnerVaultQueue({DB:d.DB,TELEGRAM_TOKEN:'test:secret'});
  assert.equal(output.processed,0);
  assert.equal(output.errors,1);
  assert.ok(d.writes.some(x=>x.sql.includes("status='needs_review'")));
 }finally{globalThis.fetch=old;}
});
