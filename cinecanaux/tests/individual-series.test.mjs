import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {parseSeason,parseEpisode,parseExpectedEpisodes,validSeriesPlan,seriesButtons,ingestIndividualSeriesUpdate,ingestSeriesOwnerForward} from '../individual-series.mjs';

test('saisons présentes dans la description des affiches',()=>{
 assert.equal(parseSeason('BLACK DOVES\nSaison 1 | VF'),1);
 assert.equal(parseSeason('S03 - Saison trois'),3);
 assert.equal(parseSeason('LUPIN SAISON 02\n8 épisodes'),2);
 assert.equal(parseSeason('LUPIN - nouvelle affiche sans numero'),null);
 assert.equal(parseSeason('Saison 99'),null);
});
test('épisodes dans légendes et noms de fichiers',()=>{
 assert.deepEqual(parseEpisode('Black Doves S01E02.mkv'),{season:1,episode:2});
 assert.deepEqual(parseEpisode('Saison 3 épisode 12 - VOSTFR'),{season:3,episode:12});
 assert.equal(parseEpisode('Episode 5 sans saison'),null);
});
test('comptage explicite des épisodes',()=>{
 assert.equal(parseExpectedEpisodes('Saison 1 : 12 épisodes'),12);
 assert.equal(parseExpectedEpisodes('8 episodes | Saison 2'),8);
 assert.equal(parseExpectedEpisodes('Une saison complète'),null);
});
test('livraison impossible si nombre non précisé ou saison incomplète',()=>{
 const seasons=[{season:1,expected_episodes:2},{season:2,expected_episodes:1}];
 const media=[
 {season:1,episode:1,source_message_id:11},
 {season:1,episode:2,source_message_id:12},
 {season:2,episode:1,source_message_id:35}
 ];
 assert.equal(validSeriesPlan(seasons,media),true);
 assert.equal(validSeriesPlan(seasons,media.slice(0,2)),false);
 assert.equal(validSeriesPlan([{season:1,expected_episodes:null}],media),false);
 assert.equal(validSeriesPlan([{season:2,expected_episodes:1}],[media[2]]),false);
 assert.equal(validSeriesPlan(seasons,[media[0],media[0],media[2]]),false);
});
test('boutons couleur, radar et secours à destination exacte',()=>{
 const mark=seriesButtons('abcdefghijklmnopqrstuvwx','https://t.me/+abcdefghijkL','https://t.me/addlist/ABCDEFGHIJK');
 assert.equal(mark.inline_keyboard.length,3);
 assert.equal(mark.inline_keyboard[0][0].url,'https://t.me/CineRadarFr_Bot?start=sr_abcdefghijklmnopqrstuvwx');
 assert.deepEqual(mark.inline_keyboard.map(r=>r[0].style),['success','danger','primary']);
 assert.throws(()=>seriesButtons('bad','https://t.me/+abcdefghijkL','https://t.me/addlist/ABCDEFGHIJK'));
 assert.throws(()=>seriesButtons('abcdefghijklmnopqrstuvwx','https://example.org/no','https://t.me/addlist/ABCDEFGHIJK'));
});


function mockD1(){
 const calls=[];
 const DB={prepare(sql){
  const q={
   bind(...args){q.args=args;return q},
   async first(){
    if(sql.includes('FROM cine_series_channels'))return {chat_id:'-1001234567890'};
    if(sql.includes('FROM admin_users'))return {role:'owner'};
    return null;
   },
   async run(){calls.push({sql,args:q.args});return {meta:{changes:1}}},
   async all(){return {results:[]}}
  };return q;
 }};
 return {DB,calls};
}
test('un nouveau message épinglé saison 2 est indexé sans API externe',async()=>{
 const {DB,calls}=mockD1(),poster={message_id:19,caption:'Ma série Saison 2 — 8 épisodes',photo:[{file_id:'img'}]};
 const out=await ingestIndividualSeriesUpdate({DB},{channel_post:{chat:{type:'channel',id:-1001234567890},pinned_message:poster}});
 assert.equal(out,true);
 assert.ok(calls.some(x=>x.sql.includes('INSERT INTO cine_series_posters')&&x.args[1]===2&&x.args[2]===19));
 assert.ok(calls.some(x=>x.sql.includes('UPDATE cine_series_channels SET expected_seasons')));
 assert.ok(calls.some(x=>x.sql.includes('INSERT INTO cine_series_seasons')&&x.args[2]===8));
});
test('les prochains épisodes sont indexés avec le message ID source',async()=>{
 const {DB,calls}=mockD1();
 const out=await ingestIndividualSeriesUpdate({DB},{channel_post:{chat:{type:'channel',id:-1001234567890},message_id:77,caption:'Ma série S02E03',video:{file_id:'video'}}});
 assert.equal(out,true);
 assert.ok(calls.some(x=>x.sql.includes('INSERT INTO cine_series_episodes')&&x.args[1]===2&&x.args[2]===3&&x.args[3]===77));
});
test('le propriétaire peut indexer une ancienne affiche et un ancien épisode par transfert',async()=>{
 const {DB,calls}=mockD1();
 const poster=await ingestSeriesOwnerForward({DB},{chat:{type:'private'},from:{id:100},forward_origin:{type:'channel',chat:{id:-1001234567890},message_id:5},caption:'Saison 1 • 10 épisodes',photo:[{file_id:'photo'}]});
 assert.equal(poster.stored,true);
 const episode=await ingestSeriesOwnerForward({DB},{chat:{type:'private'},from:{id:100},forward_origin:{type:'channel',chat:{id:-1001234567890},message_id:35},caption:'S01E02',video:{file_id:'video'}});
 assert.equal(episode.stored,true);
 assert.ok(calls.some(x=>x.sql.includes('INSERT INTO cine_series_posters')&&x.args[2]===5));
 assert.ok(calls.some(x=>x.sql.includes('INSERT INTO cine_series_episodes')&&x.args[3]===35));
});


test('an existing season and episode cannot silently be replaced by different Telegram messages',async()=>{
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../migrations/019_cinex_individual_series.sql',import.meta.url),'utf8'));
 db.exec("CREATE TABLE admin_users(user_id INTEGER PRIMARY KEY,role TEXT NOT NULL)");
 db.exec("INSERT INTO admin_users VALUES(101,'owner')");
 db.prepare("INSERT INTO cine_series_channels(chat_id,title,rights_attested) VALUES(?,'Test Série',1)").run('-1001234567890');
 const DB={
  prepare(sql){
   let params=[];
   return {
    bind(...args){params=args;return this},
    async first(){return db.prepare(sql).get(...params)||null},
    async all(){return {results:db.prepare(sql).all(...params)}},
    async run(){const a=db.prepare(sql).run(...params);return {meta:{changes:Number(a.changes)}}},
   };
  }
 };
 const env={DB},make=(messageId,caption,photo=false)=>({
  chat:{type:'private',id:101},from:{id:101},
  forward_origin:{type:'channel',chat:{id:-1001234567890},message_id:messageId},
  caption,...(photo?{photo:[{file_id:'img'}]}:{video:{file_id:'video'}})
 });
 try{
  assert.equal((await ingestSeriesOwnerForward(env,make(11,'S01E01'))).stored,true);
  const different=await ingestSeriesOwnerForward(env,make(12,'S01E01'));
  assert.equal(different.stored,false);
  assert.match(different.reason,/déjà une autre vidéo/);
  assert.equal(db.prepare("SELECT source_message_id FROM cine_series_episodes WHERE season=1 AND episode=1").get().source_message_id,11);
  assert.equal((await ingestSeriesOwnerForward(env,make(11,'S01E01'))).stored,true);
  assert.equal((await ingestIndividualSeriesUpdate(env,{channel_post:{chat:{type:'channel',id:-1001234567890},message_id:13,video:{file_id:'v'},caption:'S01E01'}})),false);
  assert.equal(db.prepare("SELECT source_message_id FROM cine_series_episodes WHERE season=1 AND episode=1").get().source_message_id,11);
  assert.equal((await ingestSeriesOwnerForward(env,make(31,'Saison 1 • 10 épisodes',true))).stored,true);
  const cover=await ingestSeriesOwnerForward(env,make(32,'Saison 1 • nouvelle affiche',true));
  assert.equal(cover.stored,false);
  assert.equal(db.prepare("SELECT source_message_id FROM cine_series_posters WHERE season=1").get().source_message_id,31);
  const mark=seriesButtons('abcdefghijklmnopqrstuvwx','https://t.me/+abcdefghijkL','https://t.me/addlist/ABCDEFGHIJK');
  assert.match(mark.inline_keyboard[0][0].text,/épisodes disponibles/);
 }finally{db.close()}
});
