import test from 'node:test';
import assert from 'node:assert/strict';
import {evaluateMarket,validFixture,getFixture,settleCoupon,safeLogo} from '../src/sports.js';
import {createEnrichedCoupon,isAdmin} from '../src/admin-ui.js';
import {miniPage} from '../src/minipage.js';
import {Script} from 'node:vm';

const f={league:'eng.1',date:'2026-10-22',id:'401770123'};
test('Only trusted ESPN fixture leagues, dates and logos are accepted',()=>{
 assert.equal(validFixture(f),true);
 assert.equal(validFixture({...f,league:'file:///secrets'}),false);
 assert.equal(validFixture({...f,date:'2026-02-31'}),false);
 assert.equal(safeLogo('https://a.espncdn.com/team.png'),'https://a.espncdn.com/team.png');
 assert.equal(safeLogo('https://evil.com/photo.jpg'),'');
});
test('Score markets are computed exactly and unknown markets are not evaluated',()=>{
 assert.equal(evaluateMarket('HOME',2,1),true);
 assert.equal(evaluateMarket('DRAW',2,1),false);
 assert.equal(evaluateMarket('OVER_2_5',2,1),true);
 assert.equal(evaluateMarket('BTTS_YES',2,1),true);
 assert.equal(evaluateMarket('BTTS_NO',0,1),true);
 assert.equal(evaluateMarket('CORNERS_OVER_9_5',2,1),null);
});
const data={leagues:[{name:'Premier League'}],events:[{
 id:'401770123',
 status:{type:{name:'STATUS_FINAL',completed:true}},
 competitions:[{competitors:[
   {homeAway:'home',score:'2',team:{displayName:'Équipe A',logo:'https://a.espncdn.com/a.png'}},
   {homeAway:'away',score:'1',team:{displayName:'Équipe B',logo:'https://a.espncdn.com/b.png'}}
 ]}]
}]};
test('ESPN response must refer to the requested event and final status',async()=>{
 const mock=async()=>({ok:true,json:async()=>data});
 const game=await getFixture(f,mock);
 assert.equal(game.completed,true);assert.deepEqual(game.score,[2,1]);
 assert.equal(game.home,'Équipe A');
 await assert.rejects(()=>getFixture({...f,id:'401770124'},mock),/introuvable|absent/);
});
test('Settlement does not mark uncompleted matches as won/lost',()=>{
 const key=[f.league,f.date,f.id].join('/');
 const selection={fixture:f,market_code:'HOME'};
 assert.equal(settleCoupon([selection],new Map([[key,{completed:false,isLive:true}]] )).status,'pending');
 assert.equal(settleCoupon([selection],new Map([[key,{completed:true,score:[2,1],source:'https://example.org'}]])).status,'won');
 assert.equal(settleCoupon([{fixture:f,market_code:'CORNERS'}],new Map()).status,'review');
});
test('Verified coupon creation rejects fake events, price/expiry problems and odds below 4',async()=>{
 const queries=[];
 const env={DB:{prepare:(sql)=>({bind:(...args)=>{
  queries.push({sql,args});
  return {first:async()=>({id:51})};
 }})}};
 const lookup=async()=>({id:f.id,league:f.league,date:f.date,completed:false,home:'Équipe A',away:'Équipe B',
    competition:'Premier League',homeLogo:'https://a.espncdn.com/a.png',awayLogo:'https://a.espncdn.com/b.png'});
 const payload={tier:'PRO',title:'Coupon match réel',xp_cost:30,stock:-1,
  expires_at:'2026-10-29T12:00:00Z',
  selections:[{fixture:f,market_code:'HOME',odds:'2.10'},{fixture:f,market_code:'OVER_2_5',odds:'2.00'}]};
 const created=await createEnrichedCoupon(env,payload,{lookup});
 assert.equal(created.total_odds,'4.20');
 assert.equal(created.media.games.length,1);
 assert.ok(queries.some(q=>q.sql.includes('auto_settlement')));
 await assert.rejects(()=>createEnrichedCoupon(env,{...payload,selections:[{fixture:f,market_code:'HOME',odds:'2.00'}]},{lookup}),/4.00/);
 await assert.rejects(()=>createEnrichedCoupon(env,{...payload,selections:[{fixture:{...f,id:'abc'},market_code:'HOME',odds:'5.00'}]},{lookup}),/ESPN/);
});
test('Admin access and Mini App composition are protected and valid',async()=>{
 assert.equal(isAdmin({CF_BOT_ADMIN_IDS:'8123, 9123'},8123),true);
 assert.equal(isAdmin({CF_BOT_ADMIN_IDS:'8123, 9123'},8124),false);
 const html=await miniPage().text();
 assert.match(html,/data-page="admin"/);
 assert.match(html,/adminSelectionRow/);
 assert.match(html,/\/brand.svg/);
 const scripts=[...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)].filter(x=>x[1].trim());
 assert.equal(scripts.length,1);
 assert.doesNotThrow(()=>new Script(scripts[0][1]));
});
