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

.analytics-dashboard{margin:18px 0 26px;padding:14px;border:1px solid #3c557c;border-radius:15px;background:#0c1c31}
.analytics-head{display:flex;justify-content:space-between;align-items:center;gap:10px}.analytics-head h2{margin:0 0 10px}
.analytics-head small{font-size:10px;text-align:right}
.analytics-controls{display:flex;flex-wrap:wrap;gap:9px;align-items:end;margin:10px 0 14px}
.analytics-controls label{display:flex;flex-direction:column;gap:4px;font-size:11px;color:#b8c9e6}
.analytics-controls select,.analytics-controls input{background:#142b48;border:1px solid #456288;border-radius:8px;color:#fff;padding:9px;width:auto;max-width:170px;min-width:0;font:inherit}
#analytics-custom{display:flex;gap:8px;flex-wrap:wrap}
.analytics-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.analytics-metrics .metric strong{font-size:19px;font-variant-numeric:tabular-nums}
.analytics-dashboard h3{font-size:13px;margin:23px 0 10px}
.analytics-row{padding:9px 10px;margin:5px 0;border-radius:9px;background:#14263e;border:1px solid #2d466c}
.analytics-row .analytics-row-top{display:flex;justify-content:space-between;gap:9px;align-items:center;line-height:1.4}
.analytics-row strong{font-size:12px;max-width:80%;overflow-wrap:anywhere}
.analytics-row small{color:#9bb5d4;font-size:10px}
.analytics-bar{height:5px;border-radius:5px;background:#182f52;margin-top:7px;overflow:hidden}
.analytics-bar span{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#577df2,#ac90f5)}
.analytics-daily{max-height:360px;overflow:auto}
.analytics-notice{color:#a9bfde;font-size:11px;line-height:1.5;margin:8px 0}
@media(min-width:660px){.analytics-metrics{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:360px){.analytics-controls select{max-width:145px}.analytics-dashboard{padding:10px}}

/* Private owner announcement composer. Nothing is sent without explicit confirmation. */
.broadcast-box{background:linear-gradient(145deg,#102443,#101e35);border:1px solid #486ba3;border-radius:14px;padding:15px;margin:15px 0 24px}
.broadcast-box h2{margin:0 0 8px;font-size:16px}
.broadcast-box p{font-size:12px;line-height:1.5;color:#bacded}
.broadcast-box label{display:flex;flex-direction:column;gap:6px;margin:12px 0 0;font-size:12px;color:#dce9ff;font-weight:650}
.broadcast-box textarea,.broadcast-box input{width:100%;min-width:0;border:1px solid #425e8b;border-radius:9px;background:#0b192c;color:#f2f7ff;font:inherit;padding:10px}
.broadcast-box textarea{min-height:160px;resize:vertical;line-height:1.5}
.broadcast-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.broadcast-toolbar{display:flex;gap:7px;flex-wrap:wrap;margin-top:7px}
.broadcast-toolbar button{padding:7px 9px;background:#203d6c;font-size:11px}
.broadcast-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.broadcast-primary{background:linear-gradient(110deg,#406bf9,#7358ef);border-color:#8ab5ff}
.broadcast-box button[hidden]{display:none}
#broadcast-status{font-size:12px;min-height:16px;color:#d3e4ff;padding-top:8px}
#broadcast-preview{white-space:pre-wrap;overflow-wrap:anywhere;border:1px dashed #52729e;border-radius:10px;padding:10px;color:#e3eeff;background:#0b182b;max-height:250px;overflow:auto;margin-top:10px;font-size:12px}
#broadcast-history .broadcast-row{border:1px solid #344b71;border-radius:9px;background:#11233d;padding:10px;margin-top:7px;font-size:11px;line-height:1.55}
@media(max-width:420px){.broadcast-grid{grid-template-columns:1fr}}
</style></head>
<body><div class="page">
<header><span style="font-size:30px">🎬</span><div><h1>Ciné Radar</h1><small>Modération privée</small></div></header>
<p id="status" role="status">Vérification de l’accès…</p>
<div id="private" hidden>
<section class="stats" id="stats"></section>

<section class="broadcast-box" id="broadcast-box" aria-label="Envoyer une annonce aux utilisateurs">
 <h2>📣 Annonces aux utilisateurs du bot</h2>
 <p>Crée un message, ajoute une image et un bouton, puis prévisualise-le dans ton Telegram avant l'envoi. <b>Aucun envoi collectif n'a lieu sans confirmation.</b></p>
 <p id="broadcast-audience">Destinataires : chargement…</p>
 <label for="broadcast-text">Message (mise en forme Telegram : gras, italique, citation)
  <textarea id="broadcast-text" maxlength="3900" placeholder="🎬 Nouveauté Ciné Radar !&#10;&#10;Découvre les nouveaux canaux…"></textarea>
 </label>
 <div class="broadcast-toolbar" aria-label="Mise en forme">
  <button type="button" data-format="b">B Gras</button>
  <button type="button" data-format="i">I Italique</button>
  <button type="button" data-format="blockquote">❞ Citation</button>
  <button type="button" data-format="u">U Souligner</button>
 </div>
 <p>Tu peux également saisir les balises HTML Telegram : &lt;b&gt;, &lt;i&gt;, &lt;blockquote&gt;. Le lien du bouton se configure ci-dessous.</p>
 <label for="broadcast-photo">Image facultative (JPEG, PNG ou WebP — 2 Mo maximum)
  <input id="broadcast-photo" type="file" accept="image/jpeg,image/png,image/webp">
 </label>
 <div class="broadcast-actions"><button id="broadcast-upload-photo" type="button">🖼️ Importer l'image</button><button id="broadcast-remove-photo" type="button" hidden>Retirer l'image</button></div>
 <p id="broadcast-photo-status">Aucune image sélectionnée. L'import envoie uniquement un aperçu privé dans ton Telegram.</p>
 <div class="broadcast-grid">
  <label for="broadcast-button-text">Texte du bouton (facultatif)<input id="broadcast-button-text" maxlength="64" placeholder="▶️ Découvrir"></label>
  <label for="broadcast-button-url">Lien HTTPS du bouton<input id="broadcast-button-url" type="url" placeholder="https://t.me/..."></label>
 </div>
 <h3>Prévisualisation du contenu</h3>
 <div id="broadcast-preview">Saisis un message pour afficher son aperçu.</div>
 <div class="broadcast-actions">
  <button id="broadcast-save" class="broadcast-primary" type="button">💾 Enregistrer le brouillon</button>
  <button id="broadcast-preview-send" type="button" disabled>👁️ Aperçu privé Telegram</button>
  <button id="broadcast-start" class="broadcast-primary" type="button" disabled>📢 Confirmer et envoyer</button>
  <button id="broadcast-cancel" type="button" disabled>Annuler</button>
 </div>
 <p id="broadcast-status" role="status"></p>
 <h3>Historique des annonces</h3><div id="broadcast-history"></div>
 <button id="broadcast-refresh" type="button">↻ Actualiser l'historique</button>
</section>
<section class="analytics-dashboard" aria-label="Statistiques de fréquentation">
 <div class="analytics-head"><h2>📊 Fréquentation et engagement</h2><small id="analytics-clock">Actualisation automatique · 30 s</small></div>
 <div class="analytics-controls">
 <label>Période <select id="analytics-period"><option value="today">Aujourd'hui</option><option value="yesterday">Hier</option><option value="7d">7 derniers jours</option><option value="week">Cette semaine</option><option value="30d" selected>30 derniers jours</option><option value="month">Ce mois</option><option value="year">Cette année</option><option value="last-year">Année passée</option><option value="all">Toutes les années</option><option value="custom">Dates personnalisées</option></select></label>
 <div id="analytics-custom" hidden><label>Du <input type="date" id="analytics-from"></label><label>Au <input type="date" id="analytics-to"></label></div>
 <button id="analytics-refresh" type="button">Actualiser</button><button id="analytics-csv" type="button">Exporter CSV</button>
 </div>
 <div class="stats analytics-metrics" id="analytics-metrics"></div>
 <p class="muted" id="analytics-note">Collecte de statistiques en cours…</p>
 <h3>📈 Évolution quotidienne</h3><div id="analytics-daily" class="analytics-daily"></div>
 <h3>🎬 Canaux les plus ouverts</h3><div id="analytics-channels"></div>
 <h3>🍿 Films et publications les plus cliqués</h3><div id="analytics-pins"></div>
 <h3>📢 Promotions, partages et avis</h3><div id="analytics-promos"></div>
 <h3>Historique des ouvertures de canaux (avant ce suivi)</h3><div id="analytics-historic"></div>
 </section>

<h2>Automatisations</h2>
<div class="item"><div class="actions"><button id="runChecks">Vérifier 10 canaux</button><button id="refreshJobs">Actualiser</button></div></div><section id="jobs"></section>
<h2>Signalements</h2><section id="reports"></section>
<h2>Avis des utilisateurs</h2><section id="reviews"></section>
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
 const [overview,reportData,suggestionData,reviewData,jobData]=await Promise.all([
  api("/api/admin/overview"),api("/api/admin/reports"),api("/api/admin/suggestions"),api("/api/admin/reviews"),api("/api/admin/jobs")]);
 $("private").hidden=false;status("");refreshAnalytics();refreshBroadcasts().catch(e=>broadcastStatus(String(e.message||e)));
 const stats=$("stats");stats.textContent="";
 for(const [key,title] of [["indexed","Référencés"],["visible","Visibles"],["hidden","Masqués"],["reviews","Avis"],["open_reports","Signalements"],["checks_24h","Contrôles 24 h"],["searches_today","Recherches"],["empty_searches_today","Sans résultat"]]){
  const box=el("div","metric");box.append(el("strong",null,String(overview[key]||0)),el("small",null,title));stats.append(box);
 }
 const jobs=$("jobs");jobs.textContent="";
 for(const item of (jobData.jobs||[]).slice(0,12)){
  const entry=el("div","item");
  entry.append(el("div","name",item.job_name+" · "+item.status),
   el("div","muted",item.started_at+" · "+item.examined+" contrôles · "+item.errors+" erreur(s)"));
  jobs.append(entry);
 }
 if(!jobs.children.length)jobs.append(el("p","muted","Aucune exécution enregistrée."));
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
 const reviews=$("reviews");reviews.textContent="";
 for(const item of reviewData.reviews||[]){
  const card=el("article","item");
  card.append(el("div","name",item.title+" · ★ "+item.rating),el("div","muted",item.matches_description+" · "+item.visibility));
  if(item.comment)card.append(el("p",null,item.comment));
  const actions=el("div","actions");
  addButton(actions,"Masquer",async()=>{await api("/api/admin/reviews/"+item.id,{visibility:"hidden"});await load();},"danger");
  addButton(actions,"Rétablir",async()=>{await api("/api/admin/reviews/"+item.id,{visibility:"visible"});await load();});
  card.append(actions);reviews.append(card);
 }
 if(!reviews.children.length)reviews.append(el("p","muted","Aucun avis."));
 const suggestions=$("suggestions");suggestions.textContent="";
 for(const item of suggestionData.suggestions||[]){
  const card=el("article","item");card.append(el("div","name",item.username),el("div","muted",item.suggested_category+" · "+item.status));
  const a=el("a",null,"Consulter le lien");a.href=item.link;a.target="_blank";a.rel="noopener noreferrer";card.append(a);suggestions.append(card);
 }
 if(!suggestions.children.length)suggestions.append(el("p","muted","Aucune suggestion."));
}


let activeBroadcastId=null,uploadedPhotoId="",broadcastAudience=0;
const broadcastStatus=message=>{$("broadcast-status").textContent=message;};
function broadcastDraftChanged(){
 activeBroadcastId=null;
 $("broadcast-preview-send").disabled=true;$("broadcast-start").disabled=true;$("broadcast-cancel").disabled=true;
 updateBroadcastPreview();
}
function updateBroadcastPreview(){
 const text=$("broadcast-text").value.trim(),button=$("broadcast-button-text").value.trim(),url=$("broadcast-button-url").value.trim();
 $("broadcast-preview").textContent=(text||"Saisis un message pour afficher son aperçu.")+
  (uploadedPhotoId?"\n\n🖼️ Image jointe":"")+(button?"\n\n🔗 "+button+" → "+url:"");
}
function broadcastPayload(){
 if($("broadcast-photo").files.length&&!uploadedPhotoId)throw Error("Clique d'abord sur « Importer l'image ».");
 return {text_html:$("broadcast-text").value.trim(),photo_id:uploadedPhotoId,button_text:$("broadcast-button-text").value.trim(),button_url:$("broadcast-button-url").value.trim()};
}
async function refreshBroadcasts(){
 const data=await api("/api/admin/broadcasts");
 broadcastAudience=Number(data.subscribers?.active||0);
 $("broadcast-audience").textContent="📬 "+broadcastAudience.toLocaleString("fr-FR")+" utilisateur(s) joignable(s) enregistré(s) après /start. Les anciens visiteurs anonymisés ne sont pas joignables automatiquement.";
 const box=$("broadcast-history");box.textContent="";
 const labels={draft:"Brouillon",preparing:"Préparation",sending:"En cours",completed:"Terminé",cancelled:"Annulé"};
 for(const item of data.jobs||[]){
  const row=el("div","broadcast-row");
  row.append(el("strong",null,"#"+item.id+" · "+(labels[item.status]||item.status)),
   el("div",null,"Destinataires : "+Number(item.recipients||0)+" · Envoyés : "+Number(item.delivered||0)+
   " · Bloqués : "+Number(item.blocked||0)+" · Échecs : "+Number(item.failed||0)),
   el("small",null,String(item.created_at||"")+(item.has_photo?" · 🖼️ Image":"")+(item.button_text?" · 🔗 Bouton":"")));
  box.append(row);
 }
 if(!box.children.length)box.append(el("p","muted","Aucune annonce créée."));
}
for(const id of ["broadcast-text","broadcast-button-text","broadcast-button-url"])
 $(id).addEventListener("input",broadcastDraftChanged);
$("broadcast-photo").addEventListener("change",()=>{
 uploadedPhotoId="";
 $("broadcast-photo-status").textContent=$("broadcast-photo").files.length?"Image sélectionnée : clique sur « Importer l'image ».":"Aucune image.";
 $("broadcast-remove-photo").hidden=true;
 broadcastDraftChanged();
});
$("broadcast-remove-photo").onclick=()=>{
 uploadedPhotoId="";$("broadcast-photo").value="";
 $("broadcast-remove-photo").hidden=true;
 $("broadcast-photo-status").textContent="Aucune image.";
 broadcastDraftChanged();
};
for(const button of document.querySelectorAll("[data-format]"))button.onclick=()=>{
 const box=$("broadcast-text"),open="<"+button.dataset.format+">",close="</"+button.dataset.format+">";
 const start=box.selectionStart,end=box.selectionEnd,selected=box.value.slice(start,end)||"Ton texte";
 box.setRangeText(open+selected+close,start,end,"select");
 broadcastDraftChanged();box.focus();
};
$("broadcast-upload-photo").onclick=async()=>{
 const file=$("broadcast-photo").files[0];
 if(!file){broadcastStatus("Choisis une image.");return}
 if(file.size>2000000){broadcastStatus("Image trop volumineuse : maximum 2 Mo.");return}
 const btn=$("broadcast-upload-photo");btn.disabled=true;broadcastStatus("Import de l'image…");
 try{
  const form=new FormData();form.append("photo",file);
  const r=await fetch("/api/admin/broadcast-image",{method:"POST",headers:{"X-Telegram-Init-Data":init},body:form});
  const data=await r.json();if(!r.ok)throw Error(data.error||"Échec de l'import");
  uploadedPhotoId=data.photo_id;$("broadcast-photo-status").textContent="✅ Image ajoutée. Un aperçu privé a été envoyé dans ton Telegram.";
  $("broadcast-remove-photo").hidden=false;broadcastStatus("Image prête.");broadcastDraftChanged();
 }catch(e){broadcastStatus(String(e.message||e));}finally{btn.disabled=false}
};
$("broadcast-save").onclick=async()=>{
 const btn=$("broadcast-save");btn.disabled=true;
 try{
  const payload=broadcastPayload();
  const data=await api("/api/admin/broadcasts",payload);
  activeBroadcastId=data.id;
  $("broadcast-preview-send").disabled=false;$("broadcast-start").disabled=false;$("broadcast-cancel").disabled=false;
  broadcastStatus("✅ Brouillon #"+data.id+" enregistré. Tu peux d'abord envoyer un aperçu privé.");
  await refreshBroadcasts();
 }catch(e){broadcastStatus("Erreur : "+String(e.message||e));}
 finally{btn.disabled=false}
};
$("broadcast-preview-send").onclick=async()=>{
 if(!activeBroadcastId)return;
 const btn=$("broadcast-preview-send");btn.disabled=true;
 try{await api("/api/admin/broadcasts/"+activeBroadcastId+"/preview",{});broadcastStatus("👁️ Aperçu envoyé dans ton Telegram privé, pas aux utilisateurs.");}
 catch(e){broadcastStatus("Erreur : "+String(e.message||e));}finally{btn.disabled=false}
};
$("broadcast-start").onclick=async()=>{
 if(!activeBroadcastId)return;
 const id=activeBroadcastId;
 const note="Envoyer l'annonce #"+id+" aux "+broadcastAudience+" utilisateurs enregistrés et actifs ?\n\nCette action démarre une diffusion qui ne pourra pas être annulée pour les messages déjà envoyés.";
 if(!confirm(note))return;
 const btn=$("broadcast-start");btn.disabled=true;
 try{
  const data=await api("/api/admin/broadcasts/"+id+"/start",{});
  broadcastStatus("📢 Diffusion "+data.status+" : "+data.recipients+" destinataire(s). Actualise l'historique pour suivre.");
  activeBroadcastId=null;$("broadcast-preview-send").disabled=true;$("broadcast-cancel").disabled=true;
  await refreshBroadcasts();
 }catch(e){btn.disabled=false;broadcastStatus("Erreur : "+String(e.message||e));}
};
$("broadcast-cancel").onclick=async()=>{
 if(!activeBroadcastId||!confirm("Annuler le brouillon #"+activeBroadcastId+" ?"))return;
 try{
  await api("/api/admin/broadcasts/"+activeBroadcastId+"/cancel",{});
  activeBroadcastId=null;$("broadcast-preview-send").disabled=true;$("broadcast-start").disabled=true;$("broadcast-cancel").disabled=true;
  broadcastStatus("Brouillon annulé.");await refreshBroadcasts();
 }catch(e){broadcastStatus(String(e.message||e))}
};
$("broadcast-refresh").onclick=()=>refreshBroadcasts().catch(e=>broadcastStatus(String(e.message||e)));

let analyticsCached=null;
function analyticsList(where,entries,formatValue,formatLabel){
 const root=$(where);root.textContent="";
 if(!entries?.length){root.append(el("p","analytics-notice","Pas encore de données sur cette période."));return}
 const largest=Math.max(1,...entries.map(x=>Number(formatValue(x))||0));
 for(const item of entries){
  const value=Number(formatValue(item))||0;
  const card=el("div","analytics-row"),top=el("div","analytics-row-top");
  top.append(el("strong",null,formatLabel(item)),el("small",null,value.toLocaleString("fr-FR")));
  const bar=el("div","analytics-bar"),fill=el("span");fill.style.width=Math.max(2,100*value/largest)+"%";bar.append(fill);
  card.append(top,bar);root.append(card);
 }
}
function renderAnalytics(data){
 analyticsCached=data;const m=data.metrics||{},e=data.events||{};
 $("analytics-clock").textContent="Dernière mise à jour : "+new Date(data.generated_at).toLocaleTimeString("fr-FR");
 const keys=[
  ["bot_total","Comptes ayant démarré le bot · total"],
  ["bot_unique","Visiteurs du bot · période"],
  ["bot_starts","Commandes /start · période"],
  ["bot_recent","Bot · actifs sur 5 min"],
  ["app_total","Navigateurs connus · total"],
  ["app_unique","Visiteurs de la Mini App · période"],
  ["app_visits","Ouvertures Mini App · période"],
  ["app_active","Mini App · activité sur 5 min"]
 ];
 const cards=$("analytics-metrics");cards.textContent="";
 for(const [k,title] of keys){const box=el("div","metric");box.append(el("strong",null,Number(m[k]||0).toLocaleString("fr-FR")),el("small",null,title));cards.append(box)}
 for(const [k,title] of [["channel_open","Clics sur les canaux"],["pin_open","Clics sur les films"],["promo_open","Promotions ouvertes"],["share","Partages"],["rating","Avis reçus"]]){
  const box=el("div","metric");box.append(el("strong",null,Number(e[k]||0).toLocaleString("fr-FR")),el("small",null,title));cards.append(box)
 }
 $("analytics-note").textContent=data.note+" Les visiteurs uniques peuvent utiliser plusieurs appareils ; aucune identité réelle n'est enregistrée. Les chiffres précédant la mise en service ne sont pas reconstitués.";
 const counts=new Map();
 for(const x of data.daily?.app||[])counts.set(x.day_utc,{day:x.day_utc,app:Number(x.unique_visitors),visits:Number(x.visits),bot:0});
 for(const x of data.daily?.bot||[]){const row=counts.get(x.day_utc)||{day:x.day_utc,app:0,visits:0,bot:0};row.bot=Number(x.unique_visitors);counts.set(x.day_utc,row)}
 const days=[...counts.values()].sort((a,b)=>a.day<b.day?1:-1).slice(0,45);
 analyticsList("analytics-daily",days,x=>x.app+x.bot,x=>x.day+" · App "+x.app+" · Bot "+x.bot);
 analyticsList("analytics-channels",data.top_channels||[],x=>x.hits,x=>x.title);
 analyticsList("analytics-pins",(data.top_pins||[]).filter(x=>x.click_count>0),x=>x.click_count,x=>x.title+" · "+x.kind+" (total cumulé)");
 analyticsList("analytics-historic",(data.historical_channels||[]).filter(x=>x.opens>0),x=>x.opens,x=>x.title+" (total historique)");
 const promoted=(data.promos||[]).map(x=>({name:({actufoot_mrxp:"Actu Foot",ActuCrypto24H:"Actu Crypto",mrxpronosfr:"MR X PRONOS"}[x.target_key]||x.target_key),hits:x.hits}));
 const votes=(data.ratings||[]).map(x=>({name:x.target_key+" ★",hits:x.hits}));
 analyticsList("analytics-promos",[...promoted,...votes],x=>x.hits,x=>x.name);
}
async function refreshAnalytics(){
 const period=$("analytics-period").value;
 if(period==="custom"&&(!$("analytics-from").value||!$("analytics-to").value))return;
 const q=new URLSearchParams({period});
 if(period==="custom"){q.set("from",$("analytics-from").value);q.set("to",$("analytics-to").value)}
 try{renderAnalytics(await api("/api/admin/analytics?"+q.toString()))}
 catch(e){$("analytics-note").textContent="Statistiques indisponibles : "+String(e.message||e)}
}
$("analytics-period").onchange=()=>{
 $("analytics-custom").hidden=$("analytics-period").value!=="custom";
 if($("analytics-period").value!=="custom")refreshAnalytics();
};
$("analytics-refresh").onclick=refreshAnalytics;
$("analytics-csv").onclick=()=>{
 if(!analyticsCached)return;
 const rows=[["date_utc","visiteurs_app","visites_app","visiteurs_bot","demarrages_bot"]];
 const app=new Map((analyticsCached.daily?.app||[]).map(x=>[x.day_utc,x]));
 const bot=new Map((analyticsCached.daily?.bot||[]).map(x=>[x.day_utc,x]));
 const days=[...new Set([...app.keys(),...bot.keys()])].sort();
 for(const day of days){const a=app.get(day),b=bot.get(day);rows.push([day,a?.unique_visitors||0,a?.visits||0,b?.unique_visitors||0,b?.starts||0])}
 const csv=rows.map(r=>r.join(",")).join("\n"),blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="cine-radar-stats.csv";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1500);
};
setInterval(()=>{if(!document.hidden&&init&&!$("private").hidden)refreshAnalytics()},30000);

$("runChecks").onclick=async()=>{
 const btn=$("runChecks");btn.disabled=true;status("Contrôle des liens en cours…");
 try{const result=await api("/api/admin/run-check",{count:10});status(result.checked+" canaux examinés.");await load();}
 catch(e){status(String(e.message||e));}finally{btn.disabled=false;}
};
$("refreshJobs").onclick=()=>load().catch(e=>status(String(e.message||e)));
for(const action of ["hide","show","exclude"])$(action).onclick=async()=>{
 const id=Number($("channelId").value);if(!Number.isSafeInteger(id)||id<1){status("Identifiant invalide.");return;}
 if(action==="exclude"&&!confirm("Exclure durablement ce canal ?"))return;
 try{await manage(id,action);}catch(e){status(String(e.message||e));}
};
if(!init)status("Ouvre cette page depuis le bot Telegram avec ton compte administrateur.");
else load().catch(e=>status("Accès refusé ou service indisponible : "+String(e.message||e)));
})();
</script></body></html>`;
