import test from 'node:test';
import assert from 'node:assert/strict';
import {simklPublicTrends,runTrendRefresh} from '../trend-radar.mjs';
import {formatRadarMissing} from '../radar-owner-ops.mjs';

const entries={
 films:{title:'Example Popular Film',year:2026,poster:'ab/cd123',url:'https://simkl.com/movies/1234/example-popular-film',ids:{simkl:1234},rank:1},
 series:{title:'Example Popular Series',year:2025,poster:'ab/cd456',url:'https://simkl.com/tv/2345/example-popular-series',ids:{simkl:2345},rank:1},
 animes:{title:'Example Popular Anime',year:2026,poster:'ab/cd789',url:'https://simkl.com/anime/3456/example-popular-anime',ids:{simkl:3456},rank:1}
};

test('Simkl keyless weekly trending charts produce genuine category-specific references', async () => {
 const original=globalThis.fetch,requests=[];
 globalThis.fetch=async(url,opts)=>{
   requests.push(String(url));
   const kind=String(url).includes('/movies/')?'films':String(url).includes('/tv/')?'series':'animes';
   assert.equal(opts.headers['User-Agent'],'CineRadar/1.2');
   return Response.json([entries[kind]]);
 };
 try{
  for(const kind of ['films','series','animes']){
   const actual=await simklPublicTrends(kind);
   assert.equal(actual.rows.length,1);
   assert.equal(actual.rows[0].kind,kind);
   assert.match(actual.rows[0].poster,/^https:\/\/simkl\.in\/posters\//);
   assert.equal(actual.rows[0].sourceUrl,entries[kind].url);
   assert.match(formatRadarMissing([{
     kind,title:actual.rows[0].title,source_url:actual.rows[0].sourceUrl
   }]),/simkl\.com/);
  }
  assert.equal(requests.length,3);
 }finally{globalThis.fetch=original;}
});

test('malformed Simkl records cannot inject external movie links or posters',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>Response.json([
  {title:'Misleading',poster:'https://evil.test/file.jpg',url:'https://evil.test/videos',ids:{simkl:555}},
  {title:'Valid',poster:'folder/file',url:'https://simkl.com/movies/777/valid',ids:{simkl:777}}
 ]);
 try{
  const rows=(await simklPublicTrends('films')).rows;
  assert.deepEqual(rows.map(x=>x.id),['simkl-films-777']);
 }finally{globalThis.fetch=original;}
});
