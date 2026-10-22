export const APP_HTML=String.raw`<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Ciné Radar — Trouve ton canal</title><meta name="theme-color" content="#0b1223"><meta name="description" content="Découvre des canaux Telegram publics de films, séries et animés.">
<script defer src="https://telegram.org/js/telegram-web-app.js?64"></script>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:#f4f7ff;background:#0b1223;--muted:#afc0db;--panel:#16203a;--stroke:#304064;--blue:#5b8dfa}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;background:radial-gradient(circle at 100% -10%,#243f7e 0,transparent 38%),#0b1223}
button,input{font:inherit}
.page{width:min(100%,800px);padding:20px 17px 54px;margin:0 auto}
.top{display:flex;align-items:center;gap:11px;margin-bottom:16px}
.mark{height:44px;width:44px;border-radius:14px;background:linear-gradient(135deg,#448ef4,#9b6ded);display:grid;place-items:center;font-size:24px;box-shadow:0 6px 20px #296fe847}
.top h1{margin:0;font-size:22px;letter-spacing:-.6px}
.hero{margin-bottom:20px;background:linear-gradient(110deg,#17264c,#292254);border:1px solid #42578a66;border-radius:19px;padding:21px 20px;position:relative;overflow:hidden}
.hero h2{font-size:22px;line-height:1.2;margin:0 0 7px;position:relative;z-index:1}
.hero p{font-size:13px;color:#d5ddf4;margin:0;position:relative;z-index:1}
.hero:after{content:"🎬";position:absolute;right:13px;top:11px;font-size:62px;opacity:.18;transform:rotate(-15deg)}
.tabs{display:flex;gap:7px;margin-bottom:17px;overflow-x:auto;scrollbar-width:none}
.tabs button{border-radius:30px;background:#17233f;border:1px solid #2d3e64;color:#c6d2eb;padding:11px 12px;white-space:nowrap;font-size:13px;cursor:pointer}
.tabs button.active{color:white;background:#3878df;border-color:#5e9aff;font-weight:800}
.search{display:flex;background:#16203a;border:1px solid #314262;border-radius:12px;gap:9px;align-items:center;padding:0 13px;margin-bottom:18px}
.search input{width:100%;background:none;color:white;border:0;outline:0;padding:13px 0}
.search:focus-within{outline:2px solid #6d9bff55}
.section-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 13px}
.section-title h3{font-size:16px;margin:0}
.section-title span{font-size:12px;color:#a9bce0}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.card{border:1px solid var(--stroke);border-radius:16px;overflow:hidden;background:var(--panel);min-width:0;cursor:pointer}
.card-cover{position:relative;height:143px;background:linear-gradient(145deg,#283b79,#3f286e);display:flex;align-items:center;justify-content:center}
.card-cover img{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}
.card-cover .placeholder{font-size:44px;opacity:.65}
.card .content{padding:11px}
.card h4{font-size:13px;margin:0 0 11px;min-height:35px;overflow-wrap:anywhere;line-height:1.3}
.actions{display:flex;gap:7px}
.actions button{border:0;border-radius:9px;padding:10px 5px;font-size:12px;cursor:pointer;font-weight:800;flex:1}
.actions .view{background:#293a61;color:#d5e6ff}
.actions .open{background:#357ce7;color:white}
.empty{grid-column:1/-1;padding:30px 16px;text-align:center;color:var(--muted);border:1px dashed #425375;border-radius:14px;line-height:1.5}
.empty strong{display:block;color:white;margin-bottom:6px}
.loading{opacity:.75;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:.55}50%{opacity:1}}
.sheet-bg{position:fixed;z-index:40;inset:0;background:#020717cf;display:flex;align-items:flex-end;justify-content:center;backdrop-filter:blur(5px);padding:8px 8px max(8px,env(safe-area-inset-bottom))}
[hidden]{display:none!important}
.sheet{max-height:92dvh;overflow:auto;width:min(100%,560px);border:1px solid #53699e;background:#14203a;border-radius:22px;padding:18px}
.sheet-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:15px;font-size:12px;color:#bbcdf1;font-weight:800;letter-spacing:.5px}
.close{border:0;background:#263956;color:white;border-radius:50%;height:37px;width:37px;font-size:21px;cursor:pointer}
.preview-photo{height:220px;background:linear-gradient(135deg,#2e5285,#39266b);border-radius:14px;overflow:hidden;display:grid;place-items:center;margin-bottom:15px;color:#c6d8ff;font-size:42px}
.preview-photo img{width:100%;height:100%;object-fit:cover}
.profile-row{display:flex;align-items:center;gap:12px}
.avatar{width:54px;height:54px;flex:0 0 54px;border-radius:14px;background:#365a9b;display:grid;place-items:center;overflow:hidden}
.avatar img{width:100%;height:100%;object-fit:cover}
.profile-row h3{margin:0;font-size:19px;overflow-wrap:anywhere}
.bio{font-size:13px;color:#d6e2f8;line-height:1.55;white-space:pre-line;margin:13px 0 16px;overflow-wrap:anywhere}
.big-open{border:0;width:100%;background:#337bf2;color:white;border-radius:12px;padding:15px;font-weight:900;cursor:pointer}
.footer{text-align:center;color:#8394b8;font-size:11px;margin-top:32px}
@media(min-width:550px){.cards{grid-template-columns:repeat(3,minmax(0,1fr))}.card-cover{height:180px}.preview-photo{height:280px}.sheet-bg{align-items:center}}
@media(prefers-reduced-motion:reduce){.loading{animation:none}}
</style></head>
<body><main class="page">
<div class="top"><div class="mark">🎬</div><h1>Ciné Radar</h1></div>
<div class="hero"><h2>Un clic, un canal.</h2><p>Films, séries et animés au même endroit.</p></div>
<div class="tabs" id="tabs">
<button data-type="all" class="active">✨ Tous</button><button data-type="films">🎬 Films</button><button data-type="series">📺 Séries</button><button data-type="animes">🎌 Animés</button>
</div>
<label class="search"><span aria-hidden="true">🔎</span><input id="search" type="search" autocomplete="off" aria-label="Rechercher" placeholder="Rechercher un canal…"></label>
<div class="section-title"><h3>Les canaux</h3><span id="count">—</span></div>
<div class="cards" id="cards" aria-live="polite"><div class="empty loading">Chargement des canaux…</div></div>
<div class="footer">Ciné Radar · Annuaire public</div>
</main>
<div class="sheet-bg" id="overlay" hidden role="dialog" aria-modal="true" aria-label="Aperçu du canal"><div class="sheet" id="sheet"></div></div>
<script>
(function(){
// Browser starts rendering before the optional Telegram SDK finishes downloading.
const PRELOADED_CATALOG=null;
const telegram=()=>window.Telegram?.WebApp||null;
document.addEventListener("DOMContentLoaded",()=>{try{telegram()?.ready();telegram()?.expand();}catch{}});
const $=id=>document.getElementById(id);
const validLink=url=>/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/.test(String(url||""));
const photoHost=url=>/^https:\/\/(?:[a-z0-9-]+\.)*(?:telesco\.pe|telegram\.org|telegram-cdn\.org|t\.me)\/[^\s"'<>]{1,1200}$/i.test(String(url||""));
let type="all",query="",channels=[],allChannels=[],lastFetch=0,fetchPending=null,images=new Map(),inFlight=new Map(),previewToken=0,thumbQueue=[],thumbActive=0;
const MAX_THUMB_FETCH=2;
const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const btn=(text,cls,callback)=>{const b=node("button",cls,text);b.type="button";b.onclick=e=>{e.stopPropagation();callback();};return b;};
async function api(path){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
 try{const r=await fetch(path,{cache:"default",signal:controller.signal});const body=await r.json();if(!r.ok)throw Error(body.error||"Service indisponible");return body;}finally{clearTimeout(timer);}
}
function openTelegram(link){if(!validLink(link))return;const tg=telegram();if(tg?.openTelegramLink)tg.openTelegramLink(link);else window.open(link,"_blank","noopener");}
function close(){ previewToken++;$("overlay").hidden=true;$("sheet").textContent=""; }
function buildCard(channel){
 const card=node("article","card"),cover=node("div","card-cover");card.dataset.channelId=String(channel.id);
 cover.append(node("span","placeholder",channel.type==="animes"?"🎌":channel.type==="series"?"📺":"🎬"));
 if(photoHost(channel.photo)){const image=node("img");image.alt="Photo publique de "+channel.title;image.loading="lazy";image.onerror=()=>{image.remove();};image.src=channel.photo;cover.append(image);}
 const main=node("div","content");main.append(node("h4",null,channel.title));
 const buttons=node("div","actions");
 buttons.append(btn("👁 Aperçu","view",()=>showPreview(channel)),btn("Ouvrir ↗","open",()=>openTelegram(channel.link)));
 main.append(buttons);card.append(cover,main);card.onclick=()=>showPreview(channel);
 return card;
}
function render(){
 const root=$("cards");root.textContent="";$("count").textContent=channels.length+" canal"+(channels.length>1?"aux":"");
 if(!channels.length){const empty=node("div","empty");empty.append(node("strong",null,"Aucun canal disponible"),document.createTextNode("Essaie une autre catégorie ou recherche."));root.append(empty);return;}
 for(const channel of channels)root.append(buildCard(channel));
}
function updatePreviewThumb(id,data){
 images.set(id,data);
 const item=allChannels.find(x=>x.id===id);
 if(!item)return;
 const imageUrl=[data.post_image,data.photo].find(photoHost);
 if(!imageUrl)return;
 item.photo=imageUrl;
 const card=Array.from($("cards").children).find(x=>Number(x.dataset.channelId)===id);
 const cover=card?.querySelector(".card-cover");
 if(cover&&!cover.querySelector("img")){
  const img=node("img");img.alt="Image publique du canal "+item.title;img.loading="lazy";
  img.onerror=()=>img.remove();img.src=imageUrl;cover.append(img);
 }
}
async function getPreview(id){
 if(images.has(id))return images.get(id);
 if(inFlight.has(id))return inFlight.get(id);
 const pending=api("/api/channel-preview?id="+encodeURIComponent(id)).then(r=>r.channel)
  .then(p=>{updatePreviewThumb(id,p);return p;}).finally(()=>inFlight.delete(id));
 inFlight.set(id,pending);return pending;
}
function enqueueVisiblePhotos(){
 // At most two metadata requests at a time; card clicks are never queued.
 const candidates=channels.slice(0,4).filter(c=>!photoHost(c.photo)&&!images.has(c.id)&&!inFlight.has(c.id));
 for(const c of candidates)if(!thumbQueue.includes(c.id))thumbQueue.push(c.id);
 pumpThumbs();
}
function pumpThumbs(){
 while(thumbActive<MAX_THUMB_FETCH&&thumbQueue.length){
  const id=thumbQueue.shift();
  if(images.has(id)||inFlight.has(id))continue;
  thumbActive++;
  getPreview(id).catch(()=>{}).finally(()=>{thumbActive--;pumpThumbs();});
 }
}
function applyFilters(){
 const key=query.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase().trim();
 channels=allChannels.filter(c=>{
  if(type!=="all"&&c.type!==type)return false;
  if(!key)return true;
  return (String(c.title)+" "+String(c.genre||"")).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase().includes(key);
 });
 render();
 enqueueVisiblePhotos();
}
async function load(force=false){
 if(allChannels.length)applyFilters();
 if(fetchPending)return fetchPending;
 if(!force&&allChannels.length&&Date.now()-lastFetch<120000)return;
 if(!allChannels.length){
  $("count").textContent="…";$("cards").textContent="";
  $("cards").append(node("div","empty loading","Chargement des canaux…"));
 }
 fetchPending=(async()=>{
  try{
   const result=await api("/api/catalog");
   allChannels=result.channels||[];
   lastFetch=Date.now();
   // Keep the user's current category and search, regardless of when fetch finishes.
   applyFilters();
  }catch{
   if(!allChannels.length){
    $("cards").textContent="";
    const box=node("div","empty");
    box.append(node("strong",null,"Connexion momentanément indisponible"),document.createTextNode("Retouche une catégorie pour réessayer."));
    $("cards").append(box);
   }
  }finally{fetchPending=null;}
 })();
 return fetchPending;
}
function fillPreview(c,p){
 const sheet=$("sheet");sheet.textContent="";
 const bar=node("div","sheet-top","🎬 Aperçu du canal");
 bar.append(btn("×","close",close));sheet.append(bar);
 const visualUrl=[p?.post_image,p?.photo,c.photo].find(photoHost);
 if(visualUrl){
  const visual=node("div","preview-photo");
  const image=node("img");image.alt="Photo publique du canal";image.onerror=()=>{visual.textContent="🎬";};
  image.src=visualUrl;visual.append(image);sheet.append(visual);
 }
 const row=node("div","profile-row"),avatar=node("div","avatar","🎬");
 if(photoHost(p?.photo)){
  const pic=node("img");pic.alt="Photo du canal";pic.onerror=()=>{avatar.textContent="🎬";};
  avatar.textContent="";pic.src=p.photo;avatar.append(pic);
 }
 const label=node("div");label.append(node("h3",null,p?.title||c.title));
 row.append(avatar,label);sheet.append(row);
 if(p?.description&&!p.description.startsWith("Canal Telegram public"))sheet.append(node("p","bio",p.description));
 sheet.append(btn("Ouvrir le canal ↗","big-open",()=>openTelegram(c.link)));
}
function showPreview(c){
 const token=++previewToken;
 $("overlay").hidden=false;
 // Immediate sheet; never wait for Telegram metadata to show the open button.
 fillPreview(c,images.get(c.id));
 if(images.has(c.id))return;
 getPreview(c.id).then(p=>{
  if(token===previewToken&&!$("overlay").hidden)fillPreview(c,p);
 }).catch(()=>{});
}
for(const b of document.querySelectorAll("[data-type]"))b.onclick=()=>{
 type=b.dataset.type;
 for(const x of document.querySelectorAll("[data-type]"))x.classList.toggle("active",x===b);
 if(allChannels.length)applyFilters();else load();
};
$("search").oninput=e=>{
 query=e.target.value.slice(0,70);
 if(allChannels.length)applyFilters();
};
document.addEventListener("visibilitychange",()=>{
 if(document.visibilityState==="visible"&&Date.now()-lastFetch>120000)load(true);
});
$("overlay").onclick=e=>{if(e.target===$("overlay"))close();};
document.addEventListener("keydown",e=>{if(e.key==="Escape")close();});
if(Array.isArray(PRELOADED_CATALOG)&&PRELOADED_CATALOG.length){
 allChannels=PRELOADED_CATALOG;
 lastFetch=Date.now();
 applyFilters();
}
load();
})();
</script></body></html>`;
