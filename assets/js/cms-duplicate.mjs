// Partie 2B — Dupliquer un contenu en brouillon, sans identifiant ni métadonnées de publication.
// Fonction pure pour pouvoir tester les cinq catégories indépendamment de Supabase.
const FIELDS = Object.freeze({
  articles: ["slug","title","content","image_url","og_image","meta_description","category","tags"],
  conseils: ["slug","title","content","image_url","category","difficulty","tags"],
  infos: ["title","content","image_url","category"],
  bonus: ["bookmaker","title","description","image_url","link","footer"],
  bookmakers: ["name","logo","url","description"]
});
function slugBase(value) {
  return String(value||"copie").normalize("NFKD").replace(/[\u0300-\u036f]/g,"")
    .toLowerCase().replace(/[^a-z0-9-]+/g,"-").replace(/-+/g,"-").replace(/^-|-$/g,"").slice(0,72)||"copie";
}
export function createCmsDraftCopy(kind,original,existingRows=[]) {
  const fields=FIELDS[kind];
  if(!fields||!original||typeof original!=="object")throw Error("Contenu à dupliquer invalide");
  const draft={};
  for(const field of fields)if(original[field]!==undefined&&original[field]!==null){
    draft[field]=Array.isArray(original[field])?[...original[field]]:original[field];
  }
  if(kind==="bookmakers")draft.name=String(original.name||"Partenaire").trim()+" (copie)";
  else draft.title=String(original.title||"Sans titre").trim()+" (copie)";
  if(fields.includes("slug")){
    const existing=new Set(existingRows.map(r=>String(r?.slug||"").toLowerCase()));
    const root=slugBase(original.slug||original.title)+"-copie";
    let candidate=root,n=2;
    while(existing.has(candidate)){candidate=root+"-"+n++;if(n>10000)throw Error("Impossible de choisir un slug unique");}
    draft.slug=candidate;
  }
  draft.status="draft";
  draft.active=false;
  // Never copy id, timestamps, audit fields, or a publication/scheduling date.
  return draft;
}
