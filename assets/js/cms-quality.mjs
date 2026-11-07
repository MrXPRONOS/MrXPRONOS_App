// Deterministic editorial QA. It never modifies a record.
const clean=value=>String(value??"").trim();
export function inspectCmsEditorial(kind,row,existing=[]){
 const errors=[],warnings=[];
 if(!row||typeof row!=="object")return {errors:["Enregistrement invalide"],warnings};
 const title=clean(row.title||row.name||row.bookmaker);
 const status=clean(row.status||"draft");
 const published=status==="published";
 const content=clean(row.content);
 if(!title)errors.push("Titre ou nom obligatoire.");
 if(kind==="articles"||kind==="conseils"){
  const slug=clean(row.slug);
  if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))errors.push("Slug invalide (lettres, chiffres, tirets).");
  if((existing||[]).some(e=>e&&e.id!==row.id&&clean(e.slug)===slug))
   errors.push("Ce slug existe déjà.");
 }
 for(const key of ["image_url","og_image","website","url","affiliate_url"]){
  const value=clean(row[key]);if(!value)continue;
  try{
   const url=new URL(value,"https://mrxpronos.github.io/MrXPRONOS_App/");
   if(!["https:","http:"].includes(url.protocol))errors.push("Lien non autorisé : "+key);
  }catch{errors.push("URL invalide : "+key);}
 }
 // Public pages must never reference expiring private Storage preview links.
 const rich=JSON.stringify(row);
 if(/\/storage\/v1\/object\/sign\/cms-drafts\//.test(rich)||
    /\/storage\/v1\/object\/public\/cms-drafts\//.test(rich))
  errors.push("Publie les médias privés avant d'utiliser leurs liens dans un contenu.");
 if(published){
  if(["articles","conseils","infos"].includes(kind)&&!content)
   errors.push("Le contenu publié est vide.");
  if(kind==="articles"&&!clean(row.meta_description))
   warnings.push("Description SEO absente.");
  if(kind==="articles"&&!clean(row.image_url))
   warnings.push("Image de couverture absente.");
  if(content&&/!\[\]\(/.test(content))
   warnings.push("Une image du contenu n'a pas de description alternative.");
  if(content&&/https?:\/\/[\w.-]+\s/.test(content))
   warnings.push("Vérifier les liens dans le contenu.");
 }
 return {errors,warnings};
}
