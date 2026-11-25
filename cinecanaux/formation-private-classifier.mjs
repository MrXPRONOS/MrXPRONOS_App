// A single private Formation stock feeds five independent destinations.
// Classification is conservative: one explicit category wins; otherwise one
// unambiguous domain from the title or an exact same-course cover in this
// PRIVATE chat. Never guess "general" from a missing/ambiguous category.
export const FORMATION_CATEGORIES=Object.freeze([
 'formation_general','formation_business','formation_finance',
 'formation_digitale','formation_mindset'
]);
const ALIASES=new Map([
 ['general','formation_general'],['generale','formation_general'],
 ['generales','formation_general'],['général','formation_general'],
 ['business','formation_business'],['entrepreneuriat','formation_business'],
 ['business et commerce electronique','formation_business'],
 ['commerce electronique','formation_business'],['marketing','formation_business'],
 ['finance','formation_finance'],['finances','formation_finance'],
 ['digital','formation_digitale'],['digitale','formation_digitale'],
 ['numerique','formation_digitale'],['informatique','formation_digitale'],
 ['mindset','formation_mindset'],['mental','formation_mindset'],
 ['developpement personnel','formation_mindset']
]);
const WORDS={
 formation_business:['entrepreneuriat','entreprise','business','marketing',
  'ecommerce','commerce','vente','dropshipping','affiliation',
  'tiktok','reseaux sociaux','gestion de projet','startup','start up'],
 formation_finance:['finance','finances','trading','crypto','bitcoin','bourse',
  'investissement','forex','immobilier','blockchain'],
 formation_digitale:['informatique','programmation','python','javascript',
  'intelligence artificielle','chatgpt','developpement web','montage video',
  'graphisme','automatisation','excel','digital','numerique',
  'data science','power bi','wordpress','docker','cisco','cybersecurite',
  'cybercriminalite','reseaux informatiques','prompt engineering',
  'illustration 3d','copilot','hacking ethique'],
 formation_mindset:['mindset','leadership','developpement personnel',
  'productivite','psychologie','discipline','communication','motivation']
};
const norm=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
 .toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
const coursePattern=/^\s*(?:cours|course)\s*:\s*([a-z][a-z0-9_-]{3,80})\s*$/im;
const categoryLine=/^\s*(?:cat[eé]gorie|category|domaine|rubrique)\s*:\s*([^\r\n]{1,60})\s*$/gim;
const heading=/^\s*(?:titre|title|cours|course)\s*:\s*(.{3,180})\s*$/gim;
export function courseId(caption){
 return coursePattern.exec(String(caption||''))?.[1]?.toLowerCase()||null;
}
export function classifyFormationPost(caption,filename='',knownPosters=[]){
 const text=String(caption||'').slice(0,1200);
 const id=courseId(text);
 const labels=[...text.matchAll(categoryLine)];
 if(labels.length){
  const matched=labels.map(x=>ALIASES.get(norm(x[1])));
  if(matched.some(x=>!x)||new Set(matched).size!==1)
   return {category:null,reason:'explicit_category_invalid_or_conflicting',course_id:id};
  return {category:matched[0],reason:'explicit',course_id:id};
 }
 if(id){
  const matches=new Set();
  for(const poster of knownPosters||[]){
   if(courseId(poster?.caption)!==id)continue;
   if(!FORMATION_CATEGORIES.includes(poster.category))continue;
   matches.add(poster.category);
  }
  if(matches.size===1)
   return {category:[...matches][0],reason:'matching_course_cover',course_id:id};
  if(matches.size>1)
   return {category:null,reason:'conflicting_course_covers',course_id:id};
 }
 const headings=[...text.matchAll(heading)].map(x=>x[1]);
 // Only the course ID/title and filename are considered, never author names,
 // arbitrary advertising captions or contact information.
 const evidence=norm(headings.join(' ')+' '+String(filename||'').slice(0,250));
 const hits=Object.entries(WORDS).filter(([_,ws])=>
  ws.some(w=>(' '+evidence+' ').includes(' '+w+' '))).map(([k])=>k);
 return hits.length===1?
  {category:hits[0],reason:'unambiguous_title',course_id:id}:
  {category:null,reason:hits.length?'ambiguous_training_domain':
   'training_category_unknown',course_id:id};
}
