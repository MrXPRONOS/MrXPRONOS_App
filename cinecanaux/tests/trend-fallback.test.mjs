import test from 'node:test';
import assert from 'node:assert/strict';
import {runTrendRefresh, radarApi} from '../trend-radar.mjs';
import {formatRadarMissing} from '../radar-owner-ops.mjs';

// This fixture mimics public API shapes without requesting credentials or sending Telegram.
test('TVmaze provides new episodes without mislabelling them as TMDB trends', async () => {
 const original=globalThis.fetch;
 const stored=[],stamp=[];
 const show={id:123,name:'Example Series',url:'https://www.tvmaze.com/shows/123/example-series',
   image:{medium:'https://static.tvmaze.com/uploads/images/medium_portrait/12/12345.jpg'},
   summary:'<p>An original TV series.</p>',premiered:'2025-10-06'};
 globalThis.fetch=async (url) => {
   if(String(url).includes('/schedule/web?'))
     return Response.json([{id:55,_embedded:{show}}]);
   if(String(url).includes('graphql.anilist.co'))
     return Response.json({data:{Page:{media:[{id:444,title:{english:'Original Anime',romaji:'Original Anime'},
      description:'A current anime',coverImage:{large:'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx444-abcd.jpg'},seasonYear:2026}]}}});
   throw Error('unexpected '+url);
 };
 const DB={prepare(sql){let params=[];const statement={
   bind(...p){params=p;return statement;},
   async first(){return null;},
   async all(){return {results:[]};},
   async run(){
     if(sql.includes('INSERT INTO radar_titles'))stored.push(params);
     if(sql.includes('INSERT INTO radar_runs'))stamp.push(params);
     return {meta:{changes:1}};
   }
 };return statement;}};
 try{
   const result=await runTrendRefresh({DB});
   assert.ok(result.skipped.some(x=>String(x).includes('TMDB')));
   assert.equal(result.errors.length,0);
   assert.ok(stored.some(x=>x[0]==='tvmaze-series-123'),JSON.stringify(result));
   assert.ok(stamp.some(x=>x[0]==='trends_series'));
   assert.match(formatRadarMissing([{kind:'series',title:'Example Series',source_url:show.url}]),/tvmaze\.com/);
 }finally{globalThis.fetch=original;}
});

test('new fallback IDs are validated before recording clicks',async()=>{
 const db={prepare(){throw Error('Do not query DB on invalid ID');}};
 const r=await radarApi({DB:db},new Request('https://example.org/api/radar/click',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:'tvmaze-series-notnumber'})}));
 assert.equal(r.status,400);
});
