import { initAdminMfaControl } from "./admin-mfa-ui.mjs";
import { mountIncidentCenter } from "./admin-incidents.mjs";
import { mountCronJobRegister,readCronJobs } from "./admin-cron-register.mjs";
import { createAdminHighlightWidget,loadAdminHighlights } from "./admin-unified-highlights.mjs";
import {adminSnapshotLabel} from "./admin-data-freshness.mjs";
import { mountAdminUsers } from "./admin-users.mjs";
import { inspectCmsEditorial } from "./cms-quality.mjs";
import { mountCmsServerSearch } from "./cms-server-search.mjs";
import { mountCmsBlockEditor } from "./cms-block-editor.mjs";
import { mountCmsRevisionPanel } from "./cms-revisions.mjs";
import { createCmsDraftCopy } from "./cms-duplicate.mjs";
import { mountCmsListFilters } from "./cms-list-filters.mjs";
import { mountCmsMediaFieldPicker, mountCmsMediaPicker } from "./cms-media-library.mjs";
import { supabaseUrl, supabaseAnonKey } from "./config.js";
import "./loading-ui.js";


// Charger la feuille de style sans modifier la page de connexion administrateur.
if (!document.querySelector('link[href*="loading-ui.css"]')) {
  const mxLoadingSheet = document.createElement("link");
  mxLoadingSheet.rel = "stylesheet";
  mxLoadingSheet.href = "assets/css/loading-ui.css?v=20261012-3";
  document.head.appendChild(mxLoadingSheet);
}

const sb = window.supabase.createClient(supabaseUrl, supabaseAnonKey);
const $ = (id) => document.getElementById(id);

const premiumAdminLoading = (kind = "admin", count = 3) =>
  window.MXLoading?.render?.(kind, count) || '<div class="muted">Chargement…</div>';


const TAB_NAMES = ["overview","pronostics","push","articles","conseils","bonus","infos","media","vip","health","incidents","users","audit"];
const loadedTabs = new Set();
let publishBusy = false;
let adminPermissions={read:true,cms:false,push:false,media:false,vip:false,users:false};
const tabPermission={articles:"cms",conseils:"cms",bonus:"cms",infos:"cms",
  media:"media",push:"push",vip:"vip",users:"users"};

function tabs() {
  return Array.from(document.querySelectorAll(".tab"));
}

function showOnlyTab(name) {
  tabs().forEach(t => {
    const active=t.dataset.tab===name;
    t.classList.toggle("active",active);
    t.setAttribute("aria-current",active?"page":"false");
  });
  TAB_NAMES.forEach(n => {
    const el = $(`tab-${n}`);
    if (!el) return;
    const active=n===name;
    el.hidden=!active;
    el.classList.toggle("active-screen",active);
  });
}

async function isAdmin() {
  const { data, error } = await sb.rpc("is_admin");
  if (error) return false;
  return data === true;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = String(s ?? "");
  return div.innerHTML;
}

function safeIdEq(a, b) {
  return String(a) === String(b);
}

// Keep original publication timestamps even when editing previously published CMS rows.
async function confirmCmsQuality(kind,row,rows){
  const {errors,warnings}=inspectCmsEditorial(kind,row,rows);
  if(row.status==="published"&&["articles","conseils","infos","bonus","bookmakers"].includes(kind)){
    const parts=[row.image_url,row.og_image,row.website,row.url,row.affiliate_url];
    const text=String(row.content||"");
    const matches=text.match(/https?:\/\/[^\s<>\[\]()"'\x60]+/g)||[];
    const urls=[...new Set([...parts,...matches].filter(x=>typeof x==="string"&&/^https?:\/\//.test(x))
      .map(x=>x.replace(/[.,;!?]+$/,"")))];
    if(urls.length>36)warnings.push("Plus de 36 liens : vérifier les liens restants.");
    const session=(await sb.auth.getSession()).data.session;
    if(!session?.access_token)errors.push("Session expirée : contrôle des liens impossible.");
    else for(let i=0;i<Math.min(urls.length,36);i+=12){
      try{
        const response=await fetch(supabaseUrl+"/functions/v1/admin-link-check",{
          method:"POST",headers:{"Authorization":"Bearer "+session.access_token,
            apikey:supabaseAnonKey,"Content-Type":"application/json"},
          body:JSON.stringify({urls:urls.slice(i,i+12)})
        });
        const checked=await response.json().catch(()=>({}));
        if(!response.ok)throw Error(checked.error||"HTTP "+response.status);
        for(const link of checked.results||[]){
          if(link.status==="broken")
            errors.push("Lien introuvable (HTTP "+link.http_status+") : "+link.url);
          else if(["unsafe_or_unresolvable","warning","invalid"].includes(link.status))
            warnings.push("Lien à vérifier : "+link.url);
        }
      }catch(e){warnings.push("Contrôle des liens indisponible : "+String(e?.message||e));}
    }
  }
  if(errors.length){alert("Enregistrement refusé :\n"+errors.slice(0,8).join("\n"));return false;}
  if(warnings.length&&!confirm("À vérifier avant publication :\n"+
    warnings.slice(0,6).join("\n")+
    (warnings.length>6?"\n… et "+(warnings.length-6)+" autres":"")+
    "\n\nEnregistrer malgré ces avertissements ?"))return false;
  return true;
}

function preservedPublicationDate(rows,saveId,status) {
  const previous=(rows||[]).find(item=>safeIdEq(item.id,saveId));
  return status==="published" ? (previous?.published_at || new Date().toISOString())
    : (previous?.published_at || null);
}

// Avoid repeating large form fields above each article list.
function organizeCmsEditor(root) {
  const card=root?.querySelector(":scope > .card");
  const title=card?.querySelector(":scope > h3");
  const listHeading=card?.querySelector(":scope > h4");
  if(!title||!listHeading)return;
  const group=document.createElement("div");
  group.className="admin-cms-editor-fields";
  // Keep a short contextual note visible above the collapsed editor.
  const description=title.nextElementSibling?.matches("p.muted")?title.nextElementSibling:null;
  const anchor=description||title;
  while(anchor.nextElementSibling && anchor.nextElementSibling!==listHeading) {
    group.appendChild(anchor.nextElementSibling);
  }
  anchor.after(group);
  const toggle=document.createElement("button");
  toggle.type="button";
  toggle.className="btn btn-secondary admin-cms-editor-toggle";
  toggle.textContent="Créer / modifier un contenu";
  toggle.setAttribute("aria-expanded","false");
  group.hidden=true;
  anchor.after(toggle);
  const show=(visible)=>{
    group.hidden=!visible;
    toggle.setAttribute("aria-expanded",String(visible));
    toggle.textContent=visible?"Masquer le formulaire":"Créer / modifier un contenu";
  };
  toggle.addEventListener("click",()=>show(group.hidden));
  return {show};
}

async function renderAdminOverview() {
  const root = $("admin-overview-summary");
  if(!root)return;
  root.replaceChildren();
  const toolbar=document.createElement("div");toolbar.className="admin-section-heading";
  const h=document.createElement("h3");h.textContent="Pilotage en un coup d'œil";
  const refresh=document.createElement("button");refresh.type="button";refresh.className="btn btn-secondary";
  refresh.textContent="↻ Actualiser";
  toolbar.append(h,refresh);root.appendChild(toolbar);
  const state=document.createElement("p");state.className="muted";state.setAttribute("role","status");
  state.textContent="Lecture des indicateurs en cours…";root.appendChild(state);
  const grid=document.createElement("div");grid.className="admin-overview-kpis";root.appendChild(grid);
  const health=document.createElement("div");health.className="admin-overview-health";root.appendChild(health);
  const links=document.createElement("nav");links.className="admin-overview-links";
  links.setAttribute("aria-label","Voir les statistiques spécialisées");
  for(const [label,url] of [["Audience","statistiques-audience.html"],["Installation","statistiques-installation.html"],["Supervision complète","admin-supervision.html"]]){
    const a=document.createElement("a");a.href=url;a.target="_blank";a.rel="noopener noreferrer";
    a.textContent=label+" ↗";links.appendChild(a);
  }
  root.appendChild(links);
  const extra=document.createElement("div");root.append(extra);
  const extraWidget=createAdminHighlightWidget(extra);
  const metric=(label,value)=>{
    const card=document.createElement("div");card.className="admin-kpi";
    const title=document.createElement("small");title.textContent=label;
    const main=document.createElement("strong");main.textContent=value;
    card.append(main,title);grid.appendChild(card);
  };
  const age=(value)=>{
    if(!value)return null;
    const elapsed=(Date.now()-Date.parse(value))/60000;
    return Number.isFinite(elapsed)?Math.max(0,Math.round(elapsed)):null;
  };
  const populate=async()=>{
    state.textContent="Actualisation…";refresh.disabled=true;
    try{
      const {data,error}=await sb.rpc("admin_monitor_snapshot",{p_days:7});
      if(error)throw error;
      grid.replaceChildren();health.replaceChildren();
      const m=data||{},analytics=m.analytics||{},live=m.live||{},telegram=m.telegram||{},push=m.push||{};
      metric("Visites estimées · 7 j",Number(analytics.visits||0).toLocaleString("fr-FR"));
      metric("Signaux LIVE · 7 j",Number(live.total||0).toLocaleString("fr-FR"));
      const resolved=Number(live.wins||0)+Number(live.losses||0);
      metric("Réussite vérifiée",resolved?(100*Number(live.wins||0)/resolved).toFixed(1)+" %":"—");
      metric("Publications Telegram",Number(telegram.total||0).toLocaleString("fr-FR"));
      metric("Abonnements Push",Number(push.subscriptions||0).toLocaleString("fr-FR"));
      const title=document.createElement("h3");title.textContent="Fraîcheur des services";health.appendChild(title);
      const list=document.createElement("div");list.className="admin-health-cards";
      for(const [name,time,threshold] of [
        ["Scraping LIVE",m.health?.live_scrape_last,5],
        ["Fusion des données",m.health?.live_merged_last,5],
        ["Dernier signal LIVE",m.health?.latest_live_prediction,180],
        ["Actualités Football",m.health?.last_actu_foot_run,120]
      ]) {
        const mins=age(time),entry=document.createElement("div");
        entry.className="admin-health-card";
        const label=document.createElement("b");label.textContent=name;
        const status=document.createElement("span");
        status.className="admin-health-"+(mins==null?"unknown":mins>threshold?"late":"good");
        status.textContent=mins==null?"Donnée indisponible":mins>threshold?"Retard · "+mins+" min":"À jour · "+mins+" min";
        entry.append(label,status);list.appendChild(entry);
      }
      health.appendChild(list);
      state.textContent=adminSnapshotLabel("Supabase",new Date(),{windowText:"données estimées"});
      void loadAdminHighlights(sb).then(result=>extraWidget?.draw(result)).catch(err=>{
        extra.textContent="Indicateurs complémentaires indisponibles : "+String(err?.message||err);
      });
    }catch(err){
      state.textContent="Supervision indisponible : "+String(err?.message||err)+". Réessaie ou consulte la supervision détaillée.";
    }finally{refresh.disabled=false;}
  };
  refresh.addEventListener("click",()=>void populate());
  await populate();
}

// -----------------------------
// LAZY LOAD : charge la tab 1 fois
// -----------------------------
const TAB_LOADERS = {
  overview: renderAdminOverview,
  pronostics: renderPronosticsReadOnly,
  push: renderPushAdmin,
  articles: renderCmsArticles,
  conseils: renderCmsConseils,
  bonus: renderBonus,
  infos: renderInfos,
  media: renderMediaTab,
  vip: renderVip,
  health: renderHealth,
  audit: renderAudit,
  incidents: async () => mountIncidentCenter(sb,$("tab-incidents")),
  users: async () => mountAdminUsers(sb,$("tab-users")),
};

async function loadTabIfNeeded(name) {
  if (loadedTabs.has(name)) return;
  const loader = TAB_LOADERS[name];
  if (typeof loader !== "function") return;
  try {
    await loader();
    loadedTabs.add(name);
  } catch (error) {
    const target = $("tab-" + name);
    if (target) {
      target.replaceChildren();
      const notice = document.createElement("div");
      notice.className = "card";
      notice.setAttribute("role", "alert");
      notice.textContent = "Impossible de charger cette rubrique : " + String(error?.message || error);
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-secondary";
      retry.textContent = "Réessayer";
      retry.addEventListener("click", () => void loadTabIfNeeded(name));
      notice.appendChild(retry);
      target.appendChild(notice);
    }
  }
}

async function showTab(name) {
  if (!TAB_NAMES.includes(name)) name="overview";
  if(tabPermission[name]&&!adminPermissions[tabPermission[name]]) {
    alert("Ton rôle n'autorise pas cette rubrique.");
    return;
  }
  showOnlyTab(name);
  window.dispatchEvent(new CustomEvent("mx:admin-tab",{detail:{name}}));
  const target="#"+name;
  if (location.hash!==target) history.replaceState(null,"",target);
  await loadTabIfNeeded(name);
}
window.MXAdminNavigate = showTab;

// -----------------------------
// UI helpers
// -----------------------------
function setLoginMsg(msg) {
  const el = $("loginMsg");
  if (el) el.textContent = msg || "";
}

function setBtnDisabled(id, disabled) {
  const btn = $(id);
  if (btn) btn.disabled = !!disabled;
}


// -----------------------------
// PUSH (admin -> Edge Function admin-push -> push-notifications)
// + Ciblage: tous OU un user_id
// + Champs: title/body/url/tag
// + Bonus: bouton "Lister les abonnés" (Edge Function admin-list-subscribers)
// -----------------------------
async function renderPushAdmin(){
  const root=$("tab-push");if(!root)return;
  root.innerHTML=`
  <div class="card">
    <h3>Notifications Push</h3>
    <p class="muted">Prévisualise, teste sur un abonné ou programme une campagne. Aucune audience n'est présélectionnée.</p>
    <div class="admin-filter-row">
      <div><label for="push_audience">Destinataires</label>
        <select id="push_audience"><option value="">Choisir les destinataires…</option>
          <option value="user">Un abonné précis</option><option value="all">Tous les abonnés</option></select></div>
      <div id="push_user_wrap" hidden><label for="push_user_id">Identifiant de l'abonné</label>
        <input id="push_user_id" placeholder="MX-..." autocomplete="off"></div>
      <div><label for="push_schedule_at">Programmer (heure locale)</label>
        <input id="push_schedule_at" type="datetime-local"></div>
    </div>
    <label for="push_title">Titre</label><input id="push_title" maxlength="110" placeholder="Nouveaux pronostics">
    <label for="push_body">Message</label><textarea id="push_body" maxlength="700" rows="3" placeholder="Les nouvelles sélections sont disponibles."></textarea>
    <div class="admin-filter-row">
      <div><label for="push_url">Lien HTTPS au clic</label>
        <input id="push_url" type="url" value="https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"></div>
      <div><label for="push_tag">Tag (facultatif)</label><input id="push_tag" maxlength="100" placeholder="pronos-matin"></div>
    </div>
    <div class="admin-button-row">
      <button type="button" id="push_new" class="btn btn-secondary">Nouvelle campagne</button>
      <button type="button" id="push_preview" class="btn btn-secondary">Prévisualiser</button>
      <button type="button" id="push_test" class="btn btn-secondary">Envoyer un test ciblé</button>
      <button type="button" id="push_schedule" class="btn btn-secondary">Programmer</button>
      <button type="button" id="push_send" class="btn btn-primary">Envoyer maintenant</button>
    </div>
    <div id="push_status" class="muted" role="status" aria-live="polite" style="white-space:pre-line"></div>
    <div id="push_results" role="region" aria-label="Résultat de la campagne"></div>
  </div>
  <div class="card">
    <div class="admin-section-heading"><h3>Historique des campagnes</h3>
      <button type="button" id="push_history_refresh" class="btn btn-secondary">Actualiser</button></div>
    <div id="push_history" class="admin-pronostics-table-scroll" role="region" aria-label="Historique des notifications"></div>
  </div>
  <div class="card">
    <div class="admin-section-heading"><h3>Abonnés Push</h3>
      <button type="button" id="subs_refresh" class="btn btn-secondary">Rechercher</button></div>
    <label for="subs_search">Rechercher un identifiant</label>
    <input id="subs_search" type="search" placeholder="MX-..." autocomplete="off">
    <p id="subs_status" class="muted" role="status"></p>
    <div id="subs_list" class="admin-pronostics-table-scroll"></div>
    <button type="button" id="subs_more" class="btn btn-secondary" hidden>Charger la page suivante</button>
  </div>`;
  const setStatus=message=>{$("push_status").textContent=message||"";};
  let sendingPush=false,pendingRequestId=null,pendingPayload=null;
  const lock=value=>{
    sendingPush=value;
    for(const id of ["push_send","push_test","push_schedule"])$(id).disabled=value;
  };
  const getForm=(operation="send",test=false)=>{
    const mode=$("push_audience").value;
    const title=$("push_title").value.trim(),body=$("push_body").value.trim();
    const target=$("push_user_id").value.trim();
    if(!mode||!title||!body)throw Error("Choisis les destinataires, un titre et un message.");
    if((mode==="user"||test)&&!target)throw Error("Sélectionne un abonné pour cet envoi ciblé.");
    const url=$("push_url").value.trim();
    if(url){
      let u;
      try{u=new URL(url);}catch{throw Error("Lien invalide");}
      if(u.protocol!=="https:"||u.hostname!=="mrxpronos.github.io")throw Error("Lien HTTPS Mr XPRONOS obligatoire.");
    }
    const data={operation,title,body,url:url||null,tag:$("push_tag").value.trim()||null,
      audience:test?"user":mode,user_id:mode==="user"||test?target:null};
    if(operation==="schedule"){
      const scheduled=new Date($("push_schedule_at").value);
      if(!Number.isFinite(scheduled.getTime())||scheduled.getTime()-Date.now()<60000)
        throw Error("Choisis une date d'au moins une minute dans le futur.");
      data.scheduled_at=scheduled.toISOString();
    }
    return data;
  };
  const preview=()=>{
    try{
      const x=getForm();
      setStatus("Aperçu · "+(x.audience==="all"?"Tous les abonnés":x.user_id)+"\n"+x.title+"\n"+x.body);
      return x;
    }catch(e){setStatus(String(e.message||e));return null;}
  };
  $("push_audience").addEventListener("change",()=>{
    $("push_user_wrap").hidden=$("push_audience").value!=="user";
  });
  // Do not reuse idempotency keys after any user-visible content change.
  for(const el of root.querySelectorAll("#push_audience,#push_user_id,#push_title,#push_body,#push_url,#push_tag,#push_schedule_at")){
    el.addEventListener("input",()=>{pendingRequestId=null;pendingPayload=null;});
  }
  $("push_new").addEventListener("click",()=>{
    pendingRequestId=null;pendingPayload=null;
    $("push_title").value="";$("push_body").value="";
    $("push_schedule_at").value="";$("push_tag").value="";
    setStatus("Nouveau formulaire : une nouvelle campagne pourra être créée.");
    $("push_results").replaceChildren();$("push_title").focus();
  });
  $("push_preview").addEventListener("click",preview);
  async function api(payload){
    const session=(await sb.auth.getSession()).data.session;
    if(!session)throw Error("Session expirée.");
    const response=await fetch(supabaseUrl+"/functions/v1/admin-push",{
      method:"POST",headers:{"Content-Type":"application/json",
        Authorization:"Bearer "+session.access_token,apikey:supabaseAnonKey},
      body:JSON.stringify(payload)
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(data.error||"Erreur HTTP "+response.status);
    return data;
  }
  const result=data=>{
    const box=$("push_results");
    box.replaceChildren();
    const message=document.createElement("p");
    const stats=data?.summary||{};
    message.textContent=data.status==="queued"?"Campagne programmée · "+new Date(data.scheduled_at).toLocaleString("fr-FR"):
      data.reused?"Demande déjà reçue : "+data.status:
      data.status==="sent"?"Envoi terminé · "+Number(stats.sent||0)+" envoyées, "+Number(stats.failed||0)+" échecs, "+Number(stats.skipped||0)+" ignorées.":
      data.status==="failed"?"Envoi en échec : "+(data.error||"Consulte l'historique"):
      "État de campagne : "+(data.status||"inconnu");
    box.append(message);
  };
  async function submit(operation,test=false){
    if(sendingPush)return;
    let payload;
    try{payload=getForm(operation,test);}catch(e){setStatus(e.message);return;}
    const fingerprint=JSON.stringify(payload);
    if(!pendingRequestId||pendingPayload!==fingerprint){
      pendingRequestId=crypto.randomUUID();pendingPayload=fingerprint;
    }
    const name=test?"l'abonné "+payload.user_id:payload.audience==="all"?"TOUS les abonnés":"l'abonné "+payload.user_id;
    const action=operation==="schedule"?"Programmer pour "+new Date(payload.scheduled_at).toLocaleString("fr-FR"):"Envoyer maintenant à "+name;
    if(!confirm(action+" ?\n\n"+payload.title+"\n"+payload.body))return;
    lock(true);setStatus("Enregistrement de la campagne…");
    try{
      const response=await api({...payload,request_id:pendingRequestId});
      result(response);
      setStatus(response.reused
        ? "Cette demande a déjà été enregistrée ; aucun nouvel envoi n'a été déclenché."
        : "Campagne enregistrée. Consulte l'historique pour vérifier sa livraison.");
      // Keep the same request ID while the form remains unchanged. A second
      // click must return the original campaign rather than dispatch again.
      await reloadHistory();
    }catch(e){
      setStatus("Résultat incertain ou échec : "+String(e?.message||e)+
        ". Vérifie l'historique avant un nouvel envoi ; la clé de demande est conservée.");
    }finally{lock(false);}
  }
  $("push_send").addEventListener("click",()=>void submit("send"));
  $("push_test").addEventListener("click",()=>void submit("send",true));
  $("push_schedule").addEventListener("click",()=>void submit("schedule"));
  async function reloadHistory(){
    const view=$("push_history");view.textContent="Chargement…";
    try{
      const data=await api({operation:"history"});
      view.replaceChildren();
      const table=document.createElement("table");
      table.innerHTML="<thead><tr><th>Date prévue</th><th>Campagne</th><th>Audience</th><th>Statut</th><th>Action</th></tr></thead>";
      const body=document.createElement("tbody");
      for(const row of data.campaigns||[]){
        const tr=document.createElement("tr");
        for(const value of [new Date(row.scheduled_at).toLocaleString("fr-FR"),
          row.title,row.recipient_user_id||"Tous",row.status]){
          const td=document.createElement("td");td.textContent=String(value);tr.append(td);
        }
        const td=document.createElement("td");
        if(row.status==="queued"){
          const button=document.createElement("button");button.type="button";
          button.className="btn btn-secondary";button.textContent="Annuler";
          button.addEventListener("click",async()=>{
            if(!confirm("Annuler cette notification programmée ?"))return;
            button.disabled=true;
            try{await api({operation:"cancel",id:row.id});await reloadHistory();}
            catch(e){setStatus("Annulation impossible : "+e.message);button.disabled=false;}
          });td.append(button);
        }else if(row.summary&&Object.keys(row.summary).length){
          const summary=document.createElement("small");
          summary.textContent=Number(row.summary.sent||0)+" envoyées / "+Number(row.summary.failed||0)+" échecs";
          td.append(summary);
          if(row.summary.logs_incomplete)td.append(document.createTextNode(" · Journal incomplet"));
        }
        if(row.status==="sent"){
          const details=document.createElement("button");details.type="button";
          details.className="btn btn-secondary";details.textContent="Appareils";
          details.addEventListener("click",async()=>{
            details.disabled=true;
            const wrap=document.createElement("div");wrap.className="admin-push-device-log";
            wrap.setAttribute("role","region");wrap.setAttribute("aria-label","Détail par appareil");
            try{
              const result=await api({operation:"details",id:row.id});
              const items=result.devices||[];
              if(!items.length){wrap.textContent="Aucun détail par appareil enregistré.";td.append(wrap);return;}
              const heading=document.createElement("p");
              heading.textContent=items.length+" appareil(s) documenté(s). Les adresses sont masquées.";
              wrap.append(heading);
              for(const device of items){
                const item=document.createElement("div");item.className="admin-device-row";
                const info=document.createElement("span");
                info.textContent="#"+String(device.digest).slice(0,12)+" · "+
                  String(device.result||"indéterminé")+
                  (device.http_status?" · HTTP "+device.http_status:"")+
                  (device.error_message?" · "+device.error_message:"");
                item.append(info);
                if(device.result==="failed"&&[429,502,503,504].includes(Number(device.http_status))){
                  const retry=document.createElement("button");retry.className="btn btn-secondary";
                  retry.type="button";retry.textContent="Réessayer uniquement cet appareil";
                  retry.addEventListener("click",async()=>{
                    if(prompt("Réessai ciblé : une notification peut être reçue en retard.\n"
                      +"Pour confirmer, saisis RENVOYER APPAREIL")!=="RENVOYER APPAREIL")return;
                    retry.disabled=true;
                    try{
                      const result=await api({operation:"retry_failed",id:row.id,
                        endpoint_digest:device.digest,request_id:crypto.randomUUID(),
                        acknowledge:"RENVOYER APPAREIL"});
                      retry.textContent=result.reused?"Réessai déjà créé":"Réessai enregistré";
                      setStatus("Réessai ciblé : "+String(result.status||"reçu")+".");
                      await reloadHistory();
                    }catch(err){setStatus("Réessai impossible : "+String(err?.message||err));retry.disabled=false;}
                  });
                  item.append(retry);
                }
                wrap.append(item);
              }
              td.append(wrap);
            }catch(err){setStatus("Diagnostic indisponible : "+String(err?.message||err));}
            finally{details.disabled=false;details.hidden=true;}
          });td.append(details);
        }
        tr.append(td);body.append(tr);
      }
      table.append(body);view.append(table);
    }catch(e){view.textContent="Historique indisponible : "+String(e?.message||e);}
  }
  $("push_history_refresh").addEventListener("click",()=>void reloadHistory());
  let nextPage=0,hasMore=false,lastSubscribers=new Map(),subscriberBusy=false;
  const renderSubs=()=>{
    const list=$("subs_list");list.replaceChildren();
    const rows=[...lastSubscribers.values()].sort((a,b)=>String(b.last_subscribed_at||"").localeCompare(a.last_subscribed_at||""));
    if(!rows.length){list.textContent="Aucun abonné sur les pages chargées.";return;}
    const table=document.createElement("table");
    table.innerHTML="<thead><tr><th>Identifiant</th><th>Appareils</th><th>Dernière inscription</th><th>Action</th></tr></thead>";
    const body=document.createElement("tbody");
    for(const row of rows.slice(0,500)){
      const tr=document.createElement("tr");
      for(const value of [row.user_id,row.endpoints,row.last_subscribed_at||"—"]){
        const td=document.createElement("td");td.textContent=String(value);tr.append(td);
      }
      const td=document.createElement("td");
      const choose=document.createElement("button");choose.type="button";
      choose.className="btn btn-secondary";choose.textContent="Sélectionner";
      choose.addEventListener("click",()=>{
        $("push_audience").value="user";$("push_user_wrap").hidden=false;
        $("push_user_id").value=row.user_id;pendingRequestId=null;
        setStatus("Abonné sélectionné : "+row.user_id);
      });
      td.append(choose);tr.append(td);body.append(tr);
    }
    table.append(body);list.append(table);
    $("subs_status").textContent=rows.length+" abonné(s) chargé(s)"
      +(rows.length>500?" (500 affichés ; affine ta recherche).":"")
      +(hasMore?" · Il existe une page suivante.":" · Fin de liste.");
  };
  async function fetchSubscribers(reset=false){
    if(subscriberBusy)return;
    if(reset){nextPage=0;lastSubscribers.clear();hasMore=true;}
    if(!hasMore)return;
    subscriberBusy=true;$("subs_more").disabled=true;
    try{
      const session=(await sb.auth.getSession()).data.session;
      if(!session)throw Error("Session expirée.");
      const params=new URLSearchParams({page:String(nextPage),search:$("subs_search").value.trim()});
      const response=await fetch(supabaseUrl+"/functions/v1/admin-list-subscribers?"+params,{
        headers:{"Authorization":"Bearer "+session.access_token,apikey:supabaseAnonKey}});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(data.error||"Échec HTTP "+response.status);
      for(const row of data.subscribers||[]){
        const previous=lastSubscribers.get(row.user_id);
        if(previous){
          previous.endpoints+=row.endpoints;
          if(String(row.last_subscribed_at)>String(previous.last_subscribed_at))
            previous.last_subscribed_at=row.last_subscribed_at;
        } else lastSubscribers.set(row.user_id,{...row});
      }
      hasMore=!!data.has_more;nextPage++;renderSubs();
    }catch(e){$("subs_status").textContent="Erreur abonnés : "+String(e?.message||e);}
    finally{subscriberBusy=false;$("subs_more").disabled=false;$("subs_more").hidden=!hasMore;}
  }
  $("subs_refresh").addEventListener("click",()=>void fetchSubscribers(true));
  $("subs_more").addEventListener("click",()=>void fetchSubscribers(false));
  $("subs_search").addEventListener("keydown",event=>{
    if(event.key==="Enter"){event.preventDefault();void fetchSubscribers(true);}
  });
  await reloadHistory();
}

// -----------------------------
// STATS (corrigé : partages multi event_type)
// -----------------------------
async function renderStats() {
  const root = $("tab-stats");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const start = new Date();
  start.setHours(0,0,0,0);
  const startISO = start.toISOString();

  try {
    const { count: views } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .eq("event_type","visit")
      .gte("created_at", startISO);

    // ✅ Compatibilité : share / share_whatsapp / share_telegram
    const { count: shares } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .in("event_type", ["share", "share_whatsapp", "share_telegram"])
      .gte("created_at", startISO);

    const { count: clicks } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .eq("event_type","click_pronostic")
      .gte("created_at", startISO);

    const { count: vip } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .eq("event_type","vip_conversion")
      .gte("created_at", startISO);

    root.innerHTML = `
      <div class="row">
        <div class="card"><div class="muted">Visites (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${views||0}</div></div>
        <div class="card"><div class="muted">Partages (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${shares||0}</div></div>
        <div class="card"><div class="muted">Clics pronos (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${clicks||0}</div></div>
        <div class="card"><div class="muted">Conversions VIP (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${vip||0}</div></div>
      </div>
      <div class="muted" style="margin-top:10px">Astuce: harmonise les event_type dans main.js si tu veux des stats parfaites.</div>
    `;
  } catch (e) {
    root.innerHTML = `<div class="muted">Erreur stats: ${escapeHtml(e?.message || e)}</div>`;
  }
}

// -----------------------------
// PRONOSTICS (lecture seule)
// -----------------------------
async function renderPronosticsReadOnly() {
  const root = $("tab-pronostics");
  if (!root) return;
  root.innerHTML = `
    <div class="card admin-pronostics-panel">
      <div class="admin-section-heading">
        <div><h3>Pronostics Pro & VIP</h3><p class="muted">Flux public · consultation et diagnostic, sans modifier les résultats</p></div>
        <button type="button" class="btn btn-secondary" id="pRefresh">↻ Actualiser</button>
      </div>
      <div class="admin-filter-row">
        <div><label for="pDay">Date</label><select id="pDay">
          <option value="today">Aujourd'hui</option><option value="tomorrow">Demain</option>
          <option value="yesterday">Hier</option>
        </select></div>
        <div><label for="pCat">Catégorie</label><select id="pCat">
          <option value="pro">Pro</option><option value="vip">VIP</option>
        </select></div>
        <div><label for="pSearch">Recherche</label><input id="pSearch" type="search" placeholder="Équipe ou compétition"></div>
      </div>
      <div id="pStatus" class="muted" role="status" aria-live="polite">Chargement des pronostics…</div>
      <div id="pDiagnostics" class="muted" role="status" aria-live="polite"></div>
      <div id="pList"></div>
    </div>`;
  let matches = [];
  let loadFailed = false;
  const dayKey = (day) => {
    const d = new Date();
    d.setUTCHours(0,0,0,0);
    d.setUTCDate(d.getUTCDate() + (day === "tomorrow" ? 1 : day === "yesterday" ? -1 : 0));
    return d.toISOString().slice(0,10);
  };
  const safeLogo = (value) => {
    if (!value) return "";
    try {
      const target = new URL(String(value),document.baseURI);
      return (target.protocol === "https:" || target.origin === location.origin)
        ? target.href : "";
    } catch { return ""; }
  };
  const scoreOf = (m) => {
    const h = m.home_score ?? m.score?.home ?? m.score?.home_score;
    const a = m.away_score ?? m.score?.away ?? m.score?.away_score;
    return h != null && a != null ? `${h}-${a}` : "—";
  };
  const labelStatus = (m) => {
    const raw = String(m.status || m.result || "").toLowerCase();
    if (["won","win","gagné","gagne","success"].includes(raw)) return "Gagné";
    if (["lost","loss","perdu","failed"].includes(raw)) return "Perdu";
    if (["void","cancelled","annulé"].includes(raw)) return "Annulé";
    if (m.is_finished) return "Terminé · à vérifier";
    return "En attente";
  };
  const render = () => {
    const date = dayKey($("pDay").value);
    const category = $("pCat").value;
    const search = $("pSearch").value.toLocaleLowerCase("fr").trim();
    const selected = matches.filter(m => {
      const when = String(m.event_date || m.date || m.kickoff || "").slice(0,10);
      const searchable = [m.home_team,m.away_team,m.league].join(" ").toLocaleLowerCase("fr");
      return when === date && String(m.category||"").toLowerCase() === category
        && (!search || searchable.includes(search));
    });
    $("pStatus").textContent = loadFailed ? "Flux indisponible : vérifie la publication de data.json."
      : selected.length ? `${selected.length} rencontre(s) · ${category.toUpperCase()} · ${date}`
      : `Aucun pronostic ${category.toUpperCase()} pour le ${date}.`;
    if (loadFailed || !selected.length) {
      $("pList").replaceChildren();
      return;
    }
    const head = '<div class="admin-pronostics-table-scroll"><table><thead><tr><th>Match / compétition</th><th>Pronostic</th><th>Confiance</th><th>Score</th><th>État</th></tr></thead><tbody>';
    const rows = selected.map(m => {
      const logo = (name,url) => {
        const src = safeLogo(url);
        return src ? `<img class="admin-team-logo" src="${escapeHtml(src)}" alt="${escapeHtml(name)}" loading="lazy" onerror="this.hidden=true">` : "";
      };
      const pred = m.prediction || (Array.isArray(m.predictions) ? m.predictions[0] : {}) || {};
      const market = pred.market_label || pred.bet_type || pred.type || pred.double_chance || pred.pick || "—";
      const confidenceRaw = Number(pred.confidence);
      const confidence = pred.confidence == null || !Number.isFinite(confidenceRaw)
        ? "—" : `${(confidenceRaw <= 1 ? confidenceRaw*100 : confidenceRaw).toFixed(0)} %`;
      const when = m.event_date || m.kickoff || "";
      const localDate = when && !Number.isNaN(Date.parse(when)) ? new Date(when).toLocaleString("fr-FR",{timeZone:"UTC",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})+" UTC" : "—";
      return `<tr>
        <td><div class="admin-team-pair">${logo(m.home_team,m.home_logo)}<b>${escapeHtml(m.home_team||"Équipe A")}</b><span>–</span><b>${escapeHtml(m.away_team||"Équipe B")}</b>${logo(m.away_team,m.away_logo)}</div>
          <small class="muted">${escapeHtml(m.league||"")} · ${escapeHtml(localDate)}</small></td>
        <td>${escapeHtml(market)}</td><td>${escapeHtml(confidence)}</td>
        <td>${escapeHtml(scoreOf(m))}</td><td>${escapeHtml(labelStatus(m))}</td></tr>`;
    }).join("");
    $("pList").innerHTML = head + rows + "</tbody></table></div>";
  };
  const refresh = async () => {
    $("pStatus").textContent = "Actualisation du flux…";
    try {
      const response = await fetch(`data.json?t=${Date.now()}`,{cache:"no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data?.matches)) throw new Error("Format du flux incorrect");
      matches = data.matches;
      const last=String(data.updated_at||data.generated_at||data.last_updated||"");
      const time=Date.parse(last);
      const age=Number.isFinite(time)?Math.max(0,Math.round((Date.now()-time)/60000)):null;
      const invalid=matches.filter(m=>!["pro","vip"].includes(String(m.category||"").toLowerCase())).length;
      $("pDiagnostics").textContent="Flux : "+matches.length+" sélection(s) • "
        +(age==null?"Date de génération non indiquée":age+" min depuis génération")+
        (age!=null&&age>180?" · Retard possible":"")+
        (invalid?" · "+invalid+" catégorie(s) inconnue(s)":" · Catégories valides");
      loadFailed = false;
    } catch(err) {
      loadFailed = true;
      matches = [];
      $("pDiagnostics").textContent="Erreur de diagnostic : "+String(err?.message||err);
    }
    render();
  };
  for (const id of ["pDay","pCat","pSearch"]) $(id).addEventListener("input",render);
  $("pRefresh").addEventListener("click",()=>void refresh());
  await refresh();
}

// Bounded, server-side paginated CMS retrieval replaces the old 50-row cap.
// The UI reports when the safety limit is reached instead of silently omitting content.
async function loadCmsRows(table) {
  const all=[],size=200,maximum=2000;
  for(let offset=0;offset<maximum;offset+=size){
    const {data,error}=await sb.from(table).select("*")
      .order("updated_at",{ascending:false}).range(offset,offset+size-1);
    if(error)return {data:all,error,truncated:false};
    const page=Array.isArray(data)?data:[];
    all.push(...page);
    if(page.length<size)return {data:all,error:null,truncated:false};
  }
  return {data:all,error:null,truncated:true};
}
function warnCmsTruncated(root,truncated){
  if(!truncated)return;
  const warning=document.createElement("p");warning.className="muted";warning.setAttribute("role","status");
  warning.textContent="Plus de 2 000 contenus : seuls les derniers enregistrements sont affichés. Prévoir une recherche serveur pour explorer toute l'archive.";
  root.querySelector(".card")?.appendChild(warning);
}

// -----------------------------
// CMS ARTICLES
// -----------------------------
async function renderCmsArticles() {
  const root = $("tab-articles");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const { data, error, truncated } = await loadCmsRows("cms_articles");
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Articles</h3>
      <p class="muted">Cette liste contient les publications éditoriales du CMS. Les analyses générées automatiquement sont conservées dans GitHub et ne sont pas écrasées lors de la publication.</p>

      <div class="row">
        <div><label>Slug</label><input id="a_slug"></div>
        <div><label>Titre</label><input id="a_title"></div>
      </div>

      <label>Image URL</label><input id="a_image">
      <label>Meta description</label><input id="a_meta">
      <div class="row">
        <div><label>Catégorie</label><input id="a_category" placeholder="Analyse, actu, guide…"></div>
        <div><label>Étiquettes (virgules)</label><input id="a_tags" placeholder="Football, tactique"></div>
      </div>
      <label>Contenu</label><textarea id="a_content" rows="8"></textarea>

      <div class="row">
        <div><label>Status</label>
          <select id="a_status"><option value="draft">Brouillon</option><option value="published">Publié</option></select>
        </div>
        <div><label>Actif</label>
          <select id="a_active"><option value="true">Actif</option><option value="false">Désactivé</option></select>
        </div>
      </div>

      <button id="a_save" class="btn btn-primary" style="margin-top:10px">Enregistrer</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste</h4>
      <div style="margin-top:10px">
        ${rows.map(a => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${escapeHtml(a.id)}">
            <div style="font-weight:900">${escapeHtml(a.title)}</div>
            <div class="muted">${escapeHtml(a.slug)} • ${escapeHtml(a.status)} • ${a.active !== false ? "Actif" : "Désactivé"}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  warnCmsTruncated(root,truncated);
  const articleEditorLayout=organizeCmsEditor(root);
  const cmsEditor = mountCmsBlockEditor({sb,textarea:$("a_content"),kind:"articles"});
  mountCmsMediaFieldPicker(sb,$("a_image"));

  const versions = mountCmsRevisionPanel({sb,table:"cms_articles",
    container:root.querySelector(".card"),onChoose:row=>setForm(row)});
  const setForm = (a) => {
    $("a_slug").value = a.slug || "";
    $("a_title").value = a.title || "";
    $("a_image").value = a.image_url || "";
    $("a_meta").value = a.meta_description || "";
    $("a_category").value = a.category || "";
    $("a_tags").value = (a.tags||[]).join(", ");
    cmsEditor.setMarkdown(a.content || "",a.id);
    $("a_status").value = a.status || "draft";
    $("a_active").value = (a.active !== false) ? "true" : "false";
    $("a_save").dataset.id = a.id;
    articleEditorLayout?.show(true);
    void versions.load(a.id);
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const a = rows.find(x => safeIdEq(x.id, id));
      if (a) setForm(a);
    });
  });

  attachDuplicateButtons(root,"[data-id]",rows,"articles",setForm,"a_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-id]")],rows,kind:"articles"});
  mountCmsServerSearch({sb,root,kind:"articles",onChoose:row=>{
    if(!rows.some(x=>safeIdEq(x.id,row.id)))rows.push(row);
    setForm(row);
  }});

  $("a_save").addEventListener("click", async () => {
    let cmsText;
    try { cmsText=cmsEditor.getMarkdown(); } catch(error) { alert(error.message); return; }
    const row = {
      slug: $("a_slug").value.trim(),
      title: $("a_title").value.trim(),
      image_url: $("a_image").value.trim(),
      og_image: $("a_image").value.trim(),
      meta_description: $("a_meta").value.trim(),
      category: $("a_category").value.trim(),
      tags: $("a_tags").value.split(",").map(x=>x.trim()).filter(Boolean).slice(0,12),
      content: cmsText,
      status: $("a_status").value,
      active: $("a_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: preservedPublicationDate(rows, $("a_save").dataset.id, $("a_status").value)
    };
    if (!row.slug || !row.title || !row.content) return alert("Slug/Titre/Contenu requis.");

    const id = $("a_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    if(!(await confirmCmsQuality("articles",payload,rows)))return;
    const { error } = await sb.from("cms_articles").upsert(payload);
    if (error) return alert(error.message);

    alert("Sauvegardé.");
    loadedTabs.delete("articles");
    await renderCmsArticles();
    loadedTabs.add("articles");
  });
}

// A copy must never reuse its source ID. No database write occurs until the admin saves it.
function attachDuplicateButtons(root,selector,rows,kind,fillForm,saveButtonId) {
  for(const card of root.querySelectorAll(selector)){
    const button=document.createElement("button");
    button.type="button";button.className="btn btn-secondary";
    button.textContent="Dupliquer en brouillon";
    button.style.marginTop="8px";
    button.addEventListener("click",event=>{
      event.preventDefault();event.stopPropagation();
      const sourceId=card.getAttribute("data-id")||card.getAttribute("data-bonus-id")||card.getAttribute("data-book-id");
      const original=rows.find(item=>safeIdEq(item.id,sourceId));
      if(!original)return;
      const draft=createCmsDraftCopy(kind,original,rows);
      fillForm(draft);
      delete $(saveButtonId).dataset.id;
      const status=document.createElement("p");
      status.className="muted";
      status.textContent="Copie préparée en brouillon inactif. Vérifie puis enregistre : l'original est intact.";
      $(saveButtonId).before(status);
      $(saveButtonId).scrollIntoView({behavior:"smooth",block:"center"});
    });
    card.appendChild(button);
  }
}

// -----------------------------
// CMS CONSEILS
// -----------------------------
async function renderCmsConseils() {
  const root = $("tab-conseils");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const { data, error, truncated } = await loadCmsRows("cms_conseils");
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Conseils</h3>
      <div class="row">
        <div><label>Slug</label><input id="c_slug"></div>
        <div><label>Titre</label><input id="c_title"></div>
      </div>
      <label>Image URL</label><input id="c_image">
      <div class="row">
        <div><label>Catégorie</label><input id="c_category" placeholder="Débutants, stratégie…"></div>
        <div><label>Niveau</label><select id="c_level">
          <option value="">Non précisé</option><option value="debutant">Débutant</option>
          <option value="intermediaire">Intermédiaire</option><option value="avance">Avancé</option>
        </select></div>
      </div>
      <label>Étiquettes</label><input id="c_tags" placeholder="Conseils, sécurité">
      <label>Contenu</label><textarea id="c_content" rows="6"></textarea>

      <div class="row">
        <div><label>Status</label>
          <select id="c_status"><option value="draft">Brouillon</option><option value="published">Publié</option></select>
        </div>
        <div><label>Actif</label>
          <select id="c_active"><option value="true">Actif</option><option value="false">Désactivé</option></select>
        </div>
      </div>

      <button id="c_save" class="btn btn-primary" style="margin-top:10px">Enregistrer</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste</h4>
      <div style="margin-top:10px">
        ${rows.map(c => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${escapeHtml(c.id)}">
            <div style="font-weight:900">${escapeHtml(c.title)}</div>
            <div class="muted">${escapeHtml(c.slug)} • ${escapeHtml(c.status)} • ${c.active !== false ? "Actif" : "Désactivé"}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  warnCmsTruncated(root,truncated);
  const conseilsEditorLayout=organizeCmsEditor(root);
  const cmsEditor = mountCmsBlockEditor({sb,textarea:$("c_content"),kind:"conseils"});
  mountCmsMediaFieldPicker(sb,$("c_image"));

  const versions = mountCmsRevisionPanel({sb,table:"cms_conseils",
    container:root.querySelector(".card"),onChoose:row=>setForm(row)});
  const setForm = (c) => {
    $("c_slug").value = c.slug || "";
    $("c_title").value = c.title || "";
    $("c_image").value = c.image_url || "";
    $("c_category").value = c.category || "";
    $("c_level").value = c.difficulty || "";
    $("c_tags").value = (c.tags||[]).join(", ");
    cmsEditor.setMarkdown(c.content || "",c.id);
    $("c_status").value = c.status || "draft";
    $("c_active").value = (c.active !== false) ? "true" : "false";
    $("c_save").dataset.id = c.id;
    conseilsEditorLayout?.show(true);
    void versions.load(c.id);
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const c = rows.find(x => safeIdEq(x.id, id));
      if (c) setForm(c);
    });
  });

  attachDuplicateButtons(root,"[data-id]",rows,"conseils",setForm,"c_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-id]")],rows,kind:"conseils"});
  mountCmsServerSearch({sb,root,kind:"conseils",onChoose:row=>{
    if(!rows.some(x=>safeIdEq(x.id,row.id)))rows.push(row);
    setForm(row);
  }});

  $("c_save").addEventListener("click", async () => {
    let cmsText;
    try { cmsText=cmsEditor.getMarkdown(); } catch(error) { alert(error.message); return; }
    const row = {
      slug: $("c_slug").value.trim(),
      title: $("c_title").value.trim(),
      image_url: $("c_image").value.trim(),
      category: $("c_category").value.trim(),
      difficulty: $("c_level").value,
      tags: $("c_tags").value.split(",").map(x=>x.trim()).filter(Boolean).slice(0,12),
      content: cmsText,
      status: $("c_status").value,
      active: $("c_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: preservedPublicationDate(rows, $("c_save").dataset.id, $("c_status").value)
    };
    if (!row.slug || !row.title || !row.content) return alert("Slug/Titre/Contenu requis.");

    const id = $("c_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    if(!(await confirmCmsQuality("conseils",payload,rows)))return;
    const { error } = await sb.from("cms_conseils").upsert(payload);
    if (error) return alert(error.message);

    alert("Sauvegardé.");
    loadedTabs.delete("conseils");
    await renderCmsConseils();
    loadedTabs.add("conseils");
  });
}

// -----------------------------
// BONUS + BOOKMAKERS
// -----------------------------
async function renderBonus() {
  const root = $("tab-bonus");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const [{ data: bonus, error: e1 }, { data: books, error: e2 }] = await Promise.all([
    loadCmsRows("cms_bonus"),
    loadCmsRows("cms_bookmakers")
  ]);
  if (e1 || e2) {
    root.innerHTML = `<div class="muted">Erreur: ${escapeHtml((e1||e2).message)}</div>`;
    return;
  }

  const bonusRows = bonus || [];
  const bookRows = books || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Bonus</h3>
      <div class="row">
        <div><label>Bookmaker</label><input id="b_bookmaker"></div>
        <div><label>Titre</label><input id="b_title"></div>
      </div>
      <label>Description</label><textarea id="b_description" rows="5"></textarea>
      <div class="row">
        <div><label>Image URL</label><input id="b_image"></div>
        <div><label>Lien</label><input id="b_link"></div>
      </div>
      <div class="row">
        <div><label>Footer</label><input id="b_footer"></div>
        <div><label>Status</label>
          <select id="b_status"><option value="draft">Brouillon</option><option value="published">Publié</option></select>
        </div>
      </div>
      <div class="row">
        <div><label>Date début</label><input id="b_start" type="date"></div>
        <div><label>Date fin</label><input id="b_end" type="date"></div>
      </div>
      <label>Actif</label>
      <select id="b_active"><option value="true">Actif</option><option value="false">Désactivé</option></select>
      <button id="b_save" class="btn btn-primary" style="margin-top:10px">Enregistrer bonus</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste bonus</h4>
      <div>
        ${bonusRows.map(b => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-bonus-id="${escapeHtml(b.id)}">
            <div style="font-weight:900">${escapeHtml(b.title)}</div>
            <div class="muted">${escapeHtml(b.bookmaker)} • ${escapeHtml(b.status)} • ${b.active !== false ? "Actif" : "Désactivé"}</div>
          </div>
        `).join("")}
      </div>
    </div>

    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Bookmakers</h3>
      <div class="row">
        <div><label>Nom</label><input id="bk_name"></div>
        <div><label>Logo URL</label><input id="bk_logo"></div>
      </div>
      <label>Lien</label><input id="bk_url">
      <label>Description</label><input id="bk_description">

      <div class="row">
        <div><label>Status</label>
          <select id="bk_status"><option value="published">Publié</option><option value="draft">Brouillon</option></select>
        </div>
        <div><label>Actif</label>
          <select id="bk_active"><option value="true">Actif</option><option value="false">Désactivé</option></select>
        </div>
      </div>

      <button id="bk_save" class="btn btn-primary" style="margin-top:10px">Enregistrer bookmaker</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste bookmakers</h4>
      <div>
        ${bookRows.map(b => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-book-id="${escapeHtml(b.id)}">
            <div style="font-weight:900">${escapeHtml(b.name)}</div>
            <div class="muted">${escapeHtml(b.status)} • ${b.active !== false ? "Actif" : "Désactivé"}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  mountCmsMediaFieldPicker(sb,$("b_image"));
  mountCmsMediaFieldPicker(sb,$("bk_logo"));

  const setBonus = (b) => {
    $("b_bookmaker").value = b.bookmaker || "";
    $("b_title").value = b.title || "";
    $("b_description").value = b.description || "";
    $("b_image").value = b.image_url || "";
    $("b_link").value = b.link || "";
    $("b_footer").value = b.footer || "";
    $("b_status").value = b.status || "draft";
    $("b_start").value = b.start_date || "";
    $("b_end").value = b.end_date || "";
    $("b_active").value = (b.active !== false) ? "true" : "false";
    $("b_save").dataset.id = b.id;
  };

  const setBook = (b) => {
    $("bk_name").value = b.name || "";
    $("bk_logo").value = b.logo || "";
    $("bk_url").value = b.url || "";
    $("bk_description").value = b.description || "";
    $("bk_status").value = b.status || "published";
    $("bk_active").value = (b.active !== false) ? "true" : "false";
    $("bk_save").dataset.id = b.id;
  };

  root.querySelectorAll("[data-bonus-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-bonus-id");
      const b = bonusRows.find(x => safeIdEq(x.id, id));
      if (b) setBonus(b);
    });
  });

  root.querySelectorAll("[data-book-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-book-id");
      const b = bookRows.find(x => safeIdEq(x.id, id));
      if (b) setBook(b);
    });
  });

  attachDuplicateButtons(root,"[data-bonus-id]",bonusRows,"bonus",setBonus,"b_save");
  attachDuplicateButtons(root,"[data-book-id]",bookRows,"bookmakers",setBook,"bk_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-bonus-id]")],rows:bonusRows,kind:"bonus",showCategory:false});
  mountCmsServerSearch({sb,root,kind:"bonus",onChoose:row=>{
    if(!bonusRows.some(x=>safeIdEq(x.id,row.id)))bonusRows.push(row);
    setBonus(row);
  }});
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-book-id]")],rows:bookRows,kind:"bookmakers",showCategory:false});
  mountCmsServerSearch({sb,root,kind:"bookmakers",onChoose:row=>{
    if(!bookRows.some(x=>safeIdEq(x.id,row.id)))bookRows.push(row);
    setBook(row);
  }});

  $("b_save").addEventListener("click", async () => {
    const row = {
      bookmaker: $("b_bookmaker").value.trim(),
      title: $("b_title").value.trim(),
      description: $("b_description").value.trim(),
      image_url: $("b_image").value.trim(),
      link: $("b_link").value.trim(),
      footer: $("b_footer").value.trim(),
      start_date: $("b_start").value || null,
      end_date: $("b_end").value || null,
      status: $("b_status").value,
      active: $("b_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: preservedPublicationDate(bonusRows, $("b_save").dataset.id, $("b_status").value)
    };
    if (!row.bookmaker || !row.title || !row.description) return alert("Bookmaker/Titre/Description requis.");

    const id = $("b_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    if(!(await confirmCmsQuality("bonus",payload,bonusRows)))return;
    const { error } = await sb.from("cms_bonus").upsert(payload);
    if (error) return alert(error.message);

    alert("Bonus sauvegardé.");
    loadedTabs.delete("bonus");
    await renderBonus();
    loadedTabs.add("bonus");
  });

  $("bk_save").addEventListener("click", async () => {
    const row = {
      name: $("bk_name").value.trim(),
      logo: $("bk_logo").value.trim(),
      url: $("bk_url").value.trim(),
      description: $("bk_description").value.trim(),
      status: $("bk_status").value,
      active: $("bk_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: preservedPublicationDate(bookRows, $("bk_save").dataset.id, $("bk_status").value)
    };
    if (!row.name) return alert("Nom requis.");

    const id = $("bk_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    if(!(await confirmCmsQuality("bookmakers",payload,bookRows)))return;
    const { error } = await sb.from("cms_bookmakers").upsert(payload);
    if (error) return alert(error.message);

    alert("Bookmaker sauvegardé.");
    loadedTabs.delete("bonus");
    await renderBonus();
    loadedTabs.add("bonus");
  });
}

// -----------------------------
// INFOS
// -----------------------------
async function renderInfos() {
  const root = $("tab-infos");
  if (!root) return;

  root.innerHTML = premiumAdminLoading("admin", 3);
  const { data, error, truncated } = await loadCmsRows("cms_infos");
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Infos</h3>
      <label>Titre</label><input id="i_title">
      <div class="row"><div><label>Catégorie</label><input id="i_category"></div>
        <div><label>Image</label><input id="i_image"></div></div>
      <label>Contenu</label><textarea id="i_content" rows="6"></textarea>
      <div class="row">
        <div><label>Status</label>
          <select id="i_status"><option value="draft">Brouillon</option><option value="published">Publié</option></select>
        </div>
        <div><label>Actif</label>
          <select id="i_active"><option value="true">Actif</option><option value="false">Désactivé</option></select>
        </div>
      </div>
      <button id="i_save" class="btn btn-primary" style="margin-top:10px">Enregistrer</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste</h4>
      ${rows.map(i => `
        <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${escapeHtml(i.id)}">
          <div style="font-weight:900">${escapeHtml(i.title)}</div>
          <div class="muted">${escapeHtml(i.status)} • ${i.active !== false ? "Actif" : "Désactivé"}</div>
        </div>
      `).join("")}
    </div>
  `;

  warnCmsTruncated(root,truncated);
  const infosEditorLayout=organizeCmsEditor(root);
  const cmsEditor = mountCmsBlockEditor({sb,textarea:$("i_content"),kind:"infos"});
  mountCmsMediaFieldPicker(sb,$("i_image"));

  const versions = mountCmsRevisionPanel({sb,table:"cms_infos",
    container:root.querySelector(".card"),onChoose:row=>setForm(row)});
  const setForm = (i) => {
    $("i_title").value = i.title || "";
    $("i_category").value = i.category || "";
    $("i_image").value = i.image_url || "";
    cmsEditor.setMarkdown(i.content || "",i.id);
    $("i_status").value = i.status || "draft";
    $("i_active").value = (i.active !== false) ? "true" : "false";
    $("i_save").dataset.id = i.id;
    infosEditorLayout?.show(true);
    void versions.load(i.id);
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const i = rows.find(x => safeIdEq(x.id, id));
      if (i) setForm(i);
    });
  });

  attachDuplicateButtons(root,"[data-id]",rows,"infos",setForm,"i_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-id]")],rows,kind:"informations"});
  mountCmsServerSearch({sb,root,kind:"infos",onChoose:row=>{
    if(!rows.some(x=>safeIdEq(x.id,row.id)))rows.push(row);
    setForm(row);
  }});

  $("i_save").addEventListener("click", async () => {
    let cmsText;
    try { cmsText=cmsEditor.getMarkdown(); } catch(error) { alert(error.message); return; }
    const row = {
      title: $("i_title").value.trim(),
      category: $("i_category").value.trim(),
      image_url: $("i_image").value.trim(),
      content: cmsText,
      status: $("i_status").value,
      active: $("i_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: preservedPublicationDate(rows, $("i_save").dataset.id, $("i_status").value)
    };
    if (!row.title || !row.content) return alert("Titre/Contenu requis.");

    const id = $("i_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    if(!(await confirmCmsQuality("infos",payload,rows)))return;
    const { error } = await sb.from("cms_infos").upsert(payload);
    if (error) return alert(error.message);

    alert("Info sauvegardée.");
    loadedTabs.delete("infos");
    await renderInfos();
    loadedTabs.add("infos");
  });
}

// -----------------------------
// CMS MEDIA LIBRARY
// -----------------------------
async function renderMediaTab(){
  const root=$("tab-media");if(!root)return;
  root.replaceChildren();
  const intro=document.createElement("div");
  intro.className="card";
  const h=document.createElement("h3");h.textContent="Médiathèque";
  const p=document.createElement("p");p.className="muted";
  p.textContent="Importer, rechercher et réutiliser les photos ou vidéos dans les publications. Attention : les fichiers sont hébergés dans un bucket public ; toute personne possédant leur URL peut les consulter, même avant publication. Les brouillons CMS, eux, ne sont pas publiés automatiquement.";
  const selected=document.createElement("p");selected.setAttribute("role","status");
  intro.append(h,p,selected);root.appendChild(intro);
  mountCmsMediaPicker(sb,intro,media=>{
    selected.textContent="Lien du média sélectionné : "+media.url;
    if(navigator.clipboard?.writeText)void navigator.clipboard.writeText(media.url).catch(()=>{});
  });
}

// -----------------------------
// VIP
// -----------------------------
async function renderVip() {
  const root = $("tab-vip");
  if (!root) return;

  root.innerHTML = premiumAdminLoading("admin", 3);
  const { data, error } = await sb.from("vip_access").select("*").order("expires_at",{ascending:false}).limit(200);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Accès VIP historiques</h3>
      <p class="muted">Gestion des codes et dates d'accès enregistrés dans Supabase. Les catégories de pronostics Pro et VIP affichées sur le site fonctionnent indépendamment de ce registre.</p>

      <div class="row">
        <div><label>User ID (MX-xxxx)</label><input id="v_user" placeholder="MX-..."></div>
        <div><label>IP (optionnel)</label><input id="v_ip" placeholder="1.2.3.4"></div>
      </div>

      <label>Durée (jours)</label><input id="v_days" type="number" min="1" max="365" value="30">

      <button id="v_reset" class="btn btn-primary" style="margin-top:10px">Créer / Réinitialiser VIP</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Actifs / Historique</h4>

      <table>
        <thead><tr><th>User</th><th>Code</th><th>Expire</th><th>Actif</th><th>Action</th></tr></thead>
        <tbody>
          ${rows.map(v => `
            <tr data-expires="${escapeHtml(v.expires_at||"")}" data-active="${v.active===true?"true":"false"}">
              <td>${escapeHtml(v.user_id)}</td>
              <td>${escapeHtml(v.code)}</td>
              <td>${v.expires_at ? new Date(v.expires_at).toLocaleString("fr-FR") : "-"}</td>
              <td>${v.active ? "oui" : "non"}</td>
              <td><button class="btn btn-secondary" data-revoke="${escapeHtml(v.user_id)}">Désactiver</button></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  $("v_reset").addEventListener("click", async () => {
    const uid = $("v_user").value.trim();
    const ip = $("v_ip").value.trim();
    const days = Number($("v_days").value);
    if (!uid) return alert("Identifiant utilisateur requis.");
    if (!Number.isInteger(days) || days<1 || days>365)
      return alert("Durée invalide : choisis entre 1 et 365 jours.");
    if (!confirm("Créer ou réinitialiser cet accès VIP ?\n\nCompte : "+uid+"\nDurée : "+days+" jours")) return;
    const btn=$("v_reset");btn.disabled=true;
    try{
      const { data, error } = await sb.rpc("admin_reset_vip", {
        p_user_id: uid,p_ip: ip,p_duration_days: days
      });
      if (error) throw error;
      const row = Array.isArray(data) ? data[0] : data;
      alert(`Accès VIP confirmé. Code : ${row?.code} / Expiration : ${row?.expires_at}`);
      loadedTabs.delete("vip");
      await renderVip();
      loadedTabs.add("vip");
    }catch(err){alert("Impossible de modifier l'accès VIP : "+String(err?.message||err));}
    finally{if(btn.isConnected)btn.disabled=false;}
  });

  root.querySelectorAll("[data-revoke]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const uid = btn.getAttribute("data-revoke");
      if (!confirm("Désactiver l'accès VIP du compte "+uid+" ?")) return;
      btn.disabled=true;
      try{
        const { error } = await sb.rpc("admin_revoke_vip", { p_user_id: uid });
        if (error) throw error;
        loadedTabs.delete("vip");
        await renderVip();
        loadedTabs.add("vip");
      }catch(err){alert("Désactivation impossible : "+String(err?.message||err));}
      finally{if(btn.isConnected)btn.disabled=false;}
    });
  });
}

// -----------------------------
// HEALTH
// -----------------------------
async function renderHealth() {
  const root=$("tab-health");if(!root)return;
  root.replaceChildren();
  const panel=document.createElement("section");panel.className="card";
  const header=document.createElement("div");header.className="admin-section-heading";
  const h=document.createElement("h3");h.textContent="Automatisations · dernier état connu";
  const button=document.createElement("button");button.type="button";button.className="btn btn-secondary";
  button.textContent="↻ Actualiser";header.append(h,button);
  const note=document.createElement("p");note.className="muted";note.setAttribute("role","status");
  const info=document.createElement("p");info.className="muted";
  info.textContent="Sources : Supabase cron_runs et GitHub Actions. Les tâches cron-job.org ne sont pas connectées et restent hors de ce registre.";
  const url=document.createElement("a");url.href="https://github.com/MrXPRONOS/MrXPRONOS_App/actions";
  url.target="_blank";url.rel="noopener noreferrer";url.textContent="Consulter GitHub Actions ↗";
  const table=document.createElement("table");
  table.innerHTML="<thead><tr><th>Tâche</th><th>Dernière exécution</th><th>État</th><th>Détails</th></tr></thead>";
  const body=document.createElement("tbody");table.appendChild(body);
  const ghTitle=document.createElement("h4");ghTitle.textContent="Dernières exécutions GitHub Actions";
  const ghStatus=document.createElement("p");ghStatus.className="muted";
  const ghTable=document.createElement("table");
  ghTable.innerHTML="<thead><tr><th>Workflow</th><th>Exécution</th><th>État</th><th>Déclencheur</th></tr></thead>";
  const ghBody=document.createElement("tbody");ghTable.append(ghBody);
  panel.append(header,info,url,note,table,ghTitle,ghStatus,ghTable);root.appendChild(panel);
  const externalCronRoot=document.createElement("div");root.append(externalCronRoot);
  mountCronJobRegister(sb,externalCronRoot,{
    supabaseUrl,anonKey:supabaseAnonKey
  });
  const load=async()=>{
    button.disabled=true;note.textContent="Actualisation des tâches…";
    try{
      const {data,error}=await sb.from("cron_runs").select("name,last_run_at,last_ok,meta")
        .order("last_run_at",{ascending:false}).limit(500);
      if(error)throw error;
      body.replaceChildren();
      for(const entry of data||[]){
        const tr=document.createElement("tr");
        const mk=value=>{const td=document.createElement("td");td.textContent=String(value??"—");tr.appendChild(td);return td};
        mk(entry.name);
        mk(entry.last_run_at?new Date(entry.last_run_at).toLocaleString("fr-FR"):"Jamais");
        const minutes=entry.last_run_at?(Date.now()-Date.parse(entry.last_run_at))/60000:null;
        const interval=Number(entry.meta?.expected_interval_minutes||0);
        const overdue=Number.isFinite(minutes)&&interval>0&&minutes>interval*2;
        const label=entry.last_ok===false?"Dernière exécution en échec":
          entry.last_ok===true?(overdue?"Retard à vérifier":"Dernière exécution réussie"):"État inconnu";
        mk(label+(minutes!=null&&Number.isFinite(minutes)?" · "+Math.max(0,Math.round(minutes))+" min":""));
        const td=document.createElement("td");const details=document.createElement("details");
        const summary=document.createElement("summary");summary.textContent="Détails";
        const pre=document.createElement("pre");pre.textContent=JSON.stringify(entry.meta||{},null,2);
        details.append(summary,pre);td.append(details);tr.append(td);body.append(tr);
      }
      note.textContent=(data?.length||0)+" tâche(s) Supabase enregistrée(s) · "+new Date().toLocaleTimeString("fr-FR")+".";
      ghStatus.textContent="Chargement GitHub Actions…";
      try{
        const response=await fetch("https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/runs?branch=main&per_page=70",
          {headers:{"Accept":"application/vnd.github+json"},cache:"no-store"});
        if(!response.ok)throw Error("GitHub HTTP "+response.status);
        const payload=await response.json(),runs=payload.workflow_runs||[];
        ghBody.replaceChildren();
        const groups=new Map();
        for(const run of runs){
          if(!groups.has(run.name))groups.set(run.name,[]);
          groups.get(run.name).push(run);
        }
        for(const [name,entries] of groups){
          const latest=entries[0];
          const duplicates=entries.some((r,i)=>entries.some((other,j)=>i!==j
            && r.id!==other.id&&r.event===other.event&&r.head_sha===other.head_sha
            && r.run_attempt===other.run_attempt
            && Math.abs(Date.parse(r.created_at)-Date.parse(other.created_at))<90000));
          const tr=document.createElement("tr");
          const title=document.createElement("td");
          const link=document.createElement("a");
          link.href=latest.html_url;link.target="_blank";link.rel="noopener noreferrer";
          link.textContent=name;
          title.append(link);
          const time=document.createElement("td");
          time.textContent=latest.created_at?new Date(latest.created_at).toLocaleString("fr-FR"):"—";
          const state=document.createElement("td");
          state.textContent=(latest.conclusion||latest.status||"inconnu")+
            (duplicates?" · Déclenchement doublé possible":"");
          const event=document.createElement("td");
          event.textContent=latest.event||"—";
          tr.append(title,time,state,event);ghBody.append(tr);
        }
        ghStatus.textContent=groups.size+" workflows représentés parmi "+runs.length+
          " exécutions récentes (échantillon GitHub, pas historique exhaustif).";
      }catch(err){
        ghStatus.textContent="GitHub indisponible : "+String(err?.message||err)+
          ". Les dernières informations Supabase restent consultables.";
      }
    }catch(e){note.textContent="Supervision des tâches indisponible : "+String(e?.message||e);}
    finally{button.disabled=false;}
  };
  button.addEventListener("click",()=>void load());
  await load();
}

// -----------------------------
// AUDIT
// -----------------------------
async function renderAudit(){
  const root=$("tab-audit");if(!root)return;
  root.replaceChildren();
  const panel=document.createElement("section");panel.className="card";
  const head=document.createElement("div");head.className="admin-section-heading";
  const title=document.createElement("h3");title.textContent="Journal d'audit";
  const exportButton=document.createElement("button");exportButton.type="button";
  exportButton.className="btn btn-secondary";exportButton.textContent="Exporter CSV";
  head.append(title,exportButton);
  const search=document.createElement("input");search.type="search";
  search.setAttribute("aria-label","Rechercher les actions du journal");
  search.placeholder="Rechercher une action ou un administrateur…";
  const status=document.createElement("p");status.className="muted";status.setAttribute("role","status");
  const wrap=document.createElement("div");wrap.className="admin-pronostics-table-scroll";
  const table=document.createElement("table");table.className="admin-audit-table";
  const thead=document.createElement("thead");thead.innerHTML="<tr><th>Date</th><th>Administrateur</th><th>Action</th><th>Détails</th></tr>";
  const tbody=document.createElement("tbody");table.append(thead,tbody);wrap.append(table);
  const more=document.createElement("button");more.type="button";more.className="btn btn-secondary";
  more.textContent="Charger 100 événements supplémentaires";
  panel.append(head,search,status,wrap,more);root.appendChild(panel);
  let rows=[],offset=0,done=false,busy=false;
  const apply=()=>{
    tbody.replaceChildren();
    const q=search.value.trim().toLocaleLowerCase("fr");
    const filtered=rows.filter(row=>
      [row.action,row.actor_user_id,JSON.stringify(row.details||{})]
        .some(value=>String(value||"").toLocaleLowerCase("fr").includes(q)));
    for(const row of filtered){
      const tr=document.createElement("tr");
      const cell=(value)=>{
        const td=document.createElement("td");td.textContent=String(value??"—");
        tr.appendChild(td);return td;
      };
      cell(row.created_at?new Date(row.created_at).toLocaleString("fr-FR"):"—");
      cell(row.actor_user_id||"Système");
      cell(row.action||"—");
      const detail=document.createElement("td");
      const summary=document.createElement("details");
      const trigger=document.createElement("summary");trigger.textContent="Voir";
      const pre=document.createElement("pre");pre.textContent=JSON.stringify(row.details||{},null,2);
      summary.append(trigger,pre);detail.append(summary);tr.append(detail);tbody.append(tr);
    }
    status.textContent=`${filtered.length} affiché(s) sur ${rows.length} événement(s) chargé(s).`
      +(done?" Fin de l'historique.":" Charger la suite pour explorer les anciens événements.");
  };
  const load=async()=>{
    if(busy||done)return;
    busy=true;more.disabled=true;
    try{
      const {data,error}=await sb.from("audit_log")
        .select("created_at,action,details,actor_user_id")
        .order("created_at",{ascending:false}).range(offset,offset+99);
      if(error)throw error;
      const page=data||[];rows.push(...page);offset+=page.length;done=page.length<100;
      apply();
    }catch(e){status.textContent="Lecture du journal impossible : "+String(e?.message||e);}
    finally{busy=false;more.disabled=false;more.hidden=done;}
  };
  search.addEventListener("input",apply);
  more.addEventListener("click",()=>void load());
  exportButton.addEventListener("click",()=>{
    const escapeCsv=value=>'"'+String(value??"").replaceAll('"','""')+'"';
    const lines=[["Date","Administrateur","Action","Détails"].map(escapeCsv).join(","),
      ...rows.map(x=>[x.created_at,x.actor_user_id,x.action,JSON.stringify(x.details||{})].map(escapeCsv).join(","))];
    const blob=new Blob(["\ufeff"+lines.join("\r\n")],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="mrxpronos-audit-"+new Date().toISOString().slice(0,10)+".csv";
    a.click();URL.revokeObjectURL(url);
    status.textContent="Export CSV : "+rows.length+" événement(s) chargé(s).";
  });
  await load();
}

// -----------------------------

async function cmsAdminRequest(operation,extra={}) {
  const session=(await sb.auth.getSession()).data.session;
  if(!session) throw new Error("Session administrateur expirée");
  const response=await fetch(`${supabaseUrl}/functions/v1/publish`,{
    method:"POST",
    headers:{"Content-Type":"application/json","Authorization":`Bearer ${session.access_token}`,"apikey":supabaseAnonKey},
    body:JSON.stringify({operation,...extra})
  });
  const data=await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(data.error||`Erreur HTTP ${response.status}`);
  return data;
}
function cmsDom(tag,text="",className="") {
  const node=document.createElement(tag);node.textContent=text;
  if(className)node.className=className;
  return node;
}
async function cmsCheckCommit(commit,root) {
  root.textContent="Vérification du déploiement GitHub Pages…";
  try {
    const s=await cmsAdminRequest("status",{commit});
    const map={deployed:"Déploiement réussi",pending:"Déploiement en cours",
      failed:"Déploiement échoué",unknown:"Statut de déploiement inconnu"};
    root.textContent=(map[s.deployment]||"Statut non confirmé")+" — "+commit.slice(0,12)+
      (s.is_current?" (version courante)":" (une autre version est courante)");
    if(s.workflow_url&&/^https:\/\/github\.com\//.test(s.workflow_url)){
      const a=cmsDom("a"," — Voir le workflow");a.href=s.workflow_url;a.target="_blank";a.rel="noopener noreferrer";
      root.appendChild(a);
    }
  }catch(error){root.textContent="Impossible de vérifier : "+error.message;}
}
async function cmsShowPreview(entry,root) {
  root.replaceChildren(cmsDom("p","Préparation de la comparaison…"));
  try{
    const data=await cmsAdminRequest("preview_restore",{version_id:entry.id});
    const p=data.preview;
    root.replaceChildren(cmsDom("h4","Prévisualisation du retour arrière"));
    root.appendChild(cmsDom("p","Source : "+p.target_commit.slice(0,12)+" | Branche actuelle : "+p.current_head.slice(0,12)));
    const table=cmsDom("table"),body=cmsDom("tbody");
    const head=cmsDom("tr");
    for(const name of ["Fichier","Actuel","Version choisie","Ajoutés","Supprimés","Modifiés"]){
      head.appendChild(cmsDom("th",name));
    }
    table.appendChild(head);
    for(const [file,change] of Object.entries(p.changes||{})){
      const tr=cmsDom("tr");
      for(const value of [file,change.before,change.after,change.added,change.removed,change.modified]){
        tr.appendChild(cmsDom("td",String(value)));
      }
      body.appendChild(tr);
      const examples=[...(change.samples?.added||[]),...(change.samples?.removed||[]),...(change.samples?.modified||[])];
      if(examples.length)root.appendChild(cmsDom("p",file+" — Exemples : "+examples.join(", "),"muted"));
    }
    table.appendChild(body);root.appendChild(table);
    const changes=Object.values(p.changes||{}).some(c=>c.different);
    if(!changes){root.appendChild(cmsDom("p","Ces fichiers sont identiques. Aucune restauration nécessaire."));return;}
    const warning=cmsDom("p","Attention : seuls les cinq fichiers de contenu seront restaurés. L'historique Git et la base Supabase restent inchangés.");
    root.appendChild(warning);
    const restore=cmsDom("button","Restaurer cette version","btn btn-secondary");restore.type="button";
    restore.addEventListener("click",async()=>{
      if(!window.confirm("Créer un nouveau commit qui remplace les cinq JSON par cette version historique ?"))return;
      if(window.prompt("Confirmation : écris exactement RESTAURER")!=="RESTAURER")return;
      restore.disabled=true;
      try{
        const result=await cmsAdminRequest("restore",{version_id:p.version_id,expected_head:p.current_head,
          preview_expires:p.preview_expires,preview_signature:p.preview_signature,confirm:"RESTAURER"});
        root.replaceChildren(cmsDom("p","Commit de restauration créé : "+result.github_commit.slice(0,12)+". Déploiement à confirmer."));
        const check=cmsDom("button","Vérifier la mise en ligne","btn btn-secondary");check.type="button";
        check.addEventListener("click",()=>void cmsCheckCommit(result.github_commit,root));
        root.appendChild(check);
      }catch(error){
        root.appendChild(cmsDom("p","Restauration refusée ou échouée : "+error.message));
        restore.disabled=false;
      }
    });
    root.appendChild(restore);
  }catch(error){root.replaceChildren(cmsDom("p","Impossible de prévisualiser : "+error.message));}
}
async function cmsLoadHistory(root){
  root.replaceChildren(cmsDom("p","Chargement de l'historique…"));
  try{
    const data=await cmsAdminRequest("history");
    root.replaceChildren(cmsDom("h3","Historique des publications"));
    if(!(data.versions||[]).length){
      root.appendChild(cmsDom("p","Aucune version enregistrée pour le moment. Une première publication créera un historique."));return;
    }
    for(const entry of data.versions){
      const row=cmsDom("div");row.style.cssText="border-bottom:1px solid #444;padding:8px 0";
      row.appendChild(cmsDom("span",new Date(entry.date).toLocaleString("fr-FR")+" — "+entry.github_commit.slice(0,12)+" — "+entry.status+" "));
      const preview=cmsDom("button","Comparer","btn btn-secondary");preview.type="button";
      const status=cmsDom("button","Statut","btn btn-secondary");status.type="button";
      const detail=cmsDom("div");
      preview.addEventListener("click",()=>void cmsShowPreview(entry,detail));
      status.addEventListener("click",()=>void cmsCheckCommit(entry.github_commit,detail));
      row.append(preview,status,detail);root.appendChild(row);
    }
  }catch(error){root.replaceChildren(cmsDom("p","Historique indisponible : "+error.message));}
}
function cmsInstallHistory(){
  if($("cms-history-btn"))return;
  const area=$("btnPublish")?.parentElement;if(!area)return;
  const button=cmsDom("button","Historique / restaurer","btn btn-secondary");
  button.id="cms-history-btn";button.type="button";
  const root=cmsDom("div");root.id="cms-history-root";
  root.style.cssText="width:100%;padding:10px 0";
  button.addEventListener("click",()=>void cmsLoadHistory(root));
  area.append(button,root);
}

// PUBLISH (corrigé headers)
// -----------------------------
async function publishNow() {
  if(publishBusy)return;
  publishBusy=true;
  setBtnDisabled("btnPublish",true);
  let panel=$("cms-publish-result");
  if(!panel){
    panel=cmsDom("div");
    panel.id="cms-publish-result";
    panel.setAttribute("role","status");
    panel.setAttribute("aria-live","polite");
    panel.style.cssText="padding:12px;margin:12px 0;border:1px solid #666;border-radius:10px";
    $("btnPublish").parentElement.appendChild(panel);
  }
  panel.textContent="Prévisualisation de la publication en cours…";
  try{
    const {preview}=await cmsAdminRequest("preflight");
    if(!preview?.has_changes){
      panel.textContent="Aucun changement à publier : les cinq fichiers GitHub sont déjà à jour.";
      return;
    }
    const lines=Object.entries(preview.changes).filter(([,data])=>data.different)
      .map(([path,data])=>path+" : "+data.before+" → "+data.after).join("\n");
    panel.textContent="Modifications proposées :\n"+lines;
    panel.style.whiteSpace="pre-line";
    if(!window.confirm("Publier les modifications suivantes sur le site ?\n\n"+lines)){
      panel.textContent="Publication annulée : aucun commit créé.";
      return;
    }
    let acknowledge_empty, acknowledge_removals;
    if(preview.emptied_files?.length){
      const files=preview.emptied_files.join(", ");
      if(window.prompt("Attention : les fichiers suivants vont être vidés : "+files+
        "\nPour confirmer, tape exactement PUBLIER VIDE")!=="PUBLIER VIDE"){
        panel.textContent="Publication annulée : suppression des contenus non confirmée.";
        return;
      }
      acknowledge_empty="PUBLIER VIDE";
    }
    if(preview.removed_files?.length) {
      const summary=preview.removed_files.map(path=>
        path+" : "+(preview.removed_counts?.[path]||0)+" contenu(s) supprimé(s)").join("\n");
      if(window.prompt("Des contenus existants vont être supprimés :\n"+summary+
        "\nPour confirmer, tape exactement PUBLIER SUPPRESSIONS")!=="PUBLIER SUPPRESSIONS") {
        panel.textContent="Publication annulée : les suppressions n'ont pas été autorisées.";
        return;
      }
      acknowledge_removals="PUBLIER SUPPRESSIONS";
    }
    panel.textContent="Publication préparée : création du commit GitHub…";
    const data=await cmsAdminRequest("publish",{
      expected_head:preview.current_head,
      preflight_expires:preview.preflight_expires,
      preflight_signature:preview.preflight_signature,
      acknowledge_empty,
      acknowledge_removals
    });
    if(data.skipped){
      panel.textContent="Aucun changement à publier : aucun commit créé.";
      return;
    }
    const commit=data?.github_commit;
    if(!commit){panel.textContent="Le serveur n'a pas retourné de commit : mise en ligne non confirmée.";return;}
    panel.textContent="Commit GitHub créé : "+commit.slice(0,12)+". Mise en ligne non confirmée.";
    const check=cmsDom("button","Vérifier le déploiement","btn btn-secondary");
    check.type="button";check.style.marginLeft="10px";
    let pendingTimer=null,attempts=0;
    async function verify(){
      if(pendingTimer!==null){clearTimeout(pendingTimer);pendingTimer=null;}
      const output=cmsDom("span","Vérification du déploiement…");
      panel.replaceChildren(output,check);
      try{
        const value=await cmsAdminRequest("status",{commit});
        const labels={deployed:"Déploiement confirmé",pending:"Déploiement en cours",
          failed:"Déploiement échoué",unknown:"Déploiement non confirmé"};
        output.textContent=(labels[value.deployment]||"Déploiement non confirmé")+" — "+commit.slice(0,12)+
          (value.is_current?" (commit actuel)":" (version antérieure)");
        if(value.workflow_url&&/^https:\/\/github\.com\//.test(value.workflow_url)){
          const url=cmsDom("a"," — Détails GitHub");url.href=value.workflow_url;
          url.rel="noopener noreferrer";url.target="_blank";output.appendChild(url);
        }
        if(value.deployment==="pending"&&attempts++<12)
          pendingTimer=setTimeout(()=>void verify(),12000);
      }catch(error){output.textContent="Vérification indisponible : "+error.message;}
    }
    check.addEventListener("click",()=>void verify());
    panel.appendChild(check);
    void verify();
    const history=$("cms-history-root");
    if(history?.childElementCount)void cmsLoadHistory(history);
  }catch(error){
    panel.textContent="Erreur de publication (vérifier l'historique avant de réessayer) : "+error.message;
  }finally{
    publishBusy=false;
    setBtnDisabled("btnPublish",false);
  }
}

// -----------------------------
// LOGIN FLOW
// -----------------------------
async function afterLogin() {
  if (!(await isAdmin())) {
    await sb.auth.signOut();
    setLoginMsg("Compte non admin.");
    return;
  }

  const values=await Promise.all(["read","cms","push","media","vip","users"].map(async permission=>{
    try{
      const {data,error}=await sb.rpc("admin_can",{p_permission:permission});
      return [permission,!error&&data===true];
    }catch{return [permission,false];}
  }));
  adminPermissions=Object.fromEntries(values);
  if(!adminPermissions.read){
    await sb.auth.signOut();
    setLoginMsg("Droits de lecture refusés.");
    return;
  }
  for(const item of document.querySelectorAll(".nav-item.tab[data-tab], .admin-mobile-nav .tab[data-tab]")){
    const permission=tabPermission[item.dataset.tab];
    item.hidden=!!permission&&!adminPermissions[permission];
  }
  $("loginCard").style.display = "none";
  $("app").style.display = "block";
  if(adminPermissions.cms)cmsInstallHistory();
  if(adminPermissions.users||adminPermissions.cms||adminPermissions.push)
    await initAdminMfaControl(sb, $("btnLogout")?.parentElement);

  const user = (await sb.auth.getUser()).data.user;
  $("who").textContent = user?.email || user?.id || "";

  // Only load the selected screen, and preserve deep links on reload.
  const route=location.hash.slice(1);
  await showTab(TAB_NAMES.includes(route)?route:"overview");
}

// -----------------------------
// EVENTS
// -----------------------------
tabs().forEach(btn => btn.addEventListener("click", () => void showTab(btn.dataset.tab)));
window.addEventListener("hashchange",()=>{if($("app").style.display!=="none")void showTab(location.hash.slice(1))});

$("loginForm").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("btnLogin").disabled) return;
  $("btnLogin").disabled=true;
  setLoginMsg("Connexion...");
  const email = $("email").value.trim();
  const password = $("password").value;

  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) { setLoginMsg(error.message); $("btnLogin").disabled=false; return; }

  setLoginMsg("");
  try { await afterLogin(); }
  finally { $("btnLogin").disabled=false; }
});

$("btnLogout").addEventListener("click", async () => {
  await sb.auth.signOut();
  location.reload();
});

$("btnPublish").addEventListener("click", publishNow);

(async () => {
  const session = (await sb.auth.getSession()).data.session;
  if (session) await afterLogin();
})();