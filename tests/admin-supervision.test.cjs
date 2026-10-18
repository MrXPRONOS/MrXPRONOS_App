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
assert(admin.includes('data-src="admin-supervision.html?embedded=1"'));
assert(!main.includes('import "./web-vitals-monitor.js"'));
assert(fs.readFileSync("index.html","utf8").includes('src="assets/js/web-vitals-monitor.js'));
assert(fs.readFileSync("pronos.html","utf8").includes('src="assets/js/web-vitals-monitor.js'));
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
assert(html.includes('id="traffic-chart"'));assert(html.includes('id="chart-visits"'));assert(html.includes('id="chart-clicks"'));assert(html.includes('class="supervision"'));assert(admin.includes('class="admin-shell"'));assert(html.includes('admin-premium.css'));assert(admin.includes('admin-premium.css'));assert(admin.includes('admin-shell.css'));assert(app.includes('renderActivityChart()'));assert(html.includes('id="compact-view"'));
assert(app.includes('classList.toggle("is-compact")'));
assert(html.includes("admin-premium.css?v=20261018-future2"));
const shell=fs.readFileSync("assets/js/admin-shell.js","utf8");
const adminLogic=fs.readFileSync("assets/js/admin-real.js","utf8");
const shellCSS=fs.readFileSync("assets/css/admin-shell.css","utf8");
new Function(shell);
new Function(adminLogic.replace(/^import .*;[ \t]*$/gm,""));
const sections=["overview","pronostics","push","vip","articles","conseils","bonus","infos","health","audit"];
for(const name of sections){
 assert(admin.includes('data-tab="'+name+'"'),"Navigation missing "+name);
 assert(admin.includes('id="tab-'+name+'"'),"Screen missing "+name);
}
assert(admin.includes('id="sidebar-open"')&&admin.includes('id="sidebar-close"'));
assert(admin.includes('id="sidebar-backdrop"'));
assert(admin.includes('id="btnPublish"')&&admin.includes('id="btnLogout"'));
assert(adminLogic.includes('window.MXAdminNavigate = showTab'));
assert(adminLogic.includes('showOnlyTab(name)'));
assert(adminLogic.includes('history.replaceState(null,"",target)'));
assert(shellCSS.includes(".admin-screen[hidden]"));
assert(shellCSS.includes("[hidden]{display:none!important}"));
assert(html.includes('get("embedded")'));
console.log("Unified admin shell: static checks passed");
console.log("Admin supervision: static checks passed");
