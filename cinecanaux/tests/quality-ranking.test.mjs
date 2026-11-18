import test from 'node:test';
import assert from 'node:assert/strict';
import {ownedQualityScore,v2API} from '../v2.mjs';
import {APP_HTML} from '../app-page.mjs';

const active={owned_featured:1,owned_priority:4,avatar_status:'real',
  audit_status:'verified',total_posts:830,posts_7d:28,posts_30d:72,media_30d:56};
const fallback={owned_featured:1,owned_priority:4,avatar_status:'fallback',
  audit_status:'verified',total_posts:0,posts_7d:0,posts_30d:0,media_30d:0};
test('a real photo and extensive current content outperform an empty featured channel',()=>{
 assert.ok(ownedQualityScore(active)>ownedQualityScore(fallback)+70);
 assert.ok(ownedQualityScore({...active,owned_featured:0})===0);
 assert.ok(ownedQualityScore({...active,avatar_status:'unknown',audit_status:'unavailable'})>ownedQualityScore(fallback),
  'A temporary unreachable audit should not imply zero content');
});
test('even a content-heavy placeholder must rank below a photographed genuine channel',()=>{
 const small={...active,total_posts:5,posts_7d:0,posts_30d:0,media_30d:0};
 const large={...active,avatar_status:'fallback',total_posts:5000,posts_7d:150,posts_30d:220,media_30d:200};
 assert.ok(ownedQualityScore(small)>ownedQualityScore(large));
});
test('actual catalog ranking prioritizes feature members verified as active and photographed',async()=>{
 const base={content_type:'films',link_status:'unknown',listing_status:'listed',genre:'general',
 language:'VF',description:'',tags:'films',review_count:0,rating:null};
 const rows=[
  {...base,id:111,title:'Sans photo et vide',link:'https://t.me/Empty00001',owned_featured:1,owned_priority:4,private_channel:0,avatar_status:'fallback',audit_status:'verified',total_posts:0,posts_7d:0,posts_30d:0,media_30d:0},
  {...base,id:112,title:'Cinéma actif photographié',link:'https://t.me/Active00002',owned_featured:1,owned_priority:4,private_channel:0,avatar_status:'real',audit_status:'verified',total_posts:990,posts_7d:15,posts_30d:60,media_30d:44},
  {...base,id:113,title:'Non partenaire',link:'https://t.me/Others00003',owned_featured:0,owned_priority:0,private_channel:0,avatar_status:null,audit_status:null,total_posts:null,posts_7d:null,posts_30d:null,media_30d:null}
 ];
 const db={prepare(sql){return{all:async()=>({results:sql.includes('FROM channels c LEFT JOIN channel_profile_cache')?rows:[]})}}};
 const response=await v2API({DB:db},new Request('https://test.local/api/catalog?limit=80'));
 assert.equal(response.status,200);
 const data=await response.json();
 assert.equal(data.channels[0].id,112);
 assert.equal(data.channels[0].avatar_verified,true);
 assert.equal(data.channels[0].content_count,990);
 assert.equal(data.channels[0].posts_7d,15);
 assert.equal(data.channels.find(x=>x.id===111).avatar_verified,false);
});
test('compact home now exposes nine featured channels with space for first two, retaining the poster carousel',()=>{
 assert.ok(APP_HTML.includes('featured.slice(0,9)'));
 assert.ok(APP_HTML.includes('.cine-home-picks .cine-pick:nth-child(-n+2)'));
 assert.ok(APP_HTML.includes('cine-poster-track'));
 assert.ok(APP_HTML.includes('cine-marquee-track'));
});
