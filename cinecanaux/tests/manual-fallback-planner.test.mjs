import test from 'node:test';
import assert from 'node:assert/strict';
import {planMovies,planSeasons,planCourses,selectManualCycle}
 from '../manual-fallback-planner.mjs';

const chat='-1001234567890';
const base=(id,category,kind,caption,file='',unique='')=>({
 chat_id:chat,message_id:id,category,kind,caption,filename:file,
 file_unique_id:unique,state:'indexed'
});
function movie(id=1,name='Sample Movie',year=2025,unique='media-123456'){
 return [
  base(id,'films','poster','Titre: '+name+'\nAnnée: '+year),
  base(id+1,'films','video','Titre: '+name+'\nAnnée: '+year,
   'sample.mkv',unique),
 ];
}
function series(){
 return [
  base(1,'series','poster','Titre: Une Série\nS01'),
  base(2,'series','video','Titre: Une Série\nS01E01','s01e01.mkv','episode-0001'),
  base(3,'series','video','Titre: Une Série\nS01E02','s01e02.mkv','episode-0002'),
 ];
}
function course(){
 return [
  base(1,'formation_business','poster','Cours: vente-2026\nAuteur: Formateur Autorisé'),
  base(2,'formation_business','course_file',
    'Cours: vente-2026\nTotal: 2\nPartie: 1/2',
    'part1.pdf','file-class-001'),
  base(3,'formation_business','course_file',
    'Cours: vente-2026\nTotal: 2\nPartie: 2/2',
    'part2.zip','file-class-002'),
 ];
}
const flags={personalStatus:'session_revoked',fallbackEnabled:true,
 botReady:true,stockReady:true,rightsAttested:true,receiptsReady:true};

test('single verified film and poster become one item',()=>{
 const p=planMovies(movie());
 assert.equal(p.items.length,1);
 assert.equal(p.items[0].poster_message_id,1);
 assert.equal(p.items[0].video_message_id,2);
});
test('missing poster is rejected',()=>{
 const p=planMovies(movie().slice(1));
 assert.equal(p.items.length,0);
 assert.equal(p.review[0].reason,'incomplete_or_ambiguous_film');
});
test('film requires explicit title and release year',()=>{
 const p=planMovies(movie().map(x=>({...x,caption:'Film inconnu'})));
 assert.equal(p.items.length,0);
});
test('same source media used for two titles is quarantined',()=>{
 const p=planMovies([...movie(1,'A Movie',2025,'same-file-123'),
  ...movie(3,'Other Movie',2025,'same-file-123')]);
 assert.equal(p.items.length,0);
 assert.ok(p.review.some(x=>x.reason==='film_media_collision'));
});
test('valid two-episode season stays one batch',()=>{
 const p=planSeasons(series());
 assert.equal(p.items.length,1);
 assert.deepEqual(p.items[0].episodes.map(x=>x.number),[1,2]);
});
test('missing E01 blocks publishing E02',()=>{
 const p=planSeasons([series()[0],series()[2]]);
 assert.equal(p.items.length,0);
 assert.equal(p.review[0].reason,'series_episode_gap');
});
test('published E01 allows progressive E02',()=>{
 const p=planSeasons([series()[0],series()[2]],{
  publishedEpisodes:new Set(['series:une serie:S01:E1'])});
 assert.equal(p.items.length,1);
 assert.deepEqual(p.items[0].episodes.map(x=>x.number),[2]);
});
test('different original video bytes for same episode are reviewed',()=>{
 const p=planSeasons([...series(),{
  ...series()[1],message_id:4,file_unique_id:'episode-9999'}]);
 assert.equal(p.items.length,0);
});
test('invalid or duplicated episode fingerprints block the season',()=>{
 const p=planSeasons([series()[0],series()[1],{
  ...series()[2],file_unique_id:'episode-0001'}]);
 assert.equal(p.items.length,0);
 assert.equal(p.review[0].reason,'same_video_for_multiple_episodes');
});
test('course requires every numbered part and exactly one cover',()=>{
 const p=planCourses(course());
 assert.equal(p.items.length,1);
 assert.deepEqual(p.items[0].parts.map(x=>x.number),[1,2]);
});
test('course incomplete blocks all parts',()=>{
 const p=planCourses(course().slice(0,2));
 assert.equal(p.items.length,0);
});
test('course executable extension refused even with explicit index',()=>{
 const files=course().map(x=>({...x}));
 files[1].filename='run.exe';
 const p=planCourses(files);
 assert.equal(p.items.length,0);
 assert.ok(p.review.some(x=>x.reason==='course_part_or_format_invalid'));
});
test('fallback never activates for personal rate limits or network ambiguity',()=>{
 const plans={movies:planMovies(movie())};
 for(const status of ['ok','flood_wait','peer_flood','uncertain_send','network_timeout','unknown']){
  const p=selectManualCycle(plans,{...flags,personalStatus:status});
  assert.equal(p.eligible.length,0,status);
 }
});
test('fallback cannot activate with incomplete bot/stock/receipts rights',()=>{
 const plans={movies:planMovies(movie())};
 for(const key of ['fallbackEnabled','botReady','stockReady','rightsAttested','receiptsReady']){
  const p=selectManualCycle(plans,{...flags,[key]:false});
  assert.equal(p.eligible.length,0,key);
 }
});
test('film quota uses previous normal-mode postings',()=>{
 const plans={movies:planMovies(movie())};
 assert.equal(selectManualCycle(plans,{...flags,existingCounts:{films:2}}).eligible.length,0);
 assert.equal(selectManualCycle(plans,{...flags,existingCounts:{films:1}}).eligible.length,1);
});
test('previously published file is blocked by durable identity',()=>{
 const plans={movies:planMovies(movie())};
 assert.equal(selectManualCycle(plans,{...flags,
  publishedFiles:new Set(['media-123456'])}).eligible.length,0);
 assert.equal(selectManualCycle(plans,{...flags,
  publishedKeys:new Set(['films:sample movie:2025'])}).eligible.length,0);
 assert.equal(selectManualCycle(plans,{...flags,
  uncertainKeys:new Set(['films:sample movie:2025'])}).eligible.length,0);
});
test('training cap is one per category and video cap two',()=>{
 const courses={items:[...planCourses(course()).items,
  ...planCourses(course().map(x=>({...x,message_id:x.message_id+10,
   caption:x.caption.replace('vente-2026','vente-2027'),
   file_unique_id:x.file_unique_id+'-other'}))).items]};
 const chosen=selectManualCycle({courses},flags);
 assert.equal(chosen.eligible.length,1);
 assert.equal(chosen.remaining.formation_business,0);
});
test('malformed count blocks all candidates',()=>{
 const p=selectManualCycle({movies:planMovies(movie())},
  {...flags,existingCounts:{films:-2}});
 assert.equal(p.eligible.length,0);
 assert.equal(p.reason,'invalid_existing_quota');
});

test('cross-category reuse of the same video quarantines both items',()=>{
 const movieItem=planMovies(movie()).items[0];
 const courseItem=planCourses(course()).items[0];
 const wrong={...courseItem,parts:courseItem.parts.map((p,i)=>({
  ...p,file_unique_id:i===0?'media-123456':p.file_unique_id
 }))};
 const decision=selectManualCycle({movies:{items:[movieItem]},courses:{items:[wrong]}},flags);
 assert.equal(decision.eligible.length,0);
 assert.equal(decision.blocked.filter(x=>x.reason==='cross_category_media_collision').length,2);
});
