import test from 'node:test';
import assert from 'node:assert/strict';
import {v2API} from '../v2.mjs';
import {channelPreview} from '../channel-preview.mjs';
import {APP_HTML} from '../app-page.mjs';
import {checkDailyLinks} from '../maintenance-v2.mjs';

function mockedDB(){
 const entries=[
  {id:1,title:'CinéX Films',description:'Films VF',link:'https://t.me/CineXFilms_vf',
    content_type:'films',genre:'general',language:'VF',tags:'films',owned_featured:1,
    owned_priority:4,private_channel:0,review_count:0,link_status:'unknown'},
  {id:2,title:'CinéX Anime privé',description:'Animés VF',link:'https://t.me/+AbCdEf1234567890ZxYw',
    content_type:'animes',genre:'general',language:'VF',tags:'animes',owned_featured:1,
    owned_priority:4,private_channel:1,review_count:0,link_status:'private'},
  {id:3,title:'Canal non qualifié',description:'Inconnu',link:'https://t.me/+abcdefgh1234567890',
    content_type:'series',genre:'general',language:'VF',tags:'series',owned_featured:0,
    owned_priority:0,private_channel:0,review_count:0,link_status:'unknown'}
 ];
 const queries=[];
 return {
  queries,
  prepare(sql){let params=[];queries.push(sql);return {
   bind(...p){params=p;return this;},
   async first(){
    if(sql.includes('SELECT private_channel,enabled FROM owned_channel_features'))return {private_channel:1,enabled:1};
    if(sql.includes('FROM channels c LEFT JOIN channel_profile_cache p'))return {
     id:2,title:'CinéX Anime privé',description:'Animés VF',link:entries[1].link,last_post_at:null
    };
    return null;
   },
   async all(){
    if(sql.includes('SELECT c.id,c.title,c.link,c.description'))return {results:entries};
    return {results:[]};
   },
   async run(){return {meta:{changes:0}};}
  }};
 }
}
test('administered public and verified private links appear; unknown private links do not',async()=>{
 const env={DB:mockedDB()};
 const response=await v2API(env,new Request('https://example.org/api/search'));
 assert.equal(response.status,200);
 const data=await response.json();
 assert.deepEqual(new Set(data.channels.map(x=>x.id)),new Set([1,2]));
 assert.equal(data.channels.find(x=>x.id===2).private_channel,true);
 assert.equal(data.channels.find(x=>x.id===1).featured,true);
});
test('private anime shows only in anime category, with no fake public avatar',async()=>{
 const data=await (await v2API({DB:mockedDB()},new Request('https://example.org/api/search?types=animes'))).json();
 assert.deepEqual(data.channels.map(x=>x.id),[2]);
 assert.equal(data.channels[0].avatar,null);
});
test('private preview uses verified metadata without scraping private messages',async()=>{
 const env={DB:mockedDB()};
 const result=await channelPreview(env,2);
 assert.equal(result.status,200);
 assert.equal(result.data.preview_status,'private');
 assert.equal(result.data.title,'CinéX Anime privé');
});
test('the UI supports private invites and highlights featured channels',()=>{
 assert.ok(APP_HTML.includes('À la une'));
 assert.ok(APP_HTML.includes('Canal privé'));
 assert.ok(APP_HTML.includes('joinchat'));
 assert.ok(APP_HTML.includes('c.featured'));
});
test('daily link maintenance excludes invite-only channels from public 404 checks',async()=>{
 const db=mockedDB();const result=await checkDailyLinks({DB:db},10);
 assert.equal(result.checked,0);
 assert.ok(db.queries.some(sql=>sql.includes('f.private_channel=1')));
});
