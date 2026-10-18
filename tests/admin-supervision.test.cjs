const fs=require("node:fs");const assert=require("node:assert/strict");
const html=fs.readFileSync("admin-supervision.html","utf8");
const app=fs.readFileSync("assets/js/admin-supervision.js","utf8");
const metrics=fs.readFileSync("assets/js/web-vitals-monitor.js","utf8");
const sql=fs.readFileSync("supabase/migrations/20261018131500_admin_supervision_metrics.sql","utf8");
const errorSql=fs.readFileSync("supabase/migrations/20261018134000_admin_client_errors.sql","utf8");
const main=fs.readFileSync("assets/js/main.js","utf8");
const admin=fs.readFileSync("admin.html","utf8");
for(const [file,data] of [["assets/js/admin-supervision.js",app],["assets/js/web-vitals-monitor.js",metrics]]) {
 const normalized=data.replace(/^import\s.*?;[ \t]*$/gm,"").replace(/^await establishSession\(\);[ \t]*$/gm,"");
 new Function(normalized);
 console.log("Syntaxe JS OK:",file);
}
const ids=[...app.matchAll(/\$\("([^"]+)"\)/g)].map(m=>m[1]);
for(const id of new Set(ids)){assert(html.includes('id="'+id+'"'),"DOM element missing: "+id)}
assert(html.includes('name="viewport"'));
assert(html.includes('name="robots" content="noindex,nofollow"'));
assert(admin.includes('href="admin-supervision.html"'));
assert(main.includes('import "./web-vitals-monitor.js"'));
assert(app.includes('rpc("is_admin")'));
assert(app.includes('rpc("admin_monitor_snapshot"'));
assert(app.includes('rpc("admin_client_error_summary"'));
assert(app.includes('refreshGitHubRuns()'));
assert(app.includes('document.hidden'));
assert(sql.includes('REVOKE ALL ON FUNCTION public.admin_monitor_snapshot(integer) FROM PUBLIC,anon,authenticated'));
assert(errorSql.includes('REVOKE ALL ON FUNCTION public.admin_client_error_summary(integer) FROM PUBLIC,anon,authenticated'));
assert(sql.includes('ALTER TABLE public.admin_web_vitals ENABLE ROW LEVEL SECURITY'));
assert(errorSql.includes('ALTER TABLE public.admin_client_errors ENABLE ROW LEVEL SECURITY'));
assert(!app.includes('.from("analytics")'),"Analytics must be server-aggregated");
assert(!metrics.includes("user_id"),"Telemetry should not persist visitor identity");
console.log("Admin supervision: static checks passed");
