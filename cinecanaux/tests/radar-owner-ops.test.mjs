import test from 'node:test';
import assert from 'node:assert/strict';
import {PRIMARY_CHANNELS,bindPrimaryRadarChannels,formatRadarMissing,missingRadarTitles,notifyOwnerMissingRadarTitles} from '../radar-owner-ops.mjs';

test('three exact primary channels are managed independently',()=>{
 assert.deepEqual(PRIMARY_CHANNELS.map(x=>x.username),['CineXFilms_vf','seriesvf_cinex','CineXAnimeFR']);
});
test('missing-title digest labels films, series and anime and does not include media links',()=>{
 const text=formatRadarMissing([
  {kind:'films',title:'Film exemple',year:2026,source_url:'https://www.themoviedb.org/movie/12'},
  {kind:'series',title:'Série exemple',source_url:'https://www.themoviedb.org/tv/13'},
  {kind:'animes',title:'Anime exemple',source_url:'https://anilist.co/anime/14'}
 ]);
 assert.match(text,/🎬 FILMS/);
 assert.match(text,/📺 SÉRIES/);
 assert.match(text,/🎌 ANIMÉS/);
 assert.match(text,/Film exemple/);
 assert.doesNotMatch(text,/file_id|t\.me\//);
});
test('only verified bot-admin channel identity can bind a D1 row',async t=>{
 const calls=[],writes=[],original=globalThis.fetch;
 globalThis.fetch=async (url,options)=>{
  const method=String(url).split('/').pop();
  const payload=JSON.parse(options.body);
  calls.push({method,payload});
  const id={'@CineXFilms_vf':-100101,'@seriesvf_cinex':-100102,'@CineXAnimeFR':-100103}[payload.chat_id]||payload.chat_id;
  const result=method==='getMe'?{id:42}:method==='getChat'?{type:'channel',id,username:payload.chat_id.slice(1)}:{status:payload.chat_id===-100102?'member':'administrator'};
  return {ok:true,json:async()=>({ok:true,result})};
 };
 t.after(()=>{globalThis.fetch=original});
 const db={prepare(sql){let args;const stmt={bind(...a){args=a;return stmt;},async first(){return {chat_id:null}},async run(){writes.push(args);return {meta:{changes:1}}}};return stmt;}};
 const result=await bindPrimaryRadarChannels({TELEGRAM_TOKEN:'test',DB:db});
 assert.equal(result.bound,2);
 assert.equal(result.errors.length,1);
 assert.equal(writes.length,2);
 assert.equal(calls.filter(x=>x.method==='getChatMember').length,3);
});
test('unmatched titles are filtered with owner-specific notice history',async()=>{
 let sql='',args=[];
 const env={DB:{prepare(s){sql=s;return {bind(...v){args=v;return {all:async()=>({results:[]})}}}}}};
 await missingRadarTitles(env,77,{onlyUnnotified:true,limit:12});
 assert.match(sql,/NOT EXISTS \(SELECT 1 FROM radar_matches/);
 assert.match(sql,/NOT EXISTS \(SELECT 1 FROM radar_notice_log/);
 assert.deepEqual(args,[77,12]);
});
test('failed Telegram send never marks a suggestion as delivered',async t=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>({ok:true,json:async()=>({ok:false,error_code:403})});
 t.after(()=>{globalThis.fetch=original});
 const writes=[];
 const DB={prepare(sql){return {bind(...args){return {run:async()=>{writes.push(args)},all:async()=>({results:[]})}},all:async()=>{
  if(sql.includes('FROM admin_users'))return {results:[{user_id:77}]};
  if(sql.includes('FROM radar_titles'))return {results:[{id:'tmdb-films-77',kind:'films',title:'Example',year:2026,source_url:'https://www.themoviedb.org/movie/77'}]};
  return {results:[]};
 }}}};
 const res=await notifyOwnerMissingRadarTitles({TELEGRAM_TOKEN:'test',DB});
 assert.equal(res.sent,0);
 assert.equal(res.errors.length,1);
 assert.equal(writes.length,0);
});
