import test from 'node:test';
import assert from 'node:assert/strict';
import {PRIMARY_CHANNELS,formatRadarMissing,missingRadarTitles,bindPrimaryRadarChannels,notifyOwnerMissingRadarTitles} from '../radar-owner-ops.mjs';

const titles=[
 {id:'tmdb-films-1',kind:'films',title:'Cinema One',year:2026,source_url:'https://www.themoviedb.org/movie/1',trend_rank:1},
 {id:'tmdb-series-2',kind:'series',title:'Series Two',year:2026,source_url:'https://www.themoviedb.org/tv/2',trend_rank:1},
 {id:'anilist-animes-3',kind:'animes',title:'Anime Three',year:2026,source_url:'https://anilist.co/anime/3',trend_rank:1}
];
function dbFixture({bound={},noticeWrites=[],ownerId=777}={}){
 const db={prepare(sql){
  let params=[];
  const stmt={
   bind(...args){params=args;return stmt;},
   async first(){
    if(sql.includes('FROM radar_primary_channels'))return {chat_id:bound[params[0]]||null};
    return null;
   },
   async all(){
    if(sql.includes("FROM admin_users"))return {results:[{user_id:ownerId}]};
    if(sql.includes('FROM radar_titles'))return {results:titles.filter(x=>x.kind===params[0])};
    return {results:[]};
   },
   async run(){if(sql.includes('radar_notice_log'))noticeWrites.push(params);return {meta:{changes:1}};}
  };return stmt;
 }};
 return db;
}
test('three exact original channels remain the only approved backfill targets',()=>{
 assert.deepEqual(PRIMARY_CHANNELS.map(x=>x.username),['CineXFilms_vf','seriesvf_cinex','CineXAnimeFR']);
});
test('a fair private digest includes films, series, and anime',async()=>{
 const rows=await missingRadarTitles({DB:dbFixture()},777,{limit:3});
 assert.deepEqual(rows.map(x=>x.kind),['films','series','animes']);
 const text=formatRadarMissing(rows);
 assert.match(text,/FILMS/);assert.match(text,/SÉRIES/);assert.match(text,/ANIMÉS/);
 assert.match(text,/Cinema One/);assert.match(text,/Series Two/);assert.match(text,/Anime Three/);
 assert.doesNotMatch(text,/file_id|download|token/i);
});
test('no automatic notifications are sent without any new titles',async()=>{
 let calls=0;const old=globalThis.fetch;
 globalThis.fetch=async()=>{calls++;throw Error('no Telegram messages expected');};
 try{
  const DB={prepare(sql){return {async all(){return {results:sql.includes('admin_users')?[{user_id:777}]:[]}},bind(){return this;}}}};
  const result=await notifyOwnerMissingRadarTitles({DB,TELEGRAM_TOKEN:'not-a-real-token'});
  assert.equal(result.sent,0);assert.equal(calls,0);
 }finally{globalThis.fetch=old;}
});
test('Telegram owner notification stays private, and receipts are saved after a successful send',async()=>{
 const old=globalThis.fetch,calls=[],writes=[];
 globalThis.fetch=async(url,opts)=>{calls.push({url,payload:JSON.parse(opts.body)});return Response.json({ok:true,result:{message_id:80}});};
 try{
  const result=await notifyOwnerMissingRadarTitles({DB:dbFixture({noticeWrites:writes}),TELEGRAM_TOKEN:'fake-token'});
  assert.equal(result.sent,1);
  assert.equal(result.listed,3);
  assert.equal(calls.length,1);
  assert.match(calls[0].url,/sendMessage$/);
  assert.equal(calls[0].payload.chat_id,777);
  assert.equal(writes.length,3);
 }finally{globalThis.fetch=old;}
});
test('channel binding rejects a mismatched persisted Telegram chat ID',async()=>{
 const old=globalThis.fetch,updates=[];
 globalThis.fetch=async(url,opts)=>{
  const method=url.split('/').at(-1),data=JSON.parse(opts.body);
  if(method==='getMe')return Response.json({ok:true,result:{id:902}});
  if(method==='getChat')return Response.json({ok:true,result:{type:'channel',id:-100222,username:data.chat_id.slice(1)}});
  if(method==='getChatMember')return Response.json({ok:true,result:{status:'administrator'}});
  throw Error('unexpected '+method);
 };
 try{
  const DB={prepare(sql){let params=[];const q={
   bind(...p){params=p;return q;},
   async first(){return {chat_id:'-100111'};},
   async run(){updates.push(params);return {meta:{changes:1}};}
  };return q;}};
  const result=await bindPrimaryRadarChannels({DB,TELEGRAM_TOKEN:'fake-token'});
  assert.equal(result.bound,0);assert.equal(result.errors.length,3);
  assert.equal(updates.length,0);
 }finally{globalThis.fetch=old;}
});
