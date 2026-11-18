import test from 'node:test';
import assert from 'node:assert/strict';
import {RADAR_CHANNELS,matchRadarTitle,ingestRadarPost,radarFeed,radarApi,authorizeRadarTitle} from '../trend-radar.mjs';
import {APP_HTML} from '../app-page.mjs';

test('three exact owner-designated public Telegram channels',()=>{
 assert.deepEqual(RADAR_CHANNELS,[
  {kind:'films',username:'CineXFilms_vf'},
  {kind:'series',username:'seriesvf_cinex'},
  {kind:'animes',username:'CineXAnimeFR'}]);
});
test('matching requires a specific title and rejects wrong years and vague posts',()=>{
 const movie={title:'Mad Max Fury Road',title_original:'Mad Max: Fury Road',aliases:'',year:2015};
 assert.ok(matchRadarTitle('Mad Max Fury Road VF 2015 1080p',movie)>=85);
 assert.equal(matchRadarTitle('Mad Max Fury Road VF 2026',movie),0);
 assert.equal(matchRadarTitle('Nouveau film VF 2026',movie),0);
 assert.equal(matchRadarTitle('One Piece VF',{title:'Up'}),0);
 assert.ok(matchRadarTitle('Bleach épisode 4 VF',{title:'Bleach'})>=85);
});
function memoryDB(){
 const posts=[],matches=[],channelBinds=[];
 const titles=[{id:'tmdb-films-13',kind:'films',title:'Film Exemple',title_original:'',aliases:'',year:2026}];
 const db={prepare(sql){let params=[];const stmt={
  bind(...xs){params=xs;return stmt;},
  async all(){
   if(sql.includes('FROM radar_titles'))return {results:titles};
   if(sql.includes('FROM radar_posts'))return {results:posts};
   if(sql.includes('FROM admin_users'))return {results:[]};
   return {results:[]};
  },
  async first(){
   if(sql.includes('FROM radar_primary_channels'))return null;
   if(sql.includes('FROM admin_users'))return {role:'owner'};
   return null;
  },
  async run(){
   if(sql.includes('INSERT INTO radar_posts'))posts.push(params);
   if(sql.includes('INSERT INTO radar_matches'))matches.push(params);
   if(sql.includes('UPDATE radar_primary_channels'))channelBinds.push(params);
   return {meta:{changes:1}};
  }
 };return stmt;}};
 return {db,posts,matches,channelBinds};
}
test('channel posts from arbitrary Telegram channels are ignored without database writes',async()=>{
 const s=memoryDB();
 const out=await ingestRadarPost({DB:s.db},{channel_post:{message_id:19,chat:{type:'channel',id:-100777,username:'notCineXFilms_vf'},caption:'Film Exemple 2026',video:{file_id:'never-store'}}});
 assert.equal(out.ignored,true);
 assert.equal(s.posts.length,0);
});
test('the authorized primary Films channel is indexed by text and message ID, without storing video bytes',async()=>{
 const s=memoryDB();
 const out=await ingestRadarPost({DB:s.db},{channel_post:{message_id:48,date:1795000000,chat:{type:'channel',id:-10044,username:'CineXFilms_vf'},caption:'Film Exemple 2026 en VF',video:{file_id:'secret-not-persisted'}}});
 assert.equal(out.ignored,false);
 assert.equal(out.kind,'films');
 assert.equal(out.matched,1);
 assert.equal(s.posts.length,1);
 assert.equal(s.posts[0][1],48);
 assert.equal(s.posts[0][5],'video');
 assert.equal(s.matches.length,1);
 assert.equal(s.matches[0][4],'https://t.me/CineXFilms_vf/48');
 assert.ok(!JSON.stringify(s).includes('secret-not-persisted'));
});
test('only rights-approved video matches with valid posters and Telegram URLs enter the public feed',async()=>{
 const sample=[
 {id:'tmdb-films-1',kind:'films',title:'Film A',summary:'a',year:2026,poster_url:'https://image.tmdb.org/t/p/w342/abcdefghi.jpg',source_url:'https://www.themoviedb.org/movie/1',trend_rank:1,last_seen_at:'2026-11-18 05:00:00',click_count:70,matched_at:'2026-11-18 04:00:00',message_url:'https://t.me/CineXFilms_vf/123',media_kind:'video'},
 {id:'tmdb-films-2',kind:'films',title:'Film B',summary:'b',year:2026,poster_url:'https://image.tmdb.org/t/p/w342/abcdefghi.jpg',source_url:'https://www.themoviedb.org/movie/2',trend_rank:2,last_seen_at:'2026-11-18 05:00:00',click_count:0,matched_at:'2026-11-18 04:00:00',message_url:'https://t.me/CineXFilms_vf/124',media_kind:'video'},
 {id:'tmdb-films-3',kind:'films',title:'Fake Link',summary:'c',year:2026,poster_url:'https://image.tmdb.org/t/p/w342/abcdefghi.jpg',source_url:'https://www.themoviedb.org/movie/3',trend_rank:1,last_seen_at:'2026-11-18 05:00:00',click_count:1000,matched_at:'2026-11-18 04:00:00',message_url:'https://evil.example/movie',media_kind:'video'}
 ];
 const DB={prepare(sql){assert.ok(sql.includes("t.authorized=1"));assert.ok(sql.includes("m.media_kind='video'"));return {bind(){return {async all(){return {results:sample}}}}}}};
 const feed=await radarFeed({DB},'films',10);
 assert.equal(feed.total,2);
 assert.deepEqual(feed.items.map(x=>x.id),['tmdb-films-1','tmdb-films-2']);
});
test('click API validates title identity and Origin before attempting a DB write',async()=>{
 const DB={prepare(){throw Error('Invalid request must not hit D1')}};
 let r=await radarApi({DB},new Request('https://demo.local/api/radar/click',{method:'POST',headers:{'origin':'https://evil.local','content-type':'application/json'},body:'{"id":"tmdb-films-1"}'}));
 assert.equal(r.status,403);
 r=await radarApi({DB},new Request('https://demo.local/api/radar/click',{method:'POST',headers:{'content-type':'application/json'},body:'{"id":"not-a-title"}'}));
 assert.equal(r.status,400);
});
test('admin approval requires owner and only accepts known source ID formats',async()=>{
 const fixture=memoryDB();
 assert.equal(await authorizeRadarTitle({DB:fixture.db},'bad',1),false);
 assert.equal(await authorizeRadarTitle({DB:fixture.db},'tmdb-films-100',1),true);
});
test('mini-app preserves the scenic cinema hero and reserves À l’affiche for real pinned messages',()=>{
 assert.ok(APP_HTML.includes('fetch("/api/pinned-showcase"'));
 assert.ok(APP_HTML.includes('fetch("/api/pinned-click"'));
 assert.ok(APP_HTML.includes('loadCinemaShowcase()'));
 assert.ok(APP_HTML.includes('renderCinemaShowcase()'));
 assert.ok(!APP_HTML.includes('home.append(homeRadar)'));
 assert.ok(!APP_HTML.includes('panel.decouvrir.append(radarSection'));
});

test('a reused channel username cannot replace the Telegram chat ID already verified',async()=>{
 const state=memoryDB(),base=state.db;
 const DB={prepare(sql){
  if(sql.includes('SELECT chat_id FROM radar_primary_channels'))return {bind(){return {async first(){return {chat_id:'-100111'}}}}};
  return base.prepare(sql);
 }};
 const result=await ingestRadarPost({DB},{channel_post:{message_id:45,chat:{type:'channel',id:-100999,username:'CineXFilms_vf'},caption:'Film Exemple 2026',video:{file_id:'not-stored'}}});
 assert.equal(result.ignored,true);
 assert.equal(result.reason,'channel_identity_changed');
 assert.equal(state.posts.length,0);
});

test('a current TV season year does not disqualify a series first aired in an earlier year',()=>{
 assert.ok(matchRadarTitle('Lupin Saison 3 2026 VF',{title:'Lupin',kind:'series',year:2021})>=85);
});
