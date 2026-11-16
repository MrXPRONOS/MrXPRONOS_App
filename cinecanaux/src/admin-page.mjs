// Private moderation mini-app. The server validates Telegram initData and admin_users.
export const ADMIN_HTML=String.raw`<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07101e"><title>Ciné Radar — Administration</title>
<script src="https://telegram.org/js/telegram-web-app.js?64"></script>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui;background:#07101e;color:#f4f8ff;font-size:14px}
*{box-sizing:border-box}body{margin:0}.page{max-width:760px;margin:auto;padding:18px 14px 40px}
header{display:flex;align-items:center;gap:10px;margin-bottom:24px}h1{font-size:20px;margin:0}h2{font-size:15px;margin:20px 0 12px}
small,.muted{color:#a7bbd9}button,input{font:inherit}
button{border:1px solid #486b9f;background:#1e3b70;color:#fff;border-radius:9px;padding:9px 12px;cursor:pointer}
button:disabled{opacity:.6}.danger{background:#552d48;border-color:#864867}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.metric,.item{background:#13253e;border:1px solid #30486f;border-radius:12px;padding:12px}
.metric strong{display:block;font-size:22px}.metric small{font-size:10px}.item{margin-bottom:8px}
.item .name{font-weight:700;overflow-wrap:anywhere}.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
input{padding:10px;border:1px solid #3c5983;background:#14243b;color:#fff;border-radius:9px;width:95px}
a{color:#91bbff}#status{color:#b5cfff;min-height:20px;margin:12px 0}
</style></head>
<body><div class="page">
<header><span style="font-size:30px">🎬</span><div><h1>Ciné Radar</h1><small>Modération privée</small></div></header>
<p id="status" role="status">Vérification de l’accès…</p>
<div id="private" hidden>
<section class="stats" id="stats"></section>
<h2>Signalements</h2><section id="reports"></section>
<h2>Canaux proposés</h2><section id="suggestions"></section>
<h2>Gestion d’un canal</h2>
<div class="item">
<label for="channelId">Identifiant du canal</label>
<input type="number" id="channelId" min="1" step="1">
<div class="actions">
<button id="hide">Masquer</button><button id="show">Afficher</button><button class="danger" id="exclude">Exclure</button>
</div></div></div></div>
<script>
(()=>{
const $=id=>document.getElementById(id);
const init=window.Telegram?.WebApp?.initData||"";
try{window.Telegram?.WebApp?.ready();window.Telegram?.WebApp?.expand();}catch{}
const status=t=>{$("status").textContent=t;};
const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!=null)x.textContent=text;return x;};
async function api(path,body){
 const headers={"X-Telegram-Init-Data":init};
 if(body){headers["Content-Type"]="application/json";}
 const r=await fetch(path,{method:body?"POST":"GET",headers,body:body?JSON.stringify(body):undefined});
 const data=await r.json();if(!r.ok)throw Error(data.error||"Erreur");return data;
}
function addButton(parent,text,handler,cls){
 const b=el("button",cls,text);b.onclick=async()=>{b.disabled=true;try{await handler();}catch(e){status(String(e.message||e));}finally{b.disabled=false;}};parent.append(b);
}
async function manage(id,action){await api("/api/admin/channels/"+id,{action});status("Canal mis à jour.");await load();}
async function load(){
 const [overview,reportData,suggestionData]=await Promise.all([
  api("/api/admin/overview"),api("/api/admin/reports"),api("/api/admin/suggestions")]);
 $("private").hidden=false;status("");
 const stats=$("stats");stats.textContent="";
 for(const [key,title] of [["indexed","Référencés"],["visible","Visibles"],["hidden","Masqués"],["reviews","Avis"],["open_reports","Signalements"],["checks_24h","Contrôles 24 h"],["searches_today","Recherches"],["empty_searches_today","Sans résultat"]]){
  const box=el("div","metric");box.append(el("strong",null,String(overview[key]||0)),el("small",null,title));stats.append(box);
 }
 const reports=$("reports");reports.textContent="";
 for(const item of reportData.reports||[]){
  const card=el("article","item");card.append(el("div","name",item.title+" · #"+item.channel_id),el("div","muted",item.reason+" · "+item.status),el("p",null,item.details||"Aucun détail"));
  const actions=el("div","actions");
  addButton(actions,"Examiner",async()=>{await api("/api/admin/reports/"+item.id,{status:"reviewing"});await load();});
  addButton(actions,"Résoudre",async()=>{await api("/api/admin/reports/"+item.id,{status:"resolved"});await load();});
  addButton(actions,"Masquer le canal",async()=>manage(item.channel_id,"hide"),"danger");
  card.append(actions);reports.append(card);
 }
 if(!reports.children.length)reports.append(el("p","muted","Aucun signalement en attente."));
 const suggestions=$("suggestions");suggestions.textContent="";
 for(const item of suggestionData.suggestions||[]){
  const card=el("article","item");card.append(el("div","name",item.username),el("div","muted",item.suggested_category+" · "+item.status));
  const a=el("a",null,"Consulter le lien");a.href=item.link;a.target="_blank";a.rel="noopener noreferrer";card.append(a);suggestions.append(card);
 }
 if(!suggestions.children.length)suggestions.append(el("p","muted","Aucune suggestion."));
}
for(const action of ["hide","show","exclude"])$(action).onclick=async()=>{
 const id=Number($("channelId").value);if(!Number.isSafeInteger(id)||id<1){status("Identifiant invalide.");return;}
 if(action==="exclude"&&!confirm("Exclure durablement ce canal ?"))return;
 try{await manage(id,action);}catch(e){status(String(e.message||e));}
};
if(!init)status("Ouvre cette page depuis le bot Telegram avec ton compte administrateur.");
else load().catch(e=>status("Accès refusé ou service indisponible : "+String(e.message||e)));
})();
</script></body></html>`;
