// Full-archive CMS search. Queries are executed inside a privileged-function-free
// SECURITY INVOKER RPC that still honors Supabase RLS.
export function mountCmsServerSearch({sb,root,kind,onChoose}){
 if(!sb||!root||typeof onChoose!=="function")return null;
 const host=document.createElement("section");
 host.className="card admin-cms-server-search";
 const heading=document.createElement("h4");heading.textContent="Rechercher dans toute l'archive";
 const input=document.createElement("input");input.type="search";
 input.placeholder="Titre, slug, bookmaker ou catégorie";input.setAttribute("aria-label","Recherche CMS serveur");
 const button=document.createElement("button");button.type="button";button.className="btn btn-secondary";button.textContent="Rechercher";
 const status=document.createElement("p");status.className="muted";status.setAttribute("role","status");
 const list=document.createElement("div");
 const more=document.createElement("button");more.type="button";more.className="btn btn-secondary";
 more.textContent="Afficher 50 résultats supplémentaires";more.hidden=true;
 host.append(heading,input,button,status,list,more);
 root.prepend(host);
 let page=0,busy=false,hasMore=false,search="";
 async function load(reset=false){
  if(busy)return;
  if(reset){page=0;list.replaceChildren();search=input.value.trim();}
  busy=true;button.disabled=true;more.disabled=true;status.textContent="Recherche serveur…";
  try{
   const {data,error}=await sb.rpc("admin_cms_search",{
    p_kind:kind,p_query:search,p_page:page,p_size:50
   });
   if(error)throw error;
   for(const row of data?.items||[]){
    const btn=document.createElement("button");btn.type="button";
    btn.className="btn btn-secondary admin-cms-server-row";
    btn.textContent=String(row.title||row.name||row.slug||row.bookmaker||row.id)+" · "+
      String(row.status||"Brouillon");
    btn.addEventListener("click",()=>{onChoose(row);status.textContent="Contenu chargé dans le formulaire."});
    list.append(btn);
   }
   hasMore=!!data?.has_more;
   status.textContent=(data?.total||0)+" résultat(s) disponibles · page "+(page+1);
   page++;
  }catch(e){status.textContent="Recherche impossible : "+String(e?.message||e);}
  finally{busy=false;button.disabled=false;more.disabled=false;more.hidden=!hasMore;}
 }
 button.addEventListener("click",()=>void load(true));
 input.addEventListener("keydown",event=>{
  if(event.key==="Enter"){event.preventDefault();void load(true);}
 });
 more.addEventListener("click",()=>void load(false));
 return {search:load,root:host};
}
