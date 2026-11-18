// Display-only carousel metadata; titles are illustrative, never linked to Telegram availability.
const IMAGE=/^https:\/\/(?:image\.tmdb\.org\/t\/p\/w342\/[A-Za-z0-9_-]{8,100}\.(?:jpe?g|png|webp)|static\.tvmaze\.com\/uploads\/images\/(?:medium_portrait|original_untouched)\/[0-9]+\/[0-9]+\.jpg|(?:m\.media-amazon\.com|images-na\.ssl-images-amazon\.com)\/images\/[A-Za-z0-9_%@.+/-]{8,800})$/;
const SOURCE=/^https:\/\/(?:www\.themoviedb\.org\/(?:movie|tv)\/[0-9]+|www\.imdb\.com\/title\/tt[0-9]{6,11}\/?|www\.tvmaze\.com\/shows\/[0-9]+\/[A-Za-z0-9_-]+)$/;
const KINDS=new Set(['films','series','animes']);
const URL='https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/poster_showcase.json';
let cache={at:0,data:null};
export function sanitizeShowcase(raw){
 const rows=Array.isArray(raw?.items)?raw.items:[];
 const seen=new Set();
 const items=[];
 for(const r of rows){
  if(!r||typeof r!=='object'||!KINDS.has(r.type)||typeof r.title!=='string'||!IMAGE.test(r.poster)||!SOURCE.test(r.tmdb))continue;
  if(seen.has(r.poster))continue;
  seen.add(r.poster);
  items.push({title:r.title.slice(0,95),type:r.type,poster:r.poster,tmdb:r.tmdb});
  if(items.length>=30)break;
 }
 return {items,source:['TMDB','SampleAPIs + TVmaze'].includes(raw?.source)?raw.source:'Affiches',notice:'Affiches illustratives — leur présence ne garantit pas la disponibilité des films ou séries dans les canaux Telegram.'};
}
export async function showcaseData(){
 if(cache.data&&Date.now()-cache.at<(cache.data.items.length?1800000:45000))return cache.data;
 try{
  const r=await fetch(URL,{signal:AbortSignal.timeout(5500),headers:{accept:'application/json'},cf:{cacheEverything:true,cacheTtl:1800}});
  if(!r.ok)throw Error('unavailable');
  const raw=await r.json();
  cache={at:Date.now(),data:sanitizeShowcase(raw)};
  return cache.data;
 }catch{
  return {items:[],source:'TMDB',notice:'Visuels en cours de synchronisation.'};
 }
}
export async function serveShowcase(request){
 if(request.method!=='GET')return Response.json({error:'Méthode non disponible'},{status:405});
 return Response.json(await showcaseData(),{headers:{'cache-control':'public, max-age=300','x-content-type-options':'nosniff'}});
}
