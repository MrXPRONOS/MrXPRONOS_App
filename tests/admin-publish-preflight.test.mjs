import test from "node:test";
import assert from "node:assert/strict";
import { CMS_PATHS, inspectPublishFiles } from "../supabase/functions/publish/guards.mjs";

const empty = () => Object.fromEntries(CMS_PATHS.map(path => [path, "[]"]));
const withRows = (which, rows, base=empty()) => ({...base, [which]:JSON.stringify(rows)});

test("No change: identical five CMS files must not create a commit",()=>{
  const result=inspectPublishFiles(empty(),empty());
  assert.equal(result.has_changes,false);
  assert.equal(result.empty_all,true);
  assert.deepEqual(result.emptied_files,[]);
  assert.equal(Object.keys(result.changes).length,5);
});
test("No change: harmless whitespace does not count as a change",()=>{
  const result=inspectPublishFiles(empty(),Object.fromEntries(CMS_PATHS.map(x=>[x,"[\n]"])));
  assert.equal(result.has_changes,false);
});
test("Real content edit produces a correct difference report",()=>{
  const before=withRows("articles.json",[{slug:"alpha",title:"First"}]);
  const after=withRows("articles.json",[{slug:"alpha",title:"Edited"}]);
  const result=inspectPublishFiles(after,before);
  assert.equal(result.has_changes,true);
  assert.deepEqual(result.changes["articles.json"],{before:1,after:1,different:true});
  assert.deepEqual(result.emptied_files,[]);
});
test("One existing category becomes empty: destructive-change confirmation is required",()=>{
  const before=withRows("articles.json",[{slug:"alpha"}]);
  const result=inspectPublishFiles(empty(),before);
  assert.deepEqual(result.emptied_files,["articles.json"]);
  assert.equal(result.has_changes,true);
});
test("Several emptying files are all identified, not just the first",()=>{
  const before=withRows("bookmakers.json",[{name:"Book"}],withRows("bonus.json",[{bookmaker:"B"}]));
  assert.deepEqual(inspectPublishFiles(empty(),before).emptied_files,["bonus.json","bookmakers.json"]);
});
test("Unknown or missing file is rejected before publication",()=>{
  const missing=empty(); delete missing["bonus.json"];
  assert.throws(()=>inspectPublishFiles(missing,empty()),/incomplet/);
  const extra={...empty(),".env":"[]"};
  assert.throws(()=>inspectPublishFiles(extra,empty()),/incomplet/);
});
test("Invalid CMS file structure is rejected",()=>{
  assert.throws(()=>inspectPublishFiles(withRows("infos.json",null),empty()),/invalide/);
  assert.throws(()=>inspectPublishFiles(withRows("infos.json","not-array"),empty()),/invalide/);
  assert.throws(()=>inspectPublishFiles({...empty(),"infos.json":"{broken"},empty()),SyntaxError);
  assert.throws(()=>inspectPublishFiles(empty(),{...empty(),"conseils.json":"false"}),/invalide/);
});
test("Preflight inspection must not mutate inputs",()=>{
  const current=empty(),next=withRows("conseils.json",[{slug:"test"}]);
  const snapshot=JSON.stringify({current,next});
  inspectPublishFiles(next,current);
  assert.equal(JSON.stringify({current,next}),snapshot);
});
