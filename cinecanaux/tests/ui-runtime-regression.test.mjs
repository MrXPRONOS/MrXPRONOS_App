import test from 'node:test';
import assert from 'node:assert/strict';
import {Script} from 'node:vm';
import {APP_HTML} from '../app-page.mjs';

const scripts=[...APP_HTML.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]).filter(s=>s.trim());
const directory=scripts.find(s=>s.includes('function buildCard('));
const navigation=scripts.find(s=>s.includes('function featuredCard('));

test('every inline UI script parses as JavaScript, not just the surrounding mjs wrapper',()=>{
 assert.ok(scripts.length>=2,'Expected directory and navigation scripts');
 for(const source of scripts)assert.doesNotThrow(()=>new Script(source));
});
test('directory cards own the avatar helper they call',()=>{
 assert.ok(directory,'Directory script missing');
 assert.ok(directory.includes('function showChannelImage('),'Directory image helper must be in same closure');
 assert.ok(directory.includes('function photoHost(')||directory.includes('const photoHost='),'Avatar URL validator missing');
 assert.ok(directory.includes('showChannelImage(img,directAvatar,c.photo,'));
});
test('home/discovery cards own their image fallback helpers',()=>{
 assert.ok(navigation,'Navigation script missing');
 assert.ok(navigation.includes('function showChannelImage('));
 assert.ok(navigation.includes('const photoHost='));
 assert.ok(navigation.includes('showChannelImage(img,url,null,'));
});
test('Films, Series, Animes shortcuts select a type filter, not free-text matches',()=>{
 assert.ok(navigation.includes('const category=["films","series","animes"].includes(term)?term:null'));
 assert.ok(navigation.includes('button.click();'));
 assert.ok(navigation.includes('q.value=category?"":term;'));
});
test('all category controls remain wired to an API-backed directory',()=>{
 for(const type of ['films','series','animes']){
  assert.ok(APP_HTML.includes('data-type="'+type+'"'));
 }
 assert.ok(directory.includes('applyFilters();load(true);'));
 assert.ok(APP_HTML.includes('"/api/search?q="'));
 assert.ok(APP_HTML.includes('const PRELOADED_CATALOG=null;'));
});

test('type shortcut actually selects the right button and clears the search term',()=>{
 const body=navigation.match(/function setFilter\(term\)\{([\s\S]*?)\n\}/)?.[1];
 assert.ok(body,'setFilter implementation missing');
 for(const kind of ['films','series','animes']){
  const state={selected:'series',query:'previous query',hash:'',focus:false,triggered:false};
  const q={get value(){return state.query},set value(v){state.query=v},dispatchEvent(){state.triggered=true},focus(){state.focus=true}};
  const all={get classList(){return {contains:()=>state.selected==='all'}},click(){state.selected='all'}};
  const cats=Object.fromEntries(['films','series','animes'].map(t=>[t,{get classList(){return{contains:()=>state.selected===t}},click(){state.selected=t}}]));
  const context={
   setHash(p){state.hash=p},
   $(id){assert.equal(id,'search');return q},
   document:{querySelector(sel){
    if(sel==='#tabs [data-type="all"]')return all;
    for(const t of ['films','series','animes'])if(sel==='#tabs [data-type="'+t+'"]')return cats[t];
    return null;
   }},
   Event:class Event{},
   setTimeout(fn){fn()}
  };
  const fn=new Function('term','setHash','$','document','Event','setTimeout',body);
  fn(kind,context.setHash,context.$,context.document,context.Event,context.setTimeout);
  assert.equal(state.hash,'explorer');
  assert.equal(state.selected,kind);
  assert.equal(state.query,'');
  assert.equal(state.triggered,true);
  assert.equal(state.focus,true);
 }
});

test('home and discovery hydrate immediately from the same preloaded catalog as Explorer',()=>{
 assert.ok(directory.includes('window.__CINERADAR_INITIAL_CATALOG__=PRELOADED_CATALOG'));
 assert.ok(navigation.includes('const embedded=window.__CINERADAR_INITIAL_CATALOG__'));
 const bootstrap=navigation.indexOf('const embedded=window.__CINERADAR_INITIAL_CATALOG__');
 const fetchIndex=navigation.indexOf('fetch("/api/catalog?limit=80"');
 assert.ok(bootstrap!==-1&&fetchIndex>bootstrap,'Home must render before the network request');
 const step=navigation.slice(bootstrap,fetchIndex);
 for(const fn of ['miniFeatured();','discover();','genreContent();','cardDecorate();'])assert.ok(step.includes(fn),fn+' omitted from instant hydration');
});

test('category counts use correct French singular/plural',()=>{
 assert.ok(APP_HTML.includes('count+(count===1?" canal":" canaux")+" dans l’annuaire"'));
 assert.ok(!APP_HTML.includes('count+" canal"+(count===1?"":"x")'));
});

test('both directory and home use versioned real-avatar URL on the first load',()=>{
 for(const block of [directory,navigation]){
  assert.ok(block.includes('source+"?v=3"'));
  assert.ok(block.includes('source+"?v=3&refresh=1"'));
  assert.ok(block.includes('img.src=candidates[0];'));
 }
});
