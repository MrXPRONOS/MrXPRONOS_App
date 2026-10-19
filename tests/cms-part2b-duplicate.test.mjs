import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createCmsDraftCopy} from "../assets/js/cms-duplicate.mjs";

test("article copy is inactive, draft and generates a collision-free slug",()=>{
 const original={id:"uuid-original",slug:"analyse-match",title:"Analyse",content:"## Analyse",tags:["foot"],status:"published",active:true,published_at:"2026-10-19",created_at:"2026-01-01"};
 const rows=[{slug:"analyse-match-copie"},{slug:"analyse-match-copie-2"}];
 const copy=createCmsDraftCopy("articles",original,rows);
 assert.equal(copy.slug,"analyse-match-copie-3");
 assert.equal(copy.status,"draft");assert.equal(copy.active,false);
 assert.equal(copy.id,undefined);assert.equal(copy.published_at,undefined);assert.equal(copy.created_at,undefined);
 assert.deepEqual(copy.tags,["foot"]);copy.tags.push("new");assert.deepEqual(original.tags,["foot"]);
});
test("copies of all content types strip ID, scheduling and audit metadata",()=>{
 for(const type of ["conseils","infos","bonus","bookmakers"]){
  const copy=createCmsDraftCopy(type,{id:"existing",title:"Titre",name:"Nom",slug:"test",status:"published",active:true,
     start_date:"2026-10-20",end_date:"2026-10-23",published_at:"2026-10-19",updated_at:"2026-10-19",created_by:"admin",description:"texte"});
  assert.equal(copy.id,undefined);assert.equal(copy.published_at,undefined);
  assert.equal(copy.start_date,undefined);assert.equal(copy.end_date,undefined);
  assert.equal(copy.updated_at,undefined);assert.equal(copy.created_by,undefined);
  assert.equal(copy.status,"draft");assert.equal(copy.active,false);
 }
});
test("unknown type and missing source are rejected",()=>{
 assert.throws(()=>createCmsDraftCopy("fake",{}),/invalide/);
 assert.throws(()=>createCmsDraftCopy("articles",null),/invalide/);
});
test("admin includes duplicate actions, content remains unpublished, and bucket is correctly disclosed",()=>{
 const admin=readFileSync(new URL("../assets/js/admin-real.js",import.meta.url),"utf8");
 assert.match(admin,/attachDuplicateButtons\(root,"\[data-id\]",rows,"articles"/);
 assert.match(admin,/attachDuplicateButtons\(root,"\[data-bonus-id\]",bonusRows,"bonus"/);
 assert.match(admin,/delete \$\(saveButtonId\)\.dataset\.id/);
 assert.match(admin,/bucket public/);
 const editor=readFileSync(new URL("../assets/js/cms-block-editor.mjs",import.meta.url),"utf8");
 assert.match(editor,/render\(\);commit\(\);list\.lastElementChild/);
});
