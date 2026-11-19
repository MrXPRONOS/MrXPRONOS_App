import test from 'node:test';
import assert from 'node:assert/strict';
import {runInNewContext} from 'node:vm';
import {APP_HTML} from '../app-page.mjs';

const scripts=[...APP_HTML.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const directory=scripts.find(s=>s.includes('function buildCard('));
assert.ok(directory,'Directory script should exist');

function createHarness(){
 const start=directory.indexOf('function matchesSelectedCategory(');
 const end=directory.indexOf('\nasync function postV2(',start);
 assert.ok(start>=0&&end>start,'Pure filter logic must be present');
 const source=directory.slice(start,end);
 const buttons=['all','films','series','animes'].map(t=>{
  const active=new Set(t==='all'?['active']:[]);
  return {dataset:{type:t},pressed:t==='all'?'true':'false',
   classList:{toggle(k,on){if(on)active.add(k);else active.delete(k);},contains(k){return active.has(k);}},
   setAttribute(key,value){if(key==='aria-pressed')this.pressed=value;}};
 });
 const controls={
  sort:{value:'relevant'},
  count:{textContent:''},
  cards:{dataset:{filterLoading:'false'},children:[],replaceChildren(...children){this.children=children;},append(child){this.children.push(child);}},
  'cine-filter-summary':{textContent:''},
  'cine-filter-reset':{hidden:true}
 };
 let harness;
 const requests=[];
 const sandbox={
  document:{documentElement:{dataset:{}},querySelectorAll(q){return q==='#tabs [data-type]'?buttons:[];}},
  $:id=>controls[id],
  node:(tag,cls,text)=>({tag,cls,textContent:text}),
  button:(label,cls,callback)=>({label,cls,callback}),
  api:url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject})),
  render(){controls.cards.dataset.filterLoading='false';},
  enqueueVisiblePhotos(){},
  clearTimeout(){},
 };
 harness=runInNewContext(`(()=>{
  let type='all',query='',channels=[],allChannels=[],lastFetch=0,lastResultKey='',filterRequestId=0,searchDelay=null;
  const selectedTypes=new Set();
  ${source}
  return {
   chooseCategory,load,applyFilters,matchesSelectedCategory,syncCategoryControls,
   changeQuery(q){query=q;filterRequestId++},
   snapshot(){return {selected:[...selectedTypes],types:channels.map(c=>c.type),ids:channels.map(c=>c.id),type,lastResultKey,filterRequestId};}
  };
 })()`,sandbox);
 return {harness,buttons,controls,requests};
}
const channels=[
 {id:1,type:'films',tags:'films, action'},
 {id:2,type:'series',tags:'series, romance'},
 {id:3,type:'animes',tags:'animes'}
];
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('multi-select uses OR; deselecting a category never filters a stale, truncated response',async()=>{
 const {harness:h,buttons,controls,requests}=createHarness();
 h.chooseCategory('films');
 assert.equal(requests.length,1);
 assert.match(requests[0].url,/types=films/);
 h.chooseCategory('series');
 assert.equal(requests.length,2);
 assert.match(requests[1].url,/types=films%2Cseries/);
 assert.equal(buttons[1].pressed,'true');
 assert.equal(buttons[2].pressed,'true');
 assert.equal(buttons[0].pressed,'false');
 assert.match(controls['cine-filter-summary'].textContent,/Films \+ Séries/);
 assert.equal(controls['cine-filter-reset'].hidden,false);
 // The newer result must be displayed, even if the earlier HTTP request finishes afterward.
 requests[1].resolve({channels:[channels[0],channels[1]]});
 await tick();
 assert.equal(h.snapshot().ids.join(','),'1,2');
 requests[0].resolve({channels:[channels[0]]});
 await tick();
 assert.equal(h.snapshot().ids.join(','),'1,2','Old response must not overwrite the current selection');

 h.chooseCategory('films'); // keep series only
 assert.equal(requests.length,3);
 assert.match(requests[2].url,/types=series(?:&|$)/);
 assert.equal(controls.cards.dataset.filterLoading,'true','Show loading, not a false empty list');
 requests[2].resolve({channels:[channels[1]]});
 await tick();
 assert.equal(h.snapshot().ids.join(','),'2');
 assert.equal(buttons[1].pressed,'false');
 assert.equal(buttons[2].pressed,'true');

 h.chooseCategory('series'); // none selected -> all categories
 assert.equal(requests.length,4);
 assert.match(requests[3].url,/types=&/);
 requests[3].resolve({channels});
 await tick();
 assert.equal(h.snapshot().ids.join(','),'1,2,3');
 assert.equal(buttons[0].pressed,'true');
 assert.equal(controls['cine-filter-reset'].hidden,true);
});
test('stale search, sorted results, category tags, and reset work without leaking previous results',async()=>{
 const {harness:h,controls,requests}=createHarness();
 assert.equal(h.matchesSelectedCategory({type:'films',tags:'animes, romance'},new Set(['romance'])),true,'Comma-separated tags must be trimmed');
 h.chooseCategory('animes');
 h.changeQuery('cinema');
 h.load(true);
 assert.match(requests[1].url,/q=cinema/);
 requests[0].resolve({channels:[channels[2]]});
 await tick();
 assert.equal(controls.cards.dataset.filterLoading,'true');
 requests[1].resolve({channels:[channels[2]]});
 await tick();
 assert.equal(h.snapshot().ids.join(','),'3');
 controls.sort.value='rated';
 h.load(true);
 assert.match(requests[2].url,/sort=rated/);
 requests[2].resolve({channels:[channels[2]]});
 await tick();
 h.chooseCategory('all');
 assert.match(requests[3].url,/types=&/);
 requests[3].resolve({channels});
 await tick();
 assert.equal(h.snapshot().selected.length,0);
 assert.equal(controls['cine-filter-summary'].textContent,'Toutes les catégories');
});
test('UI keeps advanced controls accessible and never reports fake zero during loading',()=>{
 assert.ok(APP_HTML.includes('id="cine-filter-state"'));
 assert.ok(APP_HTML.includes('id="cine-filter-reset"'));
 assert.ok(APP_HTML.includes('id="cine-filter-summary"'));
 assert.ok(APP_HTML.includes('details.append(summary,nav,$("cine-filter-state"),tools)'));
 assert.ok(APP_HTML.includes('if(root.dataset.filterLoading==="true")return;'));
 assert.ok(!directory.includes('if(fetchPending)return fetchPending'));
});
