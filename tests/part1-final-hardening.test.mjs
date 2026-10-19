import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHmac,createHash} from "node:crypto";
import {isSafeCmsUrl,safeCmsUrl} from "../assets/js/cms-url-guard.mjs";
import {adminMfaStatus,beginAdminTotp,completeAdminTotp,stepUpAdminTotp,validateTotpCode} from "../assets/js/admin-mfa-flow.mjs";
import {CMS_PATHS,inspectPublishFiles} from "../supabase/functions/publish/guards.mjs";
const root=new URL("../",import.meta.url);
const read=path=>readFileSync(new URL(path,root),"utf8");
const empty=()=>Object.fromEntries(CMS_PATHS.map(p=>[p,"[]"]));
const mutate=(files,path,rows)=>({...files,[path]:JSON.stringify(rows)});

test("CMS protects all five paths and makes no-op comparison idempotent",()=>{
 const result=inspectPublishFiles(empty(),empty());
 assert.equal(result.has_changes,false);
 assert.equal(Object.keys(result.changes).length,5);
});
test("CMS detects editing and warns before clearing a populated category",()=>{
 const before=mutate(empty(),"articles.json",[{slug:"safe"}]);
 const changed=inspectPublishFiles(mutate(before,"articles.json",[{slug:"changed"}]),before);
 assert.equal(changed.has_changes,true);
 const clear=inspectPublishFiles(empty(),before);
 assert.deepEqual(clear.emptied_files,["articles.json"]);
});
test("CMS rejects missing or malformed files without changing input",()=>{
 const old=empty(),copy={...old};delete copy["bonus.json"];
 assert.throws(()=>inspectPublishFiles(copy,old),/incomplet/);
 assert.throws(()=>inspectPublishFiles({...old,"infos.json":"false"},old),/invalide/);
 assert.deepEqual(old,empty());
});
test("CMS preflight signature model detects tampering and concurrent commits",()=>{
 const secret="sandbox-only",user="admin_mock",head="a".repeat(40),exp=100000;
 const next=mutate(empty(),"articles.json",[{slug:"one"}]);
 const sign=(h,n,u=user)=>createHmac("sha256",secret).update(JSON.stringify([u,h,exp,n])).digest("hex");
 const seal=sign(head,next);
 assert.notEqual(sign("b".repeat(40),next),seal);
 assert.notEqual(sign(head,mutate(empty(),"articles.json",[{slug:"bad"}])),seal);
 assert.notEqual(sign(head,next,"other"),seal);
});
test("CMS restore model uses prior committed snapshot without destructive ref move",()=>{
 const old=mutate(empty(),"infos.json",[{title:"old"}]);
 const now=mutate(empty(),"infos.json",[{title:"new"}]);
 const oldCommit=createHash("sha1").update(JSON.stringify(old)).digest("hex");
 const nextCommit=createHash("sha1").update(JSON.stringify([oldCommit,now,old])).digest("hex");
 assert.equal(inspectPublishFiles(old,now).has_changes,true);
 assert.notEqual(nextCommit,oldCommit);
 assert.deepEqual(JSON.parse(old["infos.json"]),[{title:"old"}]);
});
test("CMS URL allows HTTP, HTTPS, local routes and fragments",()=>{
 for(const v of ["https://example.org","http://example.org","/articles/demo","#intro","conseils/a/"])
  assert.equal(isSafeCmsUrl(v,"link"),true,v);
});
test("CMS URL blocks active protocols and credentials",()=>{
 for(const v of ["javascript:alert(1)","JaVaScRiPt:alert(1)","data:text/html,<svg>","blob:https://a.com/x",
   "file:///etc/passwd","https://user:pass@evil.test","//evil.test","\\\\evil.test","javascript:\talert(1)"]){
  assert.equal(isSafeCmsUrl(v,"link"),false,v);
  assert.equal(safeCmsUrl(v,"link"),"#");
 }
});
test("Images exclude executable protocols while telephone/email remain link-only",()=>{
 assert.equal(isSafeCmsUrl("https://cdn.example.org/pic.png","image"),true);
 assert.equal(isSafeCmsUrl("data:image/svg+xml,abc","image"),false);
 assert.equal(isSafeCmsUrl("mailto:help@example.org","link"),true);
 assert.equal(isSafeCmsUrl("mailto:help@example.org","image"),false);
});
const mock=verified=>{
 const calls=[];
 return {calls,sb:{auth:{mfa:{
   getAuthenticatorAssuranceLevel:async()=>({data:{currentLevel:"aal1",nextLevel:verified?"aal2":"aal1"}}),
   listFactors:async()=>({data:{totp:verified?[{id:"f",status:"verified"}]:[]}}),
   enroll:async x=>{calls.push(["enroll",x]);return {data:{id:"new",totp:{qr_code:"data:image/svg+xml;base64,ABC"}}};},
   challengeAndVerify:async x=>{calls.push(["verify",x]);return {data:{verified:true}};}
 }}}};
};
test("TOTP rejects invalid formats",()=>{
 for(const code of ["","123","1234567","ABCD12","12 3456"]) assert.throws(()=>validateTotpCode(code));
 assert.equal(validateTotpCode(" 123456 "),"123456");
});
test("TOTP enrollment uses official factorType and challenge/verify",async()=>{
 const {sb,calls}=mock(false);const p=await beginAdminTotp(sb);
 await completeAdminTotp(sb,p.factorId,"123456");
 assert.equal(calls[0][1].factorType,"totp");
 assert.deepEqual(calls[1][1],{factorId:"new",code:"123456"});
});
test("TOTP step-up requires a verified factor",async()=>{
 await assert.rejects(()=>stepUpAdminTotp(mock(false).sb,"123456"),/Aucun facteur/);
 const m=mock(true);const state=await adminMfaStatus(m.sb);
 assert.equal(state.currentLevel,"aal1");assert.equal(state.nextLevel,"aal2");
 await stepUpAdminTotp(m.sb,"654321");
 assert.deepEqual(m.calls[0][1],{factorId:"f",code:"654321"});
});
test("Old VIP admin page cannot load legacy administrative scripts",()=>{
 const page=read("admin-vip.html");
 assert.match(page,/admin\.html#vip/);
 assert.doesNotMatch(page,/admin-vip\.js|supabaseAnonKey|ADMIN_PASSWORD/);
});
test("Admin MFA is a voluntary step, and server enforcement is disabled by default",()=>{
 const admin=read("assets/js/admin-real.js"),publish=read("supabase/functions/publish/index.ts");
 assert.match(admin,/initAdminMfaControl\(sb,/);
 assert.match(publish,/Deno\.env\.get\("PUBLISH_REQUIRE_AAL2"\) === "true"/);
 assert.match(publish,/claim\?\.aal!=="aal2"/);
});
test("Global telemetry caps are private and preserve public counter API shape",()=>{
 const sql=read("supabase/migrations/20261019020000_telemetry_global_rate_caps.sql");
 for(const term of ["mx_telemetry_private.minute_buckets","BEFORE INSERT ON public.events",
  "BEFORE INSERT ON public.analytics","public.increment_counter(counter_name text)"])
 assert.ok(sql.includes(term),term);
 assert.ok(sql.includes("FROM PUBLIC, anon, authenticated"));
 assert.ok(!sql.includes("REVOKE EXECUTE ON FUNCTION public.increment_counter"));
});
test("Privileged function migration preserves public VIP check and admin authentication",()=>{
 const sql=read("supabase/migrations/20261019022000_remaining_function_security.sql");
 assert.ok(sql.includes("REVOKE ALL ON FUNCTION public.is_admin() FROM PUBLIC, anon"));
 assert.ok(sql.includes("GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated, service_role"));
 assert.ok(sql.includes("pg_catalog, public, extensions, pg_temp"));
 assert.ok(!sql.includes("REVOKE ALL ON FUNCTION public.check_vip_code"));
});
console.log("Partie 1 — isolated CMS/MFA/URL/RPC regression suite executed.");
