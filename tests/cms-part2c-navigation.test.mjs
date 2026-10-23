import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {filterCmsRows,normalizeCmsSearch} from "../assets/js/cms-list-filters.mjs";
import {filterCmsMedia,listCmsMedia} from "../assets/js/cms-media-library.mjs";

const editorial=[
 {id:"a",title:"Le derby de Lomé",status:"published",category:"Football",tags:["Coupe"],updated_at:"2026-10-19T12:00:00Z"},
 {id:"b",title:"Stratégie prudente",status:"draft",category:"Éducation",tags:["Débutants"],updated_at:"2026-10-18T12:00:00Z"},
 {id:"c",title:"Pronostic Liga",status:"published",category:"Football",tags:["Espagne"],updated_at:"2026-10-17T12:00:00Z"}
];
test("accent insensitive query covers titles, tags, category and user-visible names",()=>{
 assert.equal(normalizeCmsSearch("Éducation"),"education");
 assert.deepEqual(filterCmsRows(editorial,{search:"lome"}).map(r=>r.id),["a"]);
 assert.deepEqual(filterCmsRows(editorial,{search:"débutants"}).map(r=>r.id),["b"]);
 assert.deepEqual(filterCmsRows(editorial,{search:"espagne"}).map(r=>r.id),["c"]);
 assert.deepEqual(filterCmsRows([{id:"d",name:"Bookmaker Externe",status:"draft"}],{search:"externe"}).map(r=>r.id),["d"]);
});
test("status/category filters combine and stable sorts do not mutate originals",()=>{
 const snapshot=[...editorial];
 assert.deepEqual(filterCmsRows(editorial,{status:"published",category:"football"}).map(r=>r.id),["a","c"]);
 assert.deepEqual(filterCmsRows(editorial,{status:"draft",category:"football"}),[]);
 assert.deepEqual(filterCmsRows(editorial,{order:"oldest"}).map(r=>r.id),["c","b","a"]);
 assert.deepEqual(filterCmsRows(editorial,{order:"title"}).map(r=>r.id),["a","c","b"]);
 assert.deepEqual(editorial,snapshot);
 assert.deepEqual(filterCmsRows(null),[]);
});
test("media filters by kind and searches caption, alt and filenames",()=>{
 const rows=[
  {id:"i",kind:"image",original_name:"Stade-Lome.webp",alt_text:"Stade de Kégué",caption:"Terrain"},
  {id:"v",kind:"video",original_name:"video.mp4",caption:"Résumé du match"},
  {id:"i2",kind:"image",original_name:"ballon.png",caption:"Football"}
 ];
 assert.deepEqual(filterCmsMedia(rows,{search:"Kegue"}).map(m=>m.id),["i"]);
 assert.deepEqual(filterCmsMedia(rows,{kind:"video"}).map(m=>m.id),["v"]);
 assert.deepEqual(filterCmsMedia(rows,{kind:"image",search:"résumé"}),[]);
});
test("media list reads the requested page and preserves public display URLs",async()=>{
 let rangeArgs;
 const rows=[{id:"m1",kind:"image",storage_path:"cms/11111111-1111-4111-8111-111111111111.webp",thumbnail_path:null}];
 const query={order:()=>query,range:async(a,b)=>{rangeArgs=[a,b];return{data:rows,error:null}}};
 const db={from:table=>{assert.equal(table,"cms_media");return{select:()=>query}}};
 const got=await listCmsMedia(db,{offset:48,pageSize:48});
 assert.deepEqual(rangeArgs,[48,95]);
 assert.match(got[0].url,/https:\/\/br-winter-truth-b9of9tss\.storage\./);
 assert.ok(got[0].url.endsWith("/cms/11111111-1111-4111-8111-111111111111.webp"));
 await assert.rejects(()=>listCmsMedia(db,{offset:-1}),/invalide/);
});
test("five CMS lists have new controls without altering publication, live or cron pipelines",()=>{
 const admin=readFileSync(new URL("../assets/js/admin-real.js",import.meta.url),"utf8");
 for(const kind of ["articles","conseils","informations","bonus","bookmakers"]){
  assert.match(admin,new RegExp('kind:"'+kind+'"'));
 }
 const media=readFileSync(new URL("../assets/js/cms-media-library.mjs",import.meta.url),"utf8");
 assert.match(media,/Charger les médias suivants/);
 assert.match(media,/Rechercher parmi les médias chargés/);
});
