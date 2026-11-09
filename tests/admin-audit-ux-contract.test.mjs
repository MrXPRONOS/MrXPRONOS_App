import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(path,"utf8");
const admin=read("assets/js/admin-real.js");
const phase3=read("assets/js/admin-phase3.mjs");
const html=read("admin.html");
const shell=read("assets/js/admin-shell.js");
const css=read("assets/css/admin-shell.css");
const publish=read("supabase/functions/publish/index.ts");
test("Pro/VIP admin mirrors public pronostics and diagnoses loading errors",()=>{
  const block=admin.slice(admin.indexOf("async function renderPronosticsReadOnly"),admin.indexOf("// CMS ARTICLES"));
  assert.match(block,/value="pro"/);
  assert.match(block,/value="vip"/);
  assert.doesNotMatch(block,/value="simple"/);
  assert.match(block,/home_logo/);
  assert.match(block,/away_logo/);
  assert.match(block,/Flux indisponible/);
  assert.match(block,/pRefresh/);
});
test("Admin overview uses native cards and optional iframe",()=>{
  assert.match(html,/admin-overview-summary/);
  assert.match(html,/admin-detailed-supervision/);
  assert.match(admin,/renderAdminOverview/);
  assert.match(shell,/admin-detailed-supervision/);
  assert.match(shell,/if\(!event.currentTarget.open\)return/);
  assert.match(css,/admin-overview-kpis/);
  assert.match(html,/aria-label="Publier les contenus"/);
  assert.match(html,/aria-label="Déconnexion"/);
});
test("Push requires explicit audience, preview and in-flight lock",()=>{
  assert.match(admin,/Choisir les destinataires/);
  assert.match(admin,/id="push_preview"/);
  assert.match(admin,/sendingPush=value/);
  assert.match(admin,/lock\(true\)/);
  assert.match(admin,/lock\(false\)/);
});
test("CMS editing preserves original publication date and keeps generated posts",()=>{
  assert.match(admin,/function preservedPublicationDate/);
  assert.equal((admin.match(/published_at: preservedPublicationDate\(/g)||[]).length,5);
  assert.match(admin,/function organizeCmsEditor/);
  assert.match(publish,/mergeGeneratedMatchArticles\(articlesJson,existingArticles\)/);
  assert.match(publish,/inspection\.removed_files\.length/);
  assert.match(admin,/PUBLIER SUPPRESSIONS/);
});
test("Audit log has pagination, search, CSV export and safe details",()=>{
  assert.match(admin,/renderAuditWorkbench\(sb,\$\("tab-audit"\)\)/);
  const section=phase3.slice(phase3.indexOf("export async function renderAuditWorkbench"));
  assert.match(section,/range\(offset,offset\+99\)/);
  assert.match(section,/input/);
  assert.match(section,/JSON\.stringify\(row\.details/);
  assert.match(section,/text\/csv/);
  assert.match(section,/createBars\(series/);
  assert.match(section,/escapeCsv/);
});
