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
