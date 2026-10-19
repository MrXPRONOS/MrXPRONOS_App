// CMS editorial organization: safe, accent-insensitive client-side filters.
// Only operates on records that the authorized admin has already loaded.
export const normalizeCmsSearch = value => String(value ?? "").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

export function filterCmsRows(rows,{search="",status="all",category="all",order="recent"}={}) {
  if(!Array.isArray(rows))return [];
  const q=normalizeCmsSearch(search),cat=normalizeCmsSearch(category);
  const filtered=rows.filter(row=>{
    if(!row||typeof row!=="object")return false;
    if(status!=="all" && String(row.status||"draft").toLowerCase()!==status)return false;
    if(cat!=="all"&&normalizeCmsSearch(row.category)!==cat)return false;
    const corpus=[row.title,row.name,row.slug,row.bookmaker,row.description,row.category,
      ...(Array.isArray(row.tags)?row.tags:[])].map(normalizeCmsSearch).join(" ");
    return !q||corpus.includes(q);
  });
  return filtered.map((row,position)=>({row,position})).sort((a,b)=>{
    if(order==="title"){
      const x=normalizeCmsSearch(a.row.title||a.row.name),y=normalizeCmsSearch(b.row.title||b.row.name);
      return x.localeCompare(y,"fr")||a.position-b.position;
    }
    if(order==="oldest"){
      const x=Date.parse(a.row.updated_at||a.row.created_at||"")||0;
      const y=Date.parse(b.row.updated_at||b.row.created_at||"")||0;
      return x-y||a.position-b.position;
    }
    const x=Date.parse(a.row.updated_at||a.row.created_at||"")||0;
    const y=Date.parse(b.row.updated_at||b.row.created_at||"")||0;
    return y-x||a.position-b.position;
  }).map(x=>x.row);
}

// Mount simple, accessible filter controls before an existing CMS list.
// Filtering and ordering never save, delete or publish content.
export function mountCmsListFilters({root,cards,rows,kind="content",showCategory=true}) {
  if(!root||!cards?.length||!Array.isArray(rows))return null;
  const list=cards[0].parentElement;if(!list)return null;
  const byId=new Map(cards.map(card=>[
    card.getAttribute("data-id")||card.getAttribute("data-bonus-id")||card.getAttribute("data-book-id"),card
  ]));
  const element=(tag,label)=>{const el=document.createElement(tag);if(label)el.textContent=label;return el;};
  const toolbar=element("div");toolbar.className="mx-cms-list-filters";
  const search=element("input");search.type="search";search.placeholder="Rechercher par titre, nom ou mot-clé";
  search.setAttribute("aria-label","Rechercher dans les "+kind);
  const status=element("select");status.setAttribute("aria-label","Filtrer le statut");
  for(const [value,label] of [["all","Tous les statuts"],["draft","Brouillons"],["published","Publiés"]]){
    const option=element("option",label);option.value=value;status.append(option);
  }
  const category=element("select");category.setAttribute("aria-label","Filtrer la catégorie");
  const all=element("option","Toutes les catégories");all.value="all";category.append(all);
  for(const value of [...new Set(rows.map(r=>String(r?.category||"").trim()).filter(Boolean))]
    .sort((a,b)=>a.localeCompare(b,"fr"))){
    const option=element("option",value);option.value=value;category.append(option);
  }
  const order=element("select");order.setAttribute("aria-label","Trier les contenus");
  for(const [value,label] of [["recent","Plus récents"],["oldest","Plus anciens"],["title","Titre A–Z"]]){
    const option=element("option",label);option.value=value;order.append(option);
  }
  const counter=element("p");counter.className="muted mx-filter-count";counter.setAttribute("role","status");
  toolbar.append(search,status,...(showCategory&&category.options.length>1?[category]:[]),order,counter);
  list.before(toolbar);
  const apply=()=>{
    const matched=filterCmsRows(rows,{search:search.value,status:status.value,
      category:showCategory?category.value:"all",order:order.value});
    const visible=new Set(matched.map(r=>String(r.id)));
    for(const [id,card] of byId)card.hidden=!visible.has(String(id));
    for(const row of matched){const card=byId.get(String(row.id));if(card)list.appendChild(card);}
    counter.textContent=`${matched.length} / ${rows.length} résultat(s) parmi les ${rows.length} derniers contenus chargés (limite actuelle : 50).`;
  };
  for(const input of [search,status,category,order])input.addEventListener("input",apply);
  apply();
  return {refresh:apply,root:toolbar};
}
