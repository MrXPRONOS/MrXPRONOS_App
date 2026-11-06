import {
  normalizeName,localDay,nextDay,isFinished,eligible,matchDay,displayConfidence,
  resultState,favoriteMatch,normalizeFavorites,toggleFavorite,upcoming,
  settled,performance,makeSnapshot,changesSince,validNews,newsForFavorites,
  todayTip,reminderICS,MAX_FAVORITES
} from "./daily-utils.mjs";

const $ = id => document.getElementById(id);
const STORAGE = {
  favorites:"mx_daily_favorites_v1",
  baseline:"mx_daily_snapshot_v1",
  session:"mx_daily_session_snapshot_v1",
  filter:"mx_daily_filter_v1",
  reminderTime:"mx_daily_reminder_time_v1"
};
const state = {
  matches:[], news:[], exact:null, favorites: {teams:[],leagues:[]},
  filter:"all", diff:null, sourceOK:{data:false,news:false,exact:false},
  loading:false, generatedAt:null, previousWhen:null
};
const fmtTime = value => {
  const d=new Date(value);
  return Number.isFinite(d.getTime())
    ? d.toLocaleString("fr-FR",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"})
    : "Date indisponible";
};
const formatDay = value => {
  const d=new Date(value);
  return Number.isFinite(d.getTime())
    ? d.toLocaleDateString("fr-FR",{weekday:"long",day:"numeric",month:"long",year:"numeric"})
    : "—";
};
const limitText=(value,max=140)=>String(value ?? "").trim().slice(0,max);
const number = n => Number(n||0).toLocaleString("fr-FR");
function node(tag,className,text){
  const e=document.createElement(tag);
  if (className) e.className=className;
  if (text!==undefined) e.textContent=String(text);
  return e;
}
function safeRead(key){
  try{return JSON.parse(localStorage.getItem(key)||"null");}
  catch{return null;}
}
function safeWrite(key,value){
  try{localStorage.setItem(key,JSON.stringify(value));return true;}
  catch{return false;}
}
function setChildren(target,children){
  target.replaceChildren(...children);
}
function statusMessage(target,text){
  const e=$(target);
  if(e)e.textContent=text;
}
function empty(text){
  return node("p","mx-daily-muted",text);
}
function showError(text){
  const e=$("daily-error");
  e.textContent=text||"";
  e.hidden=!text;
}
function normalizeData(raw) {
  return Array.isArray(raw?.matches) ? raw.matches.filter(m=>m && typeof m==="object") : [];
}
async function publicJSON(name){
  const url=new URL(name,location.href);
  try{
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),8500);
    try{
      const r=await fetch(url.href,{cache:"no-store",signal:controller.signal});
      if(!r.ok)throw Error("HTTP "+r.status);
      return {value:await r.json(),source:"network"};
    }finally{clearTimeout(timer);}
  }catch{
    if(typeof caches!=="undefined"){
      try{
        const cached=await caches.match(url.href);
        if(cached?.ok)return{value:await cached.json(),source:"cache"};
      }catch{}
    }
    return {value:null,source:"unavailable"};
  }
}
function renderSummary(){
  const now=new Date();
  const today=localDay(now);
  $("daily-date").textContent=formatDay(now);
  const total=upcoming(state.matches,today,state.favorites,false,1000);
  const todayCount=total.filter(m=>matchDay(m)===today).length;
  const tomorrowCount=total.filter(m=>matchDay(m)===nextDay(today)).length;
  const owned=total.filter(m=>favoriteMatch(m,state.favorites)).length;
  const target=$("daily-mini-summary");
  target.replaceChildren(
    node("span","",number(todayCount)+" sélection(s) aujourd'hui"),
    node("span","",number(tomorrowCount)+" demain"),
    node("span","",number(owned)+" concernant vos favoris")
  );
  const age=state.generatedAt?Date.now()-new Date(state.generatedAt).getTime():NaN;
  let dateInfo=state.generatedAt?"Sélections mises à jour : "+fmtTime(state.generatedAt):"Date de mise à jour non fournie";
  if(!state.sourceOK.data)dateInfo="Sélections indisponibles actuellement";
  else if(Number.isFinite(age)&&age>36*3600000)dateInfo+=" · données anciennes, vérifiez la date";
  else if(Number.isFinite(age)&&age<0)dateInfo+=" · horodatage à vérifier";
  if(state.sourceOK.data&&state.dataSource==="cache")dateInfo+=" · version hors ligne";
  $("daily-last-updated").textContent=dateInfo;
}
function setFilter(filter){
  state.filter=filter==="favorites"?"favorites":"all";
  try{localStorage.setItem(STORAGE.filter,state.filter);}catch{}
  document.querySelectorAll("[data-daily-filter]").forEach(btn=>{
    btn.setAttribute("aria-pressed",String(btn.dataset.dailyFilter===state.filter));
  });
  renderFixtures();
}
function favoriteButton(kind,name){
  const key=normalizeName(name);
  const chosen=state.favorites[kind].some(v=>normalizeName(v)===key);
  const button=node("button","", (chosen?"★ ":"☆ ")+limitText(name,26));
  button.type="button";
  button.setAttribute("aria-pressed",String(chosen));
  button.setAttribute("aria-label",(chosen?"Retirer des favoris : ":"Ajouter aux favoris : ")+name);
  button.addEventListener("click",()=>{
    const before=state.favorites[kind].some(v=>normalizeName(v)===key);
    if(!before&&state.favorites[kind].length>=MAX_FAVORITES){
      statusMessage("daily-favorite-message","Limite de 20 favoris pour chaque catégorie.");
      return;
    }
    state.favorites=toggleFavorite(state.favorites,kind,name);
    safeWrite(STORAGE.favorites,state.favorites);
    statusMessage("daily-favorite-message",
      (before?"Retiré des favoris : ":"Ajouté aux favoris : ")+name);
    renderFavorites();
    renderFixtures();
    renderNews();
  });
  return button;
}
function matchCard(m){
  const card=node("article","mx-daily-match-card");
  const top=node("div","mx-daily-match-top");
  top.append(node("span","",limitText(m.league||"Compétition",75)));
  top.append(node("span","mx-daily-chip",String(m.category||"PRO").toUpperCase()));
  card.append(top);
  card.append(node("h3","",limitText(m.home_team||"Équipe à domicile",95)+" — "+
    limitText(m.away_team||"Équipe à l'extérieur",95)));
  card.append(node("p","",fmtTime(m.event_date)));
  const pred=node("div","mx-daily-prediction");
  pred.append(node("span","",limitText(m.prediction?.type||m.prediction?.label||"Sélection",125)));
  const conf=displayConfidence(m);
  pred.append(node("strong","",conf===null?"—":number(conf)+" % estimés"));
  card.append(pred);
  const controls=node("div","mx-daily-fav-buttons");
  for(const [kind,value] of [["teams",m.home_team],["teams",m.away_team],["leagues",m.league]]){
    if(typeof value==="string"&&value.trim())controls.append(favoriteButton(kind,value));
  }
  card.append(controls);
  const link=node("a","mx-daily-card-link","Consulter la sélection →");
  link.href="pronos.html?day="+(matchDay(m)===localDay(new Date())?"today":"tomorrow");
  card.append(link);
  return card;
}
function renderFixtures(){
  const target=$("daily-fixtures");
  if(!state.sourceOK.data){
    setChildren(target,[empty("Le flux des pronostics est momentanément indisponible. Les favoris enregistrés restent conservés.")]);
    return;
  }
  const all=upcoming(state.matches,localDay(new Date()),state.favorites,state.filter==="favorites",30);
  if(!all.length){
    target.replaceChildren(empty(state.filter==="favorites"
      ?"Aucune sélection du jour ou de demain ne concerne vos favoris. Vous pouvez consulter toutes les sélections."
      :"Aucune sélection publiée pour aujourd'hui et demain dans le flux consulté."));
    return;
  }
  target.replaceChildren(...all.map(matchCard));
}
function sourceNames(){
  const teams=new Map(),leagues=new Map();
  for(const m of state.matches){
    if(!eligible(m))continue;
    for(const value of [m.home_team,m.away_team]){
      if(typeof value==="string"&&value.trim()&&!teams.has(normalizeName(value)))
        teams.set(normalizeName(value),value.trim());
    }
    if(typeof m.league==="string"&&m.league.trim())
      leagues.set(normalizeName(m.league),m.league.trim());
  }
  return{teams:[...teams.values()].sort((a,b)=>a.localeCompare(b,"fr")),
    leagues:[...leagues.values()].sort((a,b)=>a.localeCompare(b,"fr"))};
}
function updateFavoriteOptions(){
  const kind=$("daily-favorite-kind").value;
  $("daily-favorite-name").placeholder=kind==="teams"?"Rechercher une équipe":"Rechercher une compétition";
  const options=sourceNames()[kind];
  const list=$("daily-favorite-options");
  list.replaceChildren();
  for(const label of options.slice(0,250)){
    const option=document.createElement("option");
    option.value=label;
    list.append(option);
  }
}
function renderFavorites(){
  const tags=$("daily-favorite-tags");
  const output=[];
  for(const kind of ["teams","leagues"]){
    for(const text of state.favorites[kind]){
      const tag=node("span","mx-daily-tag",(kind==="teams"?"Équipe · ":"Ligue · ")+text);
      const remove=node("button","","×");
      remove.type="button";
      remove.setAttribute("aria-label","Retirer "+text+" des favoris");
      remove.addEventListener("click",()=>{
        state.favorites=toggleFavorite(state.favorites,kind,text);
        safeWrite(STORAGE.favorites,state.favorites);
        renderFavorites();renderFixtures();renderNews();
      });
      tag.append(remove);output.push(tag);
    }
  }
  if(!output.length)output.push(empty("Aucun favori enregistré sur cet appareil."));
  tags.replaceChildren(...output);
  $("daily-clear-favorites").hidden=!state.favorites.teams.length&&!state.favorites.leagues.length;
}
function addFavorite(event){
  event.preventDefault();
  const kind=$("daily-favorite-kind").value;
  const value=$("daily-favorite-name").value.trim().replace(/\s+/g," ");
  const options=sourceNames()[kind]||[];
  const canonical=options.find(name=>normalizeName(name)===normalizeName(value));
  if(!canonical){
    statusMessage("daily-favorite-message",
      "Sélectionnez une équipe ou une compétition présente dans le flux de matchs publié.");
    return;
  }
  const exists=state.favorites[kind].some(n=>normalizeName(n)===normalizeName(canonical));
  if(exists){
    statusMessage("daily-favorite-message","Déjà dans vos favoris : "+canonical);
    return;
  }
  if(state.favorites[kind].length>=MAX_FAVORITES){
    statusMessage("daily-favorite-message","Limite atteinte : 20 favoris par catégorie.");
    return;
  }
  state.favorites=toggleFavorite(state.favorites,kind,canonical);
  safeWrite(STORAGE.favorites,state.favorites);
  $("daily-favorite-name").value="";
  statusMessage("daily-favorite-message","Favori enregistré : "+canonical);
  renderFavorites();renderFixtures();renderNews();
}
function renderExact(){
  const list=$("daily-exact-scores"),meta=$("daily-exact-meta");
  const doc=state.exact;
  if(!state.sourceOK.exact||!doc||!Array.isArray(doc.simple)){
    meta.textContent="Propositions de scores exacts indisponibles.";
    list.replaceChildren(empty("Retrouvez les derniers scores exacts sur la page dédiée."));
    return;
  }
  const sameDate=doc.date===localDay(new Date());
  meta.textContent=(sameDate?"Propositions datées d'aujourd'hui":"Dernières propositions publiées le "+limitText(doc.date,15))+
    ". Probabilités estimées, pas des résultats officiels."+
    (state.exactSource==="cache"?" · version hors ligne":"");
  const rows=doc.simple.slice(0,5).filter(m=>m&&typeof m==="object");
  list.replaceChildren(...rows.map(m=>{
    const row=node("div","mx-daily-score-row");
    const left=node("div");
    left.append(node("strong","",limitText(m.home,60)+" — "+limitText(m.away,60)));
    left.append(node("small","",limitText(m.league,80)+" · "+fmtTime(m.kickoff_utc)));
    const probability=Number(m.probability);
    const right=node("span","",limitText(m.score,12)+
      (Number.isFinite(probability)&&probability>=0&&probability<=1
        ?" · "+(probability*100).toFixed(1)+" % estimés":""));
    row.append(left,right);
    return row;
  }));
}
function renderResults(){
  const recent=settled(state.matches,new Date(),30);
  const p=performance(state.matches,new Date(),30);
  const performanceRoot=$("daily-performance");
  const stat=(value,label)=>{
    const block=node("div","mx-daily-stat");
    block.append(node("strong","",value),node("span","",label));
    return block;
  };
  performanceRoot.replaceChildren(
    stat(number(p.total),"Sélections évaluées (30 j)"),
    stat(number(p.won),"Validées gagnantes"),
    stat(number(p.notValidated),"Non validées"),
    stat(p.rate==null?"—":p.rate.toLocaleString("fr-FR")+" %","Taux de validation observé"),
    stat(p.confidenceAverage==null?"—":p.confidenceAverage.toLocaleString("fr-FR")+" %","Confiance moyenne annoncée (estimée)")
  );
  const list=$("daily-results-list");
  if(!state.sourceOK.data){
    list.replaceChildren(empty("Résultats indisponibles pour le moment."));return;
  }
  if(!recent.length){
    list.replaceChildren(empty("Aucun match terminé et évalué sur les 30 derniers jours dans le flux disponible."));return;
  }
  list.replaceChildren(...recent.slice(0,10).map(m=>{
    const row=node("div","mx-daily-result");
    const detail=node("div");
    detail.append(node("strong","",limitText(m.home_team,70)+" "+m.home_score+"–"+m.away_score+" "+limitText(m.away_team,70)));
    detail.append(node("small","",fmtTime(m.event_date)+" · "+limitText(m.prediction?.type||"",55)));
    const result=resultState(m);
    const status=node("span","mx-daily-status "+(result==="win"?"win":"not_validated"),
      result==="win"?"Validée":"Non validée");
    row.append(detail,status);return row;
  }));
  const categories=$("daily-category-performance");
  if(!p.byCategory.length){
    categories.replaceChildren(empty("Données insuffisantes."));return;
  }
  const table=node("table","mx-daily-table");
  const head=document.createElement("thead");
  const hrow=document.createElement("tr");
  for(const h of ["Catégorie","Évaluées","Validées","Taux"])hrow.append(node("th","",h));
  head.append(hrow);table.append(head);
  const body=document.createElement("tbody");
  for(const c of p.byCategory){
    const row=document.createElement("tr");
    for(const value of [c.name,c.total,c.won,(100*c.won/c.total).toFixed(1)+" %"]){
      row.append(node("td","",value));
    }
    body.append(row);
  }
  table.append(body);
  categories.replaceChildren(table);
}
function newsCard(item,recommended){
  const card=node("article","mx-daily-news-card");
  if(recommended)card.append(node("span","mx-daily-chip","VOTRE FAVORI"));
  card.append(node("span","",fmtTime(item.published)+" · "+limitText(item.source||"Actualité",65)));
  card.append(node("h3","",limitText(item.title,200)));
  const excerpt=limitText(item.summary_short||item.summary||"",225);
  if(excerpt)card.append(node("p","",excerpt));
  const link=node("a","","Lire l'article →");
  link.href="infos.html?news="+encodeURIComponent(item.slug);
  card.append(link);return card;
}
function renderNews(){
  const target=$("daily-news");
  if(!state.sourceOK.news){
    target.replaceChildren(empty("Les actualités sont momentanément indisponibles."));
    return;
  }
  const articles=validNews(state.news);
  const fav=new Set(newsForFavorites(articles,state.favorites).map(n=>n.slug));
  const prioritized=articles.filter(n=>fav.has(n.slug)).concat(articles.filter(n=>!fav.has(n.slug)));
  if(!prioritized.length){
    target.replaceChildren(empty("Aucun article publié actuellement."));return;
  }
  target.replaceChildren(...prioritized.slice(0,6).map(n=>newsCard(n,fav.has(n.slug))));
}
function changeLinks(items,type){
  const wrapper=node("div","mx-daily-change-list");
  for(const obj of items.slice(0,4)){
    if(type==="news"){
      const a=node("a","",limitText(obj.title,55));
      a.href="infos.html?news="+encodeURIComponent(obj.slug);
      wrapper.append(a);
    }else{
      wrapper.append(node("span","",limitText(obj.home_team,37)+" — "+limitText(obj.away_team,37)));
    }
  }
  if(items.length>4)wrapper.append(node("span","","… et "+number(items.length-4)+" autre(s)"));
  return wrapper;
}
function renderChanges(){
  const root=$("daily-changes-content"),diff=state.diff;
  root.replaceChildren();
  if(!diff || diff.firstVisit){
    root.append(empty("Première consultation sur cet appareil : vos nouveautés apparaîtront lors d'une prochaine visite, après comparaison des données publiées."));
    $("daily-previous-visit").textContent="Première consultation";
    return;
  }
  $("daily-previous-visit").textContent=state.previousWhen?"Après votre passage du "+fmtTime(state.previousWhen):"Comparaison locale";
  const pairs=[
    [diff.newMatches,"Nouvelles sélections ajoutées au flux","match"],
    [diff.updatedMatches,"Matchs dont le statut ou le score a changé","match"],
    [diff.newNews,"Nouveaux articles dans le flux","news"]
  ];
  let total=0;
  for(const [items,label,type] of pairs){
    if(!items.length)continue;
    total+=items.length;
    const block=node("div","mx-daily-change-line");
    block.append(node("strong","",number(items.length)),node("span","",label));
    root.append(block,changeLinks(items,type));
  }
  if(!total)root.append(empty("Aucun changement détecté dans les données publiées depuis votre précédente visite enregistrée sur cet appareil."));
  root.append(node("p","mx-daily-footnote",
    "Comparaison locale des publications ; elle ne mesure pas les modifications survenues puis supprimées entre deux visites."));
}
function renderEducation(){
  const tip=todayTip(new Date());
  $("daily-tip-title").textContent=tip.title;
  $("daily-tip-body").textContent=tip.body;
}
function loadReminder(){
  try{
    const time=localStorage.getItem(STORAGE.reminderTime);
    if(time&&/^([01]\d|2[0-3]):[0-5]\d$/.test(time))$("daily-reminder-time").value=time;
  }catch{}
}
function downloadReminder(){
  try{
    const time=$("daily-reminder-time").value;
    const source=reminderICS(new Date(),time);
    try{localStorage.setItem(STORAGE.reminderTime,time);}catch{}
    const blob=new Blob([source],{type:"text/calendar;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;a.download="mr-xpronos-rappel-quotidien.ics";
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    statusMessage("daily-reminder-status",
      "Rappel préparé pour "+time+" (heure locale). Ouvrez le fichier et confirmez dans votre calendrier ; rien n'est ajouté sans votre action.");
  }catch{
    statusMessage("daily-reminder-status","Impossible de préparer le rappel ; vérifiez l'heure choisie.");
  }
}
function currentUserId(){
  let id="";
  try{id=localStorage.getItem("mx_user_id")||"";}catch{}
  if(/^(MX|PL)-[a-zA-Z0-9._-]{6,120}$/.test(id))return id;
  if(typeof crypto==="undefined"||typeof crypto.randomUUID!=="function")return null;
  id="MX-"+crypto.randomUUID();
  try{localStorage.setItem("mx_user_id",id);}catch{return null;}
  return id;
}
function uint8FromBase64(s){
  const normalized=(s+"=".repeat((4-s.length%4)%4)).replace(/-/g,"+").replace(/_/g,"/");
  const raw=atob(normalized);
  return Uint8Array.from(raw,c=>c.charCodeAt(0));
}
function pushStatus(){
  const label=$("daily-push-status");
  if(!("Notification" in window)||!("serviceWorker" in navigator)||!("PushManager" in window)){
    label.textContent="Les notifications push ne sont pas disponibles dans ce navigateur.";
    $("daily-push-enable").disabled=true;$("daily-push-disable").disabled=true;
    return;
  }
  const standalone=(()=>{try{return matchMedia("(display-mode: standalone)").matches||navigator.standalone===true;}catch{return false;}})();
  if(/iphone|ipad|ipod/i.test(navigator.userAgent)&&!standalone){
    label.textContent="Sur iPhone, ajoutez d'abord l'application à l'écran d'accueil pour pouvoir activer les notifications.";
    $("daily-push-enable").disabled=true;
    return;
  }
  label.textContent="Autorisation actuelle du navigateur : "+(
    Notification.permission==="granted"?"accordée":Notification.permission==="denied"?"refusée":"non demandée")+
    ". Les envois restent généraux et ne suivent pas vos favoris.";
}
async function optInPush(){
  const status=$("daily-push-status");
  if(!("Notification" in window)||!("PushManager" in window)||!("serviceWorker" in navigator))return;
  const btn=$("daily-push-enable");
  btn.disabled=true;
  try{
    // Appel direct depuis le geste utilisateur, avant toute autre requête.
    let permission=Notification.permission;
    if(permission==="default")permission=await Notification.requestPermission();
    if(permission!=="granted"){
      status.textContent="Permission non accordée. Vous pouvez continuer à consulter les contenus sans notification.";return;
    }
    const [{supabaseUrl},reg]=await Promise.all([
      import("./config.js"),
      Promise.race([navigator.serviceWorker.ready,
        new Promise((_,reject)=>setTimeout(()=>reject(Error("Service Worker non disponible")),6000))])
    ]);
    let sub=await reg.pushManager.getSubscription();
    if(!sub){
      const keyResponse=await fetch(supabaseUrl+"/functions/v1/vapid-public-key",{cache:"no-store"});
      if(!keyResponse.ok)throw Error("Clé publique push indisponible");
      const vapid=(await keyResponse.text()).trim();
      if(!vapid)throw Error("Clé publique push absente");
      sub=await reg.pushManager.subscribe({
        userVisibleOnly:true,applicationServerKey:uint8FromBase64(vapid)
      });
    }
    const id=currentUserId();
    if(!id)throw Error("Navigateur non compatible avec les identifiants anonymes");
    const resp=await fetch(supabaseUrl+"/functions/v1/push-subscribe",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({user_id:id,subscription:sub})
    });
    if(!resp.ok)throw Error("Abonnement distant non confirmé (HTTP "+resp.status+")");
    status.textContent="Demande d'abonnement enregistrée. Les notifications, si elles sont envoyées, seront générales et facultatives.";
  }catch(error){
    status.textContent="Abonnement non confirmé : "+limitText(error?.message||"service indisponible",160)+
      ". Les rappels de calendrier restent utilisables.";
  }finally{btn.disabled=false;}
}
async function optOutPush(){
  const btn=$("daily-push-disable");
  btn.disabled=true;
  try{
    const reg=await navigator.serviceWorker.ready;
    const sub=await reg.pushManager.getSubscription();
    if(!sub){
      statusMessage("daily-push-status","Aucun abonnement push actif sur cet appareil.");
      return;
    }
    const ok=await sub.unsubscribe();
    statusMessage("daily-push-status",ok
      ?"Abonnement push désactivé sur cet appareil. Votre autorisation générale reste réglable dans le navigateur."
      :"Impossible de désactiver l'abonnement ; utilisez les paramètres des notifications du navigateur.");
  }catch(error){
    statusMessage("daily-push-status","Désactivation impossible : "+limitText(error.message||error,100));
  }finally{btn.disabled=false;}
}
async function shareDigest(){
  const today=localDay(new Date());
  const items=upcoming(state.matches,today,state.favorites,false,1000).filter(m=>matchDay(m)===today);
  const results=performance(state.matches,new Date(),30);
  const content="Mr XPRONOS · Football du "+formatDay(new Date())+
    "\nSélections publiées pour aujourd'hui : "+number(items.length)+
    "\nSélections terminées évaluées (30 j) : "+number(results.total)+
    " ; validées : "+number(results.won)+
    " ; non validées : "+number(results.notValidated)+
    "\nAnalyses informatives, sans résultat garanti.\n"+
    new URL("aujourdhui.html",location.href).href;
  const button=$("daily-share");
  if(navigator.share){
    try{await navigator.share({title:"Mr XPRONOS — Football du jour",text:content});return;}
    catch(err){if(err?.name==="AbortError")return;}
  }
  try{
    await navigator.clipboard.writeText(content);
    button.textContent="Résumé copié !";
    setTimeout(()=>{button.textContent="Partager le résumé du jour";},2500);
  }catch{
    button.textContent="Partage indisponible";
    setTimeout(()=>{button.textContent="Partager le résumé du jour";},2500);
  }
}
function bindUI(){
  $("daily-refresh").addEventListener("click",()=>{void load();});
  document.querySelectorAll("[data-daily-filter]").forEach(btn=>
    btn.addEventListener("click",()=>setFilter(btn.dataset.dailyFilter)));
  $("daily-favorite-kind").addEventListener("change",updateFavoriteOptions);
  $("daily-add-favorite").addEventListener("submit",addFavorite);
  $("daily-clear-favorites").addEventListener("click",()=>{
    state.favorites={teams:[],leagues:[]};
    safeWrite(STORAGE.favorites,state.favorites);
    renderFavorites();renderFixtures();renderNews();
    statusMessage("daily-favorite-message","Vos favoris ont été supprimés sur cet appareil.");
  });
  $("daily-reminder-download").addEventListener("click",downloadReminder);
  $("daily-push-enable").addEventListener("click",()=>{void optInPush();});
  $("daily-push-disable").addEventListener("click",()=>{void optOutPush();});
  $("daily-share").addEventListener("click",()=>{void shareDigest();});
}
async function load(){
  if(state.loading)return;
  state.loading=true;
  $("daily-refresh").disabled=true;
  const requestedAt=Date.now();
  try{
    showError("");
    const [matchResp,newsResp,exactResp]=await Promise.all([
      publicJSON("data.json"),publicJSON("footnews.json"),publicJSON("scores-exacts.json")
    ]);
    const dataOK=Array.isArray(matchResp.value?.matches);
    const newsOK=Array.isArray(newsResp.value);
    const exactOK=Array.isArray(exactResp.value?.simple)&&
      exactResp.value?.status==="published";
    state.sourceOK={data:dataOK,news:newsOK,exact:exactOK};
    state.dataSource=matchResp.source;
    state.exactSource=exactResp.source;
    state.matches=dataOK?normalizeData(matchResp.value):[];
    state.news=newsOK?validNews(newsResp.value):[];
    state.exact=exactOK?exactResp.value:null;
    state.generatedAt=dataOK?matchResp.value?.generated_at:null;
    if(!dataOK&&!newsOK&&!exactOK)
      showError("Impossible de récupérer les flux publiés. Vérifiez votre connexion puis réessayez ; vos préférences restent conservées.");
    else if([dataOK,newsOK,exactOK].some(v=>!v))
      showError("Certains contenus ne sont pas disponibles actuellement. Les sections concernées ne présentent pas de données fictives.");
    const baseline=safeRead(STORAGE.baseline);
    const sessionBaseline=(()=>{try{return JSON.parse(sessionStorage.getItem(STORAGE.session)||"null");}catch{return null;}})();
    const previous=sessionBaseline || baseline;
    const current=makeSnapshot(state.matches,state.news,new Date(requestedAt));
    if(!dataOK)current.matches=previous?.matches||{};
    if(!newsOK)current.news=previous?.news||[];
    state.diff=changesSince(previous,current,state.matches,state.news);
    state.previousWhen=previous?.when || null;
    if(!sessionBaseline){
      try{sessionStorage.setItem(STORAGE.session,JSON.stringify(previous||{firstVisit:true}));}catch{}
      // Pas de baseline sur une requête entièrement échouée.
    }
    if(dataOK||newsOK){
      safeWrite(STORAGE.baseline,current);
    }
    renderSummary();
    renderFixtures();
    renderFavorites();
    updateFavoriteOptions();
    renderExact();
    renderResults();
    renderNews();
    renderChanges();
  }catch(error){
    showError("Chargement interrompu : "+limitText(error?.message||error,120));
  }finally{
    state.loading=false;
    $("daily-refresh").disabled=false;
  }
}
function init(){
  state.favorites=normalizeFavorites(safeRead(STORAGE.favorites));
  try{state.filter=localStorage.getItem(STORAGE.filter)==="favorites"?"favorites":"all";}catch{}
  document.querySelectorAll("[data-daily-filter]").forEach(btn=>
    btn.setAttribute("aria-pressed",String(btn.dataset.dailyFilter===state.filter)));
  bindUI();loadReminder();renderFavorites();renderEducation();pushStatus();
  void load();
}
init();
void import("./daily-audience.mjs").then(module=>module.start()).catch(()=>{});
