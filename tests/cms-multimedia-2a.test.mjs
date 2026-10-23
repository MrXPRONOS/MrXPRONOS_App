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
function fakeDb(fail=false) {
 const uploads=[],deleted=[];
 const sb={
  auth:{
   getUser:async()=>({data:{user:{id:"11111111-1111-4111-8111-111111111111"}},error:null}),
   getSession:async()=>({data:{session:{access_token:"fake-test-token"}},error:null})
  },
  from:table=>{
   assert.equal(table,"cms_media");
   return {insert:row=>({select:()=>({single:async()=>fail?
    {data:null,error:{message:"Database rejection"}}:{data:{id:"m1",...row},error:null}})})};
  }
 };
 return {sb,uploads,deleted};
}
async function fakeMediaNetwork(state,callback) {
 const original=globalThis.fetch;
 globalThis.fetch=async (input,opts={})=>{
  const path=new URL(String(input)).pathname;
  if(path==="/upload"){
   assert.match(opts.headers.Authorization,/^Bearer fake-test-token$/);
   assert.equal(opts.method,"POST");
   assert.equal(opts.headers["Content-Type"],"video/mp4");
   assert.equal(opts.body.type,"video/mp4");
   const key="cms/11111111-1111-4111-8111-111111111111.mp4";
   state.uploads.push(key);
   return {ok:true,status:201,json:async()=>({key,url:"https://cdn.example.org/"+key})};
  }
  if(path==="/object"){
   assert.equal(opts.method,"DELETE");
   state.deleted.push(new URL(String(input)).searchParams.get("key"));
   return {ok:true,status:200,json:async()=>({deleted:true})};
  }
  throw Error("Unexpected network request: "+String(input));
 };
 try{return await callback()}finally{globalThis.fetch=original}
}
test("Video uploads pass an admin JWT to Cloudflare and never expose S3 credentials",async()=>{
 const x=fakeDb();
 const value=await fakeMediaNetwork(x,()=>uploadCmsFile(x.sb,video()));
 assert.match(x.uploads[0],/^cms\/[0-9a-f-]{36}\.mp4$/);
 assert.equal(value.kind,"video");
 assert.equal(value.url,"https://cdn.example.org/"+x.uploads[0]);
});
test("Metadata failure triggers Cloudflare object rollback",async()=>{
 const x=fakeDb(true);
 await fakeMediaNetwork(x,async()=>{
  await assert.rejects(()=>uploadCmsFile(x.sb,video()),/Database rejection/);
 });
 assert.deepEqual(x.deleted,x.uploads);
});
test("Neon CMS media requests enforce admin login and storage object validation",()=>{
 const worker=read("cloudflare/mrxpronos-admin-media/worker.mjs");
 for(const pattern of [/verifyAdmin\(bearer,env\)/,/NEON_S3_SECRET_ACCESS_KEY/,/signatureOk\(mime/])
  assert.match(worker,pattern);
 assert.doesNotMatch(worker,/SUPABASE_URL|supabase\.co/i);
});
test("CMS screens use real editor and image picker, and public video is sanitized",()=>{
 const admin=read("assets/js/admin-real.js"),site=read("assets/js/main.js");
 for(const k of ["articles","conseils","infos"])assert.ok(admin.includes('kind:"'+k+'"'));
 assert.ok(admin.includes('mountCmsMediaFieldPicker(sb,$("b_image"))'));
 assert.ok(admin.includes("cmsEditor.getMarkdown()"));
 assert.ok(site.includes('"video",'));
 assert.ok(site.includes("isSafeCmsUrl(value"));
});
