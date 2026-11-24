import {test} from 'node:test';
import assert from 'node:assert/strict';
import {anchorExtends} from './actufoot-v2-backup-worker.mjs';
const names=['audit','live_events','matches','news','publications','settings','statistics'];
const a='a'.repeat(64),b='b'.repeat(64),c='c'.repeat(64);
const old=Object.fromEntries(names.map(n=>[n,{generation:1,key_version:1,sha256:a}]));
const head={sequence:1,entry_hash:a,collections_json:JSON.stringify(old)};
test('same state accepted',()=>assert.equal(anchorExtends(head,{collections:old},{sequence:1,entry_hash:a},[a]),true));
test('truncation and fork rejected',()=>{
 assert.equal(anchorExtends(head,{collections:old},{sequence:0,entry_hash:'0'.repeat(64)},[]),false);
 assert.equal(anchorExtends(head,{collections:old},{sequence:2,entry_hash:b},[c,b]),false);
});
test('generation, key downgrade or same-generation replacement rejected',()=>{
 for(const changed of [{generation:0,key_version:1,sha256:a},{generation:2,key_version:0,sha256:b},{generation:1,key_version:1,sha256:b}]){
  assert.equal(anchorExtends(head,{collections:{...old,news:changed}},{sequence:1,entry_hash:a},[a]),false);
 }
});
test('append and rotation accepted',()=>assert.equal(anchorExtends(head,{collections:{...old,audit:{generation:2,key_version:2,sha256:b}}},{sequence:2,entry_hash:b},[a,b]),true));
