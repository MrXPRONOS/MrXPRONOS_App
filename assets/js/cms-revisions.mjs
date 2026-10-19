// Historic CMS snapshots. Selecting a revision only fills the form;
// an administrator must explicitly save it and then publish the site.
export function mountCmsRevisionPanel({sb,table,container,onChoose}){
  const allowed=new Set(["cms_articles","cms_conseils","cms_infos","cms_bonus","cms_bookmakers"]);
  if(!allowed.has(table))throw Error("Type de contenu invalide");
  const card=document.createElement("section"),title=document.createElement("h4"),hint=document.createElement("p"),
    status=document.createElement("p"),list=document.createElement("div");
  card.className="mx-block-card";card.hidden=true;
  title.textContent="Versions de ce contenu";
  hint.textContent="Choisir une version remplit le formulaire. Il faudra ensuite enregistrer, puis publier.";
  status.setAttribute("role","status");
  card.append(title,hint,status,list);container.appendChild(card);
  let versionLoad=0;
  async function load(documentId){
    const generation=++versionLoad;
    if(!/^[0-9a-f-]{36}$/i.test(String(documentId||""))) {card.hidden=true;return;}
    card.hidden=false;list.replaceChildren();status.textContent="Chargement de l'historique…";
    const {data,error}=await sb.from("cms_revisions").select(
      "id,operation,created_at,snapshot,actor_user_id"
    ).eq("document_table",table).eq("document_id",documentId)
      .order("created_at",{ascending:false}).limit(25);
    if(generation!==versionLoad)return;
    if(error){status.textContent="Historique indisponible : "+error.message;return;}
    status.textContent=(data||[]).length+" version(s) enregistrée(s)";
    for(const row of (data||[])){
      const button=document.createElement("button");button.type="button";
      button.className="mx-revision-choice";
      const label=[new Date(row.created_at).toLocaleString("fr-FR"),row.operation,
        String(row.snapshot?.title||row.snapshot?.slug||row.snapshot?.name||"Version")].join(" — ");
      button.textContent=label;
      button.addEventListener("click",()=>{
        if(!window.confirm("Recharger cette ancienne version dans le formulaire, sans enregistrer ni publier ?"))return;
        const record={...row.snapshot,id:documentId};
        onChoose?.(record);status.textContent="Version chargée dans le formulaire. Enregistre pour la conserver.";
      });
      list.appendChild(button);
    }
  }
  return {load,clear(){versionLoad++;card.hidden=true;list.replaceChildren();}};
}
