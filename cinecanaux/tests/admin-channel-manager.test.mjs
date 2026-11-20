import test from 'node:test';
import assert from 'node:assert/strict';
import {adminAPI} from '../admin-v2.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';

const root='https://cinecanaux.test';
const enc=new TextEncoder();
async function hmac(key,value){
 const k=await crypto.subtle.importKey('raw',typeof key==='string'?enc.encode(key):key,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(value)));
}
async function signed(){
 const auth_date=String(Math.floor(Date.now()/1000)),user=JSON.stringify({id:900,username:'mr_xpronos'});
 const secret=await hmac('WebAppData','bot:test');
 const data='auth_date='+auth_date+'\nuser='+user;
 const hash=[...await hmac(secret,data)].map(x=>x.toString(16).padStart(2,'0')).join('');
 return new URLSearchParams({user,auth_date,hash}).toString();
}
function fixture(){
 const writes=[];
 const DB={prepare(sql){
  const state={args:[]};
  const command={
   bind(...args){state.args=args;return command},
   async first(){
    if(sql.includes('SELECT role FROM admin_users'))return {role:'owner'};
    if(sql.includes('SELECT id,link FROM channels'))return {id:12,link:'https://t.me/ExempleFilmVF'};
    return null;
   },
   async all(){
    return {results:sql.includes('FROM channels c LEFT JOIN channel_index_meta')?[{
     id:12,title:'Films VF',link:'https://t.me/ExempleFilmVF',
     description:'Canal de découverte',content_type:'films',genre:'general',language:'VF',status:'approved',listing_status:'listed'
    }]:[]};
   },
   async run(){writes.push({sql,args:state.args});return {meta:{last_row_id:77,changes:1}}}
  };
  return command;
 }};
 return {env:{TELEGRAM_TOKEN:'bot:test',TELEGRAM_WEBHOOK_SECRET:'webhook-test',DB},writes};
}
const fields={title:'Films autorisés',link:'https://t.me/ExempleFilmVF',description:'Découvrir',content_type:'films',genre:'general',language:'VF'};
test('V1.2 keeps channel list and writes strictly owner authenticated',async()=>{
 const {env,writes}=fixture();
 const no=new Request(root+'/api/admin/channel-list');
 assert.equal((await adminAPI(env,no)).status,403);
 assert.equal(writes.length,0);
 const headers={'X-Telegram-Init-Data':await signed(),'Content-Type':'application/json'};
 const get=new Request(root+'/api/admin/channel-list',{headers});
 const response=await adminAPI(env,get);
 assert.equal(response.status,200);
 assert.equal((await response.json()).channels[0].title,'Films VF');
 const send=(path,data)=>adminAPI(env,new Request(root+path,{method:'POST',headers,body:JSON.stringify(data)}));
 const blocked=await send('/api/admin/channels',{action:'add',...fields,rights_confirmed:false});
 assert.equal(blocked.status,400);
 assert.equal(writes.length,0);
 const create=await send('/api/admin/channels',{action:'add',...fields,rights_confirmed:true});
 assert.equal(create.status,201);
 assert.equal((await create.json()).id,77);
 assert.ok(writes.some(x=>x.sql.startsWith('INSERT INTO channels(')));
 const edit=await send('/api/admin/channels/12',{action:'update',...fields,title:'Films VF — Révisés'});
 assert.equal(edit.status,200);
 assert.ok(writes.some(x=>x.sql.startsWith('UPDATE channels SET title=')));
 assert.ok(!writes.some(x=>x.sql.startsWith('UPDATE channels SET link=')));
 const bad=await send('/api/admin/channels',{action:'add',...fields,link:'http://private.test',rights_confirmed:true});
 assert.equal(bad.status,400);
 const type=await send('/api/admin/channels/12',{action:'update',...fields,content_type:'other'});
 assert.equal(type.status,400);
});
test('V1.2 includes owner-only channel manager and image gallery',()=>{
 for(const id of ['ad-channel-manager','ad-channel-search','ad-channel-list','ad-channel-form','ad-channel-rights','ad-channel-content-type'])
  assert.ok(ADMIN_HTML.includes('id="'+id+'"'),id);
 assert.ok(ADMIN_HTML.includes('"/assets/pin-cover/"'));
 assert.ok(ADMIN_HTML.includes('id="owner-pins-items"'));
});
