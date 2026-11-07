import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {detectCronDuplicateConfigs} from '../assets/js/admin-cron-register.mjs';
import {adminSnapshotLabel,freshnessClass} from '../assets/js/admin-data-freshness.mjs';
import {loadAdminHighlights} from '../assets/js/admin-unified-highlights.mjs';
import {inspectCmsEditorial} from '../assets/js/cms-quality.mjs';
const read=p=>readFileSync(new URL('../'+p,import.meta.url),'utf8');

test("cron-job.org duplicates require same target and complete schedule",()=>{
 const base={enabled:true,endpoint:"api.github.com/repos/MrXPRONOS/MrXPRONOS_App/dispatches",
  schedule:{timezone:"UTC",hours:[-1],minutes:[0,30],wdays:[-1]}};
 const jobs=[{...base,id:12,title:"Alpha"},{...base,id:14,title:"Beta"},
  {...base,id:15,schedule:{...base.schedule,minutes:[15,45]}}];
 const groups=detectCronDuplicateConfigs(jobs);
 assert.equal(groups.length,1);
 assert.deepEqual(groups[0].jobs.map(x=>x.id),[12,14]);
 assert.equal(detectCronDuplicateConfigs([{...base,id:12},{...base,id:14,enabled:false}]).length,0);
});
test("admin time metadata distinguishes freshness and a synchronized snapshot",()=>{
 const timestamp=new Date("2026-11-07T15:50:00Z");
 const msg=adminSnapshotLabel("Supabase",timestamp,{intervalSeconds:60});
 assert.match(msg,/Instantané Supabase/);assert.match(msg,/UTC/);
 assert.match(msg,/60 s/);assert.doesNotMatch(msg,/temps réel/i);
 assert.equal(freshnessClass("2026-11-07T15:48:00Z",5,timestamp.getTime()),"good");
 assert.equal(freshnessClass("2026-11-07T15:40:00Z",5,timestamp.getTime()),"late");
 assert.equal(freshnessClass(null,5),"unknown");
});
test("unified overview does not misreport failed Supabase RPCs as zero",async()=>{
 const fake={
  rpc:async name=>name==="admin_client_error_summary"?
   {data:null,error:{message:"offline"}}:{data:{summary:{visitors_period:9}},error:null},
  from:()=>({select:()=>({in:()=>({limit:async()=>({data:[{status:"open"}],error:null})}),
    order:()=>({limit:async()=>({data:[],error:null})})})})
 };
 const result=await loadAdminHighlights(fake);
 assert.equal(result.errors,null);
 assert.deepEqual(result.incidents,[{status:"open"}]);
 assert.equal(result.audience.summary.visitors_period,9);
});
test("CMS link validation and SEO warnings protect publication",()=>{
 const q=inspectCmsEditorial("articles",{
  status:"published",slug:"article-bref",title:"Trop bref",meta_description:"Oui",
  content:"Un petit contenu sans image."
 });
 assert.equal(q.errors.length,0);
 assert.ok(q.warnings.some(x=>x.includes("Titre")));
 assert.ok(q.warnings.some(x=>x.includes("SEO")));
 const client=read('assets/js/admin-real.js');
 assert.match(client,/admin-link-check/);
 assert.match(client,/checked\.results/);
 assert.match(client,/Lien introuvable/);
});
test("remote link verifier denies internal and unsafe targets",()=>{
 const source=read('supabase/functions/admin-link-check/index.ts');
 assert.match(source,/Deno\.resolveDns/);
 assert.match(source,/unsafe_or_unresolvable/);
 assert.match(source,/redirect:"manual"/);
 assert.match(source,/admin_can/);
 assert.match(source,/urls\.length>12/);
});
test("cron provider integration never exposes bearer keys or request query parameters",()=>{
 const source=read('supabase/functions/admin-cron-read/index.ts');
 assert.match(source,/CRON_JOB_ORG_API_KEY/);
 assert.match(source,/url\.hostname\.toLowerCase\(\)\+url\.pathname/);
 assert.match(source,/Authorization/);
 assert.match(source,/cache/);
 assert.doesNotMatch(source,/job\.extendedData/);
});
test("watchdog verifies GitHub OIDC, persists incidents and escalations",()=>{
 const fn=read('supabase/functions/admin-incident-watch/index.ts');
 const script=read('scripts/admin_incident_watch.mjs');
 const workflow=read('.github/workflows/admin-incident-watch.yml');
 assert.match(fn,/jwtVerify/);
 assert.match(fn,/workflow_ref/);
 assert.match(fn,/admin_incidents/);
 assert.match(fn,/admin_monitor_state/);
 assert.match(fn,/last_seen_at/);
 assert.match(fn,/escalations/);
 assert.match(script,/process\.exitCode=1/);
 assert.match(workflow,/id-token: write/);
 assert.match(workflow,/schedule:/);
});
test("delivery logs use digests and manual retry only for confirmed HTTP refusal",()=>{
 const fn=read('supabase/functions/admin-push/index.ts');
 const worker=read('supabase/functions/push-notifications/index.ts');
 const admin=read('assets/js/admin-real.js');
 assert.match(fn,/admin_push_delivery_logs/);
 assert.match(fn,/crypto\.subtle\.digest/);
 assert.match(fn,/\[429,502,503,504\]/);
 assert.match(fn,/RENVOYER APPAREIL/);
 assert.match(worker,/targetDigest/);
 assert.match(admin,/Réessayer uniquement cet appareil/);
 assert.match(admin,/operation:"details"/);
});
test("public preview embeds the site's real reader classes and CSS",()=>{
 const preview=read('assets/js/cms-block-editor.mjs');
 assert.match(preview,/mx-reader-article/);
 assert.match(preview,/mx-article-detail-main/);
 assert.match(preview,/assets\/css\/article-detail-premium\.css/);
 assert.match(preview,/sandbox/);
});
