const fs=require("node:fs");
const assert=require("node:assert/strict");
const server=fs.readFileSync("supabase/functions/publish/index.ts","utf8");
const admin=fs.readFileSync("assets/js/admin-real.js","utf8");
const includes=(content,items)=>items.forEach(x=>assert(content.includes(x),"Missing contract: "+x));
includes(server,[
  'await requireAdmin(req)',
  'requestBody?.operation === "status"',
  'requestBody?.operation==="history"',
  'requestBody?.operation==="preview_restore"',
  'requestBody?.operation==="restore"',
  'github_commit: publishedCommit',
  'if(expectedHead && baseSha !== expectedHead)',
  'force:false',
  '/deployments?sha=',
  '/actions/runs?head_sha=',
  'deployment_failed',
  'is_current:current',
]);
includes(server,[
  'cmsPreview(body.version_id)',
  'body?.confirm!=="RESTAURER"',
  'cmsSeal(uid,p,expiry)',
  'p.current_head!==String(body.expected_head||"")',
  'restored_from:p.target_commit',
  'cmsFiles',
  'action:"restore_json"',
]);
includes(admin,[
  'cmsAdminRequest("restore"',
  'cmsAdminRequest("preview_restore"',
  'cmsAdminRequest("history"',
  'cmsAdminRequest("status",{commit})',
  'window.confirm(',
  'window.prompt(',
  'Vérifier le déploiement',
  'Mise en ligne non confirmée',
  'Publication préparée',
  'labels[value.deployment]',
  'cmsInstallHistory();'
]);
assert(!admin.includes('alert(`Commit GitHub enregistré'),"Old premature success alert remains");
assert(!admin.includes('SUPABASE_SERVICE_ROLE_KEY'),"Service key must not exist in frontend");
assert(!admin.includes('GITHUB_PAT'),"GitHub token must not exist in frontend");
const migration=fs.readFileSync("supabase/migrations/20261018212440_secure_legacy_vip_code_rpc.sql","utf8");
assert(migration.includes("REVOKE ALL ON FUNCTION public.create_vip_code"));
assert(migration.includes("REVOKE ALL ON FUNCTION public.insert_vip_code"));
assert(migration.includes("TO service_role"));
assert(!migration.includes("REVOKE ALL ON FUNCTION public.admin_reset_vip"));
console.log("Publish status & guarded rollback source contracts passed");
