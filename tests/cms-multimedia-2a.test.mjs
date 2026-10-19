import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {parseCmsMarkdown,serializeCmsBlocks} from "../assets/js/cms-block-editor.mjs";
import {checkCmsFile,uploadCmsFile} from "../assets/js/cms-media-library.mjs";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("Blocks preserve original headings, bullets, citations and links",()=>{
 const md="## Analyse\n\n- Première\n- Seconde\n\n> Citation\n\n[Lien](https://example.org)";
 assert.equal(serializeCmsBlocks(parseCmsMarkdown(md)),md);
});
test("Legacy rich HTML remains editable as raw content",()=>{
 const md='<div class="important">Contenu existant</div>';
 assert.equal(parseCmsMarkdown(md)[0].type,"raw");
 assert.equal(serializeCmsBlocks(parseCmsMarkdown(md)),md);
});
test("Image, video and SEO text serialization is safe",()=>{
 const md=serializeCmsBlocks([
  {type:"image",url:"https://cdn.example.org/cover.webp",alt:"Terrain de football"},
  {type:"video",url:"https://cdn.example.org/report.mp4"}]);
 assert.match(md,/!\[Terrain de football\]/);
 assert.match(md,/<video controls/);
 assert.equal(parseCmsMarkdown(md).length,2);
});
test("Unsafe URLs and missing image alt fail before saving",()=>{
 assert.throws(()=>serializeCmsBlocks([{type:"image",url:"javascript:alert(1)",alt:"x"}]),/invalide/);
 assert.throws(()=>serializeCmsBlocks([{type:"image",url:"https://example.org/x",alt:""}]),/alternatif/);
 assert.throws(()=>serializeCmsBlocks([{type:"video",url:"http://example.org/x"}]),/HTTPS/);
 assert.throws(()=>serializeCmsBlocks([{type:"link",url:"data:text/html,X",value:"Click"}]),/invalide/);
});
test("File signature and MIME are verified",()=>{
 const jpeg=new Uint8Array([255,216,255,...Array(13).fill(0)]);
 assert.equal(checkCmsFile({type:"image/jpeg",size:123},jpeg).ext,"jpg");
 assert.throws(()=>checkCmsFile({type:"image/jpeg",size:123},new Uint8Array(16)),/Signature/);
 assert.throws(()=>checkCmsFile({type:"image/svg+xml",size:123},jpeg),/Format/);
 const mp4=new Uint8Array(16);mp4.set([102,116,121,112],4);
 assert.equal(checkCmsFile({type:"video/mp4",size:200},mp4).kind,"video");
 assert.throws(()=>checkCmsFile({type:"video/mp4",size:32*1048576},mp4),/volumineux/);
});
const video=()=>{
 const bytes=new Uint8Array(16);bytes.set([102,116,121,112],4);
 return {type:"video/mp4",size:200,name:"video.mp4",
 slice:()=>({arrayBuffer:async()=>bytes.buffer})};
};
function fakeDb(fail=false){
 const uploads=[],deleted=[];
 const bucket={upload:async(path,body,opts)=>{uploads.push({path,opts});return{error:null};},
 remove:async paths=>{deleted.push(...paths);return {error:null};},
 getPublicUrl:path=>({data:{publicUrl:"https://cdn.example.org/"+path}})};
 const sb={
 auth:{getUser:async()=>({data:{user:{id:"11111111-1111-4111-8111-111111111111"}},error:null})},
 storage:{from:()=>bucket},
 from:()=>({insert:row=>({select:()=>({single:async()=>fail?
 {data:null,error:{message:"Database rejection"}}:{data:{id:"m1",...row},error:null}})})})
 };
 return {sb,uploads,deleted};
}
test("Video uploads are owner scoped and never overwrite existing files",async()=>{
 const x=fakeDb(),value=await uploadCmsFile(x.sb,video());
 assert.match(x.uploads[0].path,/^cms\/11111111-1111-4111-8111-111111111111\/[0-9a-f-]+\.mp4$/);
 assert.equal(x.uploads[0].opts.upsert,false);
 assert.equal(value.kind,"video");
});
test("Metadata failure rolls uploaded file back",async()=>{
 const x=fakeDb(true);
 await assert.rejects(()=>uploadCmsFile(x.sb,video()),/Database rejection/);
 assert.deepEqual(x.deleted,[x.uploads[0].path]);
});
test("Migration enforces storage and CMS revision authorization",()=>{
 const sql=read("supabase/migrations/20261019031500_cms_media_revisions_storage.sql");
 for(const pattern of [/cms_media_admin_insert ON storage\.objects/,/cms_media_admin ON public\.cms_media/,
 /cms_revisions_admin_read/,/cms_revision_audit AFTER INSERT OR UPDATE OR DELETE/])
   assert.match(sql,pattern);
 assert.doesNotMatch(sql,/GRANT ALL ON public\.cms_media TO anon/);
});
test("CMS screens use real editor and image picker, and public video is sanitized",()=>{
 const admin=read("assets/js/admin-real.js"),site=read("assets/js/main.js");
 for(const k of ["articles","conseils","infos"])assert.ok(admin.includes('kind:"'+k+'"'));
 assert.ok(admin.includes('mountCmsMediaFieldPicker(sb,$("b_image"))'));
 assert.ok(admin.includes("cmsEditor.getMarkdown()"));
 assert.ok(site.includes('"video",'));
 assert.ok(site.includes("isSafeCmsUrl(value"));
});
