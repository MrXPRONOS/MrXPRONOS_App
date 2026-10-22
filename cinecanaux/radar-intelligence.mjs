// Ciné Radar V3: pure ranking, semantic-like query expansion, and safe metadata extraction.
// No external AI dependency; transparent deterministic scoring with no fabricated information.
const ALIASES={
 film:["film","films","cinema","ciné","movie","long metrage","film complet"],
 series:["serie","series","série","séries","episodes","épisodes","saison"],
 anime:["anime","animé","animes","animés","manga","dessin animé","animation"],
 action:["action","combat","aventure","guerre","arts martiaux"],
 comedie:["comedie","comédie","humour","drôle","rire","funny"],
 romance:["romance","romantique","amour","love","sentimental"],
 horreur:["horreur","epouvante","épouvante","peur","thriller"],
 drame:["drame","dramatique"],
 policier:["policier","police","enquete","enquête","detective"],
 sciencefiction:["sciencefiction","science fiction","sci fi","sf","futuriste"],
 shonen:["shonen","shounen"],seinen:["seinen"],fantasy:["fantasy","fantastique"],
 VF:["vf","francais","français","version francaise","french"],
 VOSTFR:["vostfr","sous titre","sous-titre","subtitles"],
 VO:["vo","version originale"]
};
export function normalize(value){return String(value??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim().replace(/\s+/g," ");}
export function distance(a,b,limit=2){
 if(Math.abs(a.length-b.length)>limit)return limit+1;
 let prev=Array.from({length:b.length+1},(_,i)=>i);
 for(let i=1;i<=a.length;i++){let next=[i];let min=next[0];for(let j=1;j<=b.length;j++){next[j]=Math.min(next[j-1]+1,prev[j]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1));min=Math.min(min,next[j]);}if(min>limit)return limit+1;prev=next;}return prev[b.length];
}
const STOP=new Set(["de","des","du","la","le","les","et","ou","pour","un","une","en","sur","a","au","aux","avec","canal","chaine","chaines","telegram","trouve","recherche"]);
function concepts(text){
 const normalized=normalize(text),found=new Set();
 for(const [key,aliases] of Object.entries(ALIASES))if(aliases.some(a=>(" "+normalized+" ").includes(" "+normalize(a)+" ")))found.add(key);
 return found;
}
export function searchRank(channel,query){
 const q=normalize(query);if(!q)return 1;
 const title=normalize(channel.title),desc=normalize(channel.description),genre=normalize(channel.genre),kind=normalize(channel.content_type),lang=normalize(channel.language);
 const whole=[title,desc,genre,kind,lang].join(" ");
 const words=whole.split(" ").filter(Boolean),found=concepts(q);
 const titleConcepts=concepts(title+" "+genre+" "+kind+" "+lang);
 let score=0,foundToken=0;
 for(const token of q.split(" ").filter(x=>x&&!STOP.has(x)).slice(0,10)){
  let tscore=0;
  if(title.includes(token))tscore=Math.max(tscore,6);
  else if(whole.includes(token))tscore=Math.max(tscore,3);
  if(!tscore&&token.length>=4) {
   for(const w of words){const d=distance(token,w,token.length>7?2:1);if(d<=2&&d<=Math.max(1,Math.floor(token.length/4))){tscore=Math.max(tscore,d===1?2:1);if(tscore===2)break;}}
  }
  if(tscore)foundToken++;
  score+=tscore;
 }
 for(const x of found)if(titleConcepts.has(x))score+=5;
 if(!foundToken&&!found.size)return 0;
 if(found.size&&!score)return 0;
 return score+(title===q?14:0);
}
export function qualityScore(channel,now=Date.now()){
 const fav=Math.min(100,Number(channel.favorites_count)||0),opens=Math.min(500,Number(channel.opens)||0);
 const health=channel.check_status==="reachable"?16:channel.check_status==="not_found"?-25:0;
 const time=Date.parse(String(channel.last_post_at||channel.updated_at||"").replace(" ","T").replace(/Z?$/,"Z"));
 const age=Number.isFinite(time)?Math.max(0,(now-time)/86400000):365;
 const freshness=age<=2?20:age<=7?14:age<=30?8:age<=90?3:0;
 const metadata=(channel.description?.length>=30?5:0)+(channel.language?2:0)+(channel.banner_url?3:0);
 return Math.round(freshness+health+Math.log2(1+fav)*7+Math.log2(1+opens)*2+metadata);
}
export function personalizedScore(channel,{category="films",language="tous",genreWeights={},favoriteIds=[]}={}){
 const baseline=qualityScore(channel);
 let score=baseline;
 if(channel.content_type===category)score+=23;
 if(language==="tous"||channel.language===language)score+=9;
 score+=(genreWeights[channel.genre]||0)*12;
 if(favoriteIds.includes(Number(channel.id)))score-=50;
 return score;
}
export function recommendations(channels,favorites,preferences={},limit=20){
 const map={};
 for(const fav of favorites){if(fav?.genre)map[fav.genre]=(map[fav.genre]||0)+1;}
 const favoriteIds=favorites.map(x=>Number(x.id));
 return channels.map(x=>({...x,_recommendation_score:personalizedScore(x,{...preferences,genreWeights:map,favoriteIds})}))
  .sort((a,b)=>b._recommendation_score-a._recommendation_score||Number(a.id)-Number(b.id)).slice(0,limit);
}
// Telegram public preview is HTML and may be unavailable: missing or invalid timestamps => unknown.
export function extractTelegramActivity(html,now=Date.now()){
 if(!html||typeof html!=="string")return {status:"unverifiable",lastPost:null};
 const matches=[...html.matchAll(/<time[^>]{0,320}datetime=["']([0-9TZ:+.-]+)["']/gi)].map(x=>x[1]).slice(0,150);
 const timestamps=matches.map(x=>Date.parse(x)).filter(t=>Number.isFinite(t)&&t<=now+86400000&&t>now-10*365*86400000);
 if(!timestamps.length)return {status:"unverifiable",lastPost:null};
 return {status:"reachable",lastPost:new Date(Math.max(...timestamps)).toISOString()};
}
export function categorizeCandidate(title,originalCategory){
 const t=normalize(title);
 // Preserve explicit source category. Do not infer a genre from generic terms.
 if(originalCategory==="anime")return {content_type:"animes",genre:"general"};
 if(originalCategory==="series")return {content_type:"series",genre:"general"};
 if(originalCategory==="comedie")return {content_type:"films",genre:"comedie"};
 if(originalCategory==="desir")return {content_type:"films",genre:"romance"};
 if(/\bserie(s)?\b|\bseason\b|\bsaison\b/.test(t)&&!/\bfilm(s)?\b/.test(t))return {content_type:"series",genre:"general"};
 if(/\banime(s)?\b|\bmanga(s)?\b|\bdessin anime\b/.test(t)&&!/\bfilm(s)?\b/.test(t))return {content_type:"animes",genre:"general"};
 for(const genre of ["action","comedie","romance","horreur","drame","policier","sciencefiction"]){
  if((ALIASES[genre]||[]).some(alias=>(" "+t+" ").includes(" "+normalize(alias)+" ")))return {content_type:"films",genre};
 }
 return {content_type:"films",genre:"general"};
}
export function notificationEligible(user,channel,favoriteGenres=[]){
 return Number(user.notification_enabled)===1 &&
  (user.category===channel.content_type||(favoriteGenres||[]).includes(channel.genre)) &&
  (user.language==="tous"||user.language===channel.language);
}
