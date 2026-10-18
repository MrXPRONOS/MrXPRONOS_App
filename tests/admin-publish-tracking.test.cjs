const fs=require("node:fs");
const assert=require("node:assert/strict");
const server=fs.readFileSync("supabase/functions/publish/index.ts","utf8");
const admin=fs.readFileSync("assets/js/admin-real.js","utf8");
for(const v of [
  'await requireAdmin(req)',
  'requestBody?.operation === "status"',
  'requestBody?.operation==="history"',
  'github_commit: publishedCommit',
  'publish_history',
  '/deployments?sha=',
  '/actions/runs?head_sha=',
  'deployment_failed',
  'is_current:current'
]) assert(server.includes(v),"Missing server contract: "+v);
for(const v of [
  'operation:"status"',
  'Vérifier le déploiement',
  'Mise en ligne non confirmée',
  'labels[value.deployment]'
]) assert(admin.includes(v),"Missing UI contract: "+v);
assert(!admin.includes('alert(`Commit GitHub enregistré'),"Old success alert remains");
console.log("Publish status contracts passed (static checks; no live deployment asserted)");
