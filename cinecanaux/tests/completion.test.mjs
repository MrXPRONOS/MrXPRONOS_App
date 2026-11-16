import test from 'node:test';
import assert from 'node:assert/strict';
import {getPublicChat,canonicalForChat,safeUpdateChannelLink} from '../channel-identity.mjs';
import {runLoggedJob} from '../job-log.mjs';
import {checkDailyLinks} from '../maintenance-v2.mjs';
function db(rows=[]){
 const writes=[];
 return {writes,prepare(sql){
  let params=[];
  return {bind(...p){params=p;return this;},async first(){
   if(sql.includes('FROM channel_index_meta WHERE channel_id'))return rows[0]||null;
   if(sql.includes('FROM channel_exclusions'))return null;
   if(sql.includes('SELECT id FROM channels WHERE LOWER(link)'))return null;
   if(sql.includes('FROM channels WHERE LOWER(link)'))return null;
   return null;
  },async all(){return {results:rows};},async run(){
   writes.push({sql,params});
   return {meta:{changes:1,last_row_id:23}};
  }};
 },async batch(items){for(const item of items)await item.run();return []}};
}
const env={DB:db(),TELEGRAM_TOKEN:'00000000:staging_test_only'};
test('resolves verified public Telegram channel identity',async()=>{
 const old=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({ok:true,result:{id:-10012345,type:'channel',username:'NewChannelName',title:'Channel name',description:'Movies'}});
 try{
  const result=await getPublicChat(env,'@OldName');
  assert.equal(result.id,'-10012345');
  assert.equal(result.username,'newchannelname');
 }finally{globalThis.fetch=old}
});
test('rejects a Telegram group as a channel',async()=>{
 const old=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({ok:true,result:{id:-10012345,type:'supergroup',username:'GroupChannel'}});
 try{assert.equal(await getPublicChat(env,'@GroupChannel'),null)}finally{globalThis.fetch=old}
});
test('stable ID is preferred over reassigned old username',async()=>{
 const old=globalThis.fetch;
 globalThis.fetch=async(_url,options)=>Response.json({ok:true,result:{
  id:JSON.parse(options.body).chat_id==='-10012345'?-10012345:-100777,
  type:'channel',
  username:JSON.parse(options.body).chat_id==='-10012345'?'NEW_CHANNEL_2026':'TAKEN_OLD_LINK'
 }});
 try{
  const result=await canonicalForChat(env,'OLD_LINK_NAME','-10012345');
  assert.equal(result.state,'verified');
  assert.equal(result.chat.username,'new_channel_2026');
 }finally{globalThis.fetch=old}
});
test('only a proven identity can migrate a link, keeping the old alias',async()=>{
 const store=db();
 const result=await safeUpdateChannelLink({DB:store},1,'https://t.me/OLD_CHANNEL',{id:'-10012345',username:'NEW_CHANNEL'});
 assert.equal(result.changed,true);
 assert.ok(store.writes.some(x=>x.sql.includes('UPDATE channels SET link=')));
 assert.ok(store.writes.some(x=>x.sql.includes('INSERT INTO channel_aliases')));
});
test('recorded exclusions prevent link moves',async()=>{
 const store=db();
 const old=store.prepare.bind(store);
 store.prepare=(sql)=>sql.includes('FROM channel_exclusions')?{bind(){return this;},async first(){return {username:'blocked'}}}:old(sql);
 const result=await safeUpdateChannelLink({DB:store},1,'https://t.me/OLD_CHANNEL',{id:'-10012345',username:'NEW_CHANNEL'});
 assert.equal(result.reason,'excluded');
 assert.equal(store.writes.length,0);
});
test('scheduled executions persist completed and failed status',async()=>{
 const store=db();
 await runLoggedJob({DB:store},'link_check',async()=>({checked:10,errors:0}));
 assert.ok(store.writes.some(x=>x.sql.includes('status=?')&&x.params.includes('success')));
 await assert.rejects(runLoggedJob({DB:store},'discovery',async()=>{throw Error('Synthetic failure')}),/Synthetic failure/);
 assert.ok(store.writes.some(x=>x.sql.includes("status='error'")));
});
test('daily checker still returns at most 10 entries',async()=>{
 const store=db([]);
 const result=await checkDailyLinks({DB:store},25);
 assert.equal(result.checked,0);
 assert.equal(store.writes.length,1);
});

test('identity metadata uses canonical username when original handle changed',async()=>{
 const {addIfPublic}=await import('../maintenance-v2.mjs');
 const old=globalThis.fetch, db2=db();
 db2.prepare=(sql)=>{
  let params=[];
  return {bind(...v){params=v;return this;},async first(){if(sql.includes('FROM channel_exclusions'))return null;if(sql.includes('FROM channels'))return null;return null;},
   async run(){db2.writes.push({sql,params});return {meta:{changes:1,last_row_id:1}};},
   async all(){return {results:[]}}};
 };
 let seenUrls=[];
 globalThis.fetch=async(url,opts={})=>{
  if(String(url).includes('api.telegram.org'))return Response.json({ok:true,result:{id:-100321,type:'channel',username:'Canonical_News_2026',title:'Films 2026'}});
  seenUrls.push(String(url));
  return new Response('<meta property="og:title" content="Films 2026 | Telegram">',{status:200,headers:{'content-type':'text/html'}});
 };
 try{
  await addIfPublic({DB:db2,TELEGRAM_TOKEN:'fake_token'},'oldfilms2026','films');
  assert.ok(seenUrls.length>0);
  assert.ok(seenUrls.every(x=>x.includes('canonical_news_2026')));
 }finally{globalThis.fetch=old;}
});
