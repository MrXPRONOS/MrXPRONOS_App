const humanStatus={0:"Non exécutée",1:"Réussie",2:"DNS en échec",3:"Connexion échouée",
 4:"HTTP en échec",5:"Délai dépassé",6:"Réponse trop volumineuse",7:"URL invalide",8:"Erreur interne",9:"Échec inconnu"};
function fingerprint(job){
 const schedule=job.schedule||{};
 return [job.endpoint||"",schedule.timezone||"UTC",
  ...["hours","minutes","wdays"].map(k=>JSON.stringify(schedule[k]||[]))].join("|");
}
export function detectCronDuplicateConfigs(jobs){
 const seen=new Map(),duplicateGroups=[];
 for(const job of jobs.filter(x=>x.enabled)){
  const k=fingerprint(job);
  if(!seen.has(k))seen.set(k,[]);
  seen.get(k).push(job);
 }
 for(const group of seen.values())if(group.length>1)
  duplicateGroups.push({jobs:group.map(j=>({id:j.id,title:j.title})),
    endpoint:group[0].endpoint});
 return duplicateGroups;
}
export async function readCronJobs(sb,{supabaseUrl,anonKey,operation="jobs",jobId}={}){
 const {data:{session}}=await sb.auth.getSession();
 if(!session?.access_token)throw Error("Session administrateur expirée");
 const result=await fetch(supabaseUrl+"/functions/v1/admin-cron-read",{
  method:"POST",headers:{"Authorization":"Bearer "+session.access_token,
   apikey:anonKey,"Content-Type":"application/json"},
  body:JSON.stringify(operation==="history"?{operation,job_id:jobId}:{operation})
 });
 const json=await result.json().catch(()=>({}));
 if(!result.ok)throw Error(json.error||"Erreur cron-job.org HTTP "+result.status);
 return json;
}
export function mountCronJobRegister(sb,root,config){
 if(!root)return null;
 root.replaceChildren();
 const panel=document.createElement("section");panel.className="card";
 const head=document.createElement("div");head.className="admin-section-heading";
 const title=document.createElement("h3");title.textContent="cron-job.org";
 const button=document.createElement("button");button.type="button";
 button.className="btn btn-secondary";button.textContent="Actualiser";
 head.append(title,button);
 const info=document.createElement("p");info.className="muted";info.setAttribute("role","status");
 const table=document.createElement("table");const rows=document.createElement("tbody");
 table.innerHTML="<thead><tr><th>Tâche</th><th>Dernière exécution</th><th>Prochaine</th><th>État</th><th>Historique</th></tr></thead>";
 table.append(rows);
 const caption=document.createElement("p");caption.className="muted";
 panel.append(head,info,table,caption);root.append(panel);
 const stamp=sec=>sec>0?new Date(sec*1000).toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"}):"—";
 const load=async()=>{
  info.textContent="Lecture du registre…";button.disabled=true;
  try{
   const res=await readCronJobs(sb,config);
   rows.replaceChildren();
   if(!res.configured){
    info.textContent="Connexion non configurée : ajouter CRON_JOB_ORG_API_KEY aux secrets Supabase Edge.";
    caption.textContent="Aucune tâche cron-job.org n'a été vérifiée.";return;
   }
   const jobs=res.jobs||[];
   for(const job of jobs){
    const tr=document.createElement("tr");
    for(const value of [job.title,stamp(job.last_execution),stamp(job.next_execution),
     job.enabled?(humanStatus[job.last_status]||"Inconnu"):"Désactivée"]){
      const td=document.createElement("td");td.textContent=value;tr.append(td);
    }
    const td=document.createElement("td"),more=document.createElement("button");
    more.type="button";more.className="btn btn-secondary";more.textContent="Détails";
    more.addEventListener("click",async()=>{
     more.disabled=true;
     try{
      const history=await readCronJobs(sb,{...config,operation:"history",jobId:job.id});
      const dialog=document.createElement("details");dialog.open=true;
      const label=document.createElement("summary");label.textContent=job.title;
      const historyList=document.createElement("ul");
      for(const item of history.history||[]){
       const li=document.createElement("li");
       li.textContent=stamp(item.executed)+" · "+item.status+
         (item.http_status?" · HTTP "+item.http_status:"");
       historyList.append(li);
      }
      dialog.append(label,historyList);td.replaceChildren(dialog);
     }catch(err){info.textContent="Historique indisponible : "+err.message;}
     finally{more.disabled=false;}
    });
    td.append(more);tr.append(td);rows.append(tr);
   }
   const duplicates=detectCronDuplicateConfigs(jobs);
   info.textContent=jobs.length+" tâche(s) connues · "+jobs.filter(x=>x.enabled).length+
     " actives · "+(res.fetched_at?new Date(res.fetched_at).toLocaleString("fr-FR"):"Date inconnue");
   caption.textContent=(duplicates.length?duplicates.length+
     " configuration(s) identiques possibles : "+duplicates.map(x=>x.jobs.map(y=>y.title).join(" / ")).join("; "):
      "Aucune configuration identique détectée.")+
      (res.stale?" · Registre en cache (API indisponible).":"");
   if(res.partial)caption.textContent+=" · Liste partielle signalée par cron-job.org.";
  }catch(e){info.textContent="cron-job.org indisponible : "+String(e?.message||e);}
  finally{button.disabled=false;}
 };
 button.addEventListener("click",()=>void load());
 void load();
 return {reload:load};
}
