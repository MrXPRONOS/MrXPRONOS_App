// Durable admin incident register; Supabase RLS limits every operation to admins.
const advice={
 "pronostics":"Vérifier la fraîcheur de data.json, puis les dernières exécutions GitHub Actions.",
 "telegram":"Contrôler les journaux d'envoi et la dernière réponse Telegram avant de relancer.",
 "push":"Contrôler les campagnes dans l'historique Push ; ne pas renvoyer sans vérifier l'idempotence.",
 "cms":"Vérifier l'historique GitHub et le déploiement avant de republier.",
 "cron":"Comparer le dernier déclenchement aux horaires programmés.",
 "site":"Vérifier les journaux GitHub Pages et l'état du service worker."
};
const statusNames={open:"Ouvert",acknowledged:"Pris en charge",resolved:"Résolu"};
export async function mountIncidentCenter(sb,root){
 if(!root||!sb)return;
 root.replaceChildren();
 const panel=document.createElement("section");panel.className="card";
 panel.innerHTML=`<div class="admin-section-heading"><h3>Centre d'incidents</h3>
  <button id="incident-refresh" class="btn btn-secondary" type="button">Actualiser</button></div>
 <div class="admin-filter-row">
  <div><label for="incident-source">Service</label><select id="incident-source">
   <option value="pronostics">Pronostics</option><option value="telegram">Telegram</option>
   <option value="push">Push</option><option value="cms">CMS</option>
   <option value="cron">Automatisations</option><option value="site">Site</option>
  </select></div>
  <div><label for="incident-severity">Gravité</label><select id="incident-severity">
   <option value="low">Faible</option><option value="medium" selected>Modérée</option>
   <option value="high">Élevée</option></select></div>
  <div><label for="incident-filter">État</label><select id="incident-filter">
   <option value="all">Tous</option><option value="open">Ouverts</option>
   <option value="acknowledged">Pris en charge</option><option value="resolved">Résolus</option>
  </select></div>
 </div>
 <label for="incident-summary">Description de l'incident</label>
 <input id="incident-summary" maxlength="500" placeholder="Exemple : données des pronostics absentes">
 <p id="incident-advice" class="muted"></p>
 <button type="button" id="incident-create" class="btn btn-primary">Créer un incident</button>
 <p id="incident-status" class="muted" role="status" aria-live="polite"></p>
 <div class="admin-pronostics-table-scroll"><table id="incident-table">
 <thead><tr><th>Service</th><th>Incident</th><th>État</th><th>Créé</th><th>Action</th></tr></thead>
 <tbody></tbody></table></div>
 <button id="incident-more" type="button" class="btn btn-secondary" hidden>Charger les incidents suivants</button>`;
 root.append(panel);
 const $=id=>panel.querySelector("#"+id);
 const notice=(s)=>{$("incident-status").textContent=s;};
 const updateAdvice=()=>{$("incident-advice").textContent="Action conseillée : "+(advice[$("incident-source").value]||"Examiner les journaux.");};
 $("incident-source").addEventListener("change",updateAdvice);updateAdvice();
 let rows=[],offset=0,more=false,busy=false;
 const audit=async(action,details)=>{
  try{
   const {data:{user}}=await sb.auth.getUser();
   await sb.from("audit_log").insert({action,actor_user_id:user?.id||null,details});
  }catch{}
 };
 const load=async(reset=false)=>{
  if(busy)return;
  if(reset){offset=0;rows=[];}
  busy=true;$("incident-more").disabled=true;notice("Chargement…");
  try{
   const {data,error}=await sb.from("admin_incidents")
     .select("id,source,summary,severity,status,created_at,last_seen_at,detail,escalation_level,escalated_at")
     .order("created_at",{ascending:false}).range(offset,offset+99);
   if(error)throw error;
   rows.push(...data||[]);offset+=(data||[]).length;more=(data||[]).length===100;
   render();notice(rows.length+" incident(s) chargé(s).");
  }catch(e){notice("Lecture impossible : "+String(e?.message||e));}
  finally{busy=false;$("incident-more").hidden=!more;$("incident-more").disabled=false;}
 };
 const render=()=>{
  const tbody=$("incident-table").querySelector("tbody");tbody.replaceChildren();
  const filter=$("incident-filter").value;
  for(const row of rows.filter(x=>filter==="all"||x.status===filter)){
   const tr=document.createElement("tr");
   for(const content of [row.source,row.summary,
     (statusNames[row.status]||row.status)+(row.escalation_level>0?" · Escaladé":""),
     row.created_at?new Date(row.created_at).toLocaleString("fr-FR"):"—"]){
    const td=document.createElement("td");td.textContent=String(content);tr.append(td);
   }
   if(row.detail?.action){
    const details=document.createElement("details");
    const summary=document.createElement("summary");summary.textContent="Diagnostic";
    const advice=document.createElement("p");advice.textContent=String(row.detail.action);
    const observed=document.createElement("small");
    observed.textContent=row.last_seen_at?
      "Dernière observation : "+new Date(row.last_seen_at).toLocaleString("fr-FR"):"";
    details.append(summary,advice,observed);
    tr.children[1].append(details);
   }
   const action=document.createElement("td");
   if(row.status!=="resolved"){
    const next=row.status==="open"?"acknowledged":"resolved";
    const button=document.createElement("button");button.className="btn btn-secondary";button.type="button";
    button.textContent=next==="acknowledged"?"Prendre en charge":"Marquer résolu";
    button.addEventListener("click",async()=>{
     button.disabled=true;
     try{
      const {data:{user}}=await sb.auth.getUser();
      const {data,error}=await sb.from("admin_incidents").update({
       status:next,updated_at:new Date().toISOString(),
       ...(next==="acknowledged"?{acknowledged_by:user?.id||null}:{resolved_at:new Date().toISOString()})
      }).eq("id",row.id).eq("status",row.status).select("id").maybeSingle();
      if(error||!data)throw Error(error?.message||"Déjà modifié dans un autre onglet.");
      await audit("admin_incident_status",{incident_id:row.id,status:next});
      await load(true);
     }catch(e){notice(String(e?.message||e));button.disabled=false;}
    });action.append(button);
   }
   tr.append(action);tbody.append(tr);
  }
 };
 $("incident-create").addEventListener("click",async()=>{
  const source=$("incident-source").value,summary=$("incident-summary").value.trim();
  if(summary.length<3){notice("Décris l'incident en au moins trois caractères.");return;}
  const btn=$("incident-create");btn.disabled=true;
  try{
   const {error}=await sb.from("admin_incidents").insert({
    source,summary,severity:$("incident-severity").value,status:"open"
   });
   if(error)throw error;
   await audit("admin_incident_created",{source,summary});
   $("incident-summary").value="";await load(true);
  }catch(e){notice("Création impossible : "+String(e?.message||e));}
  finally{btn.disabled=false;}
 });
 $("incident-refresh").addEventListener("click",()=>void load(true));
 $("incident-more").addEventListener("click",()=>void load(false));
 $("incident-filter").addEventListener("change",render);
 await load(true);
}
