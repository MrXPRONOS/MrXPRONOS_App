export const APP_HTML=String.raw`<!doctype html>
<html lang="fr"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1,viewport-fit=cover"/><meta name="theme-color" content="#090d1b"/>
<meta name="description" content="Ciné Radar — Films, séries, animés et favoris."/><title>Ciné Radar</title>
<script src="https://telegram.org/js/telegram-web-app.js?64"></script>
<style>
:root{color-scheme:dark;--bg:#090e1e;--paper:#121b31;--paper2:#192541;--ink:#f4f7ff;--muted:#b1bed9;--line:#2a395a;--blue:#3f87ff;--purple:#9874ff;--glow:rgba(73,122,255,.22);--success:#4bdfab}*{box-sizing:border-box}
body{margin:0;font:15px/1.45 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--ink);min-height:100dvh}
.shell{width:min(100%,760px);margin:auto;padding:18px 16px 102px}header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:10px}
.brand{display:flex;align-items:center;gap:9px;font-size:20px;font-weight:900;letter-spacing:.2px}.brand-icon{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,#3876f5,#8b5cf6);box-shadow:0 8px 22px var(--glow);font-size:23px}
.status{font-size:11px;border:1px solid var(--line);color:var(--muted);border-radius:24px;padding:7px 10px}
.hero{border:1px solid #435bb07a;position:relative;overflow:hidden;border-radius:22px;padding:23px 18px 24px;background:radial-gradient(ellipse at top right,#5943b4b8,transparent 54%),linear-gradient(140deg,#1e3868,#11162d 62%,#1a1640);margin-bottom:18px;box-shadow:0 14px 45px #0004}
.hero::after{content:"";position:absolute;width:210px;height:210px;right:-95px;top:-80px;border-radius:50%;border:32px solid #c0ccff14}
.hero small{text-transform:uppercase;letter-spacing:1.8px;color:#cbd8ff;font-weight:700}
.hero h1{font-size:29px;line-height:1.15;letter-spacing:-.6px;margin:9px 0 10px;max-width:260px}.hero p{color:#d0d9f2;max-width:290px;margin:0;font-size:13px}
.hero .sticker{position:absolute;font-size:58px;right:17px;bottom:12px;transform:rotate(12deg);filter:drop-shadow(0 8px 8px #0005)}
.search{width:100%;display:flex;align-items:center;gap:10px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:12px 14px;color:var(--muted);margin-bottom:14px}
.search:focus-within{border-color:#6a91ff;box-shadow:0 0 0 3px #4d82ec29}.search input{width:100%;background:none;border:none;outline:none;color:var(--ink);font:inherit}.search input::placeholder{color:#8898bb}
.pills{display:flex;gap:8px;overflow:auto;padding-bottom:10px;scrollbar-width:none}.pills::-webkit-scrollbar{display:none}
.pill{white-space:nowrap;padding:10px 13px;background:var(--paper);border:1px solid var(--line);color:var(--muted);border-radius:50px;font-size:13px;cursor:pointer}.pill.active{background:var(--blue);color:white;border-color:var(--blue);font-weight:800}
.filters{display:flex;gap:10px;margin:6px 0 20px}.filters select{flex:1;min-width:0;padding:10px 8px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:12px}
.section{display:flex;align-items:center;justify-content:space-between;margin:10px 0 15px}.section h2{font-size:16px;margin:0}.section span{font-size:12px;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:12px}
.card{border:1px solid var(--line);background:var(--paper);border-radius:17px;overflow:hidden;min-width:0}
.poster{height:120px;background:radial-gradient(circle at 75% 15%,#855cedaa,transparent 60%),linear-gradient(135deg,#18336d,#131c38);display:flex;align-items:center;justify-content:center;font-size:47px;position:relative}
.poster .label{font-size:10px;position:absolute;left:10px;top:9px;background:#04091fc7;border-radius:9px;padding:4px 7px;color:#d8e5ff}
.card-info{padding:13px}.card-info h3{margin:0 0 5px;line-height:1.3;font-size:14px;min-height:36px;overflow-wrap:anywhere}.caption{font-size:12px;color:var(--muted);min-height:34px}.card-actions{display:flex;gap:6px;margin-top:9px}
.btn{border:0;cursor:pointer;border-radius:10px;padding:9px 10px;font:inherit;font-size:12px;font-weight:800;background:var(--paper2);color:var(--ink)}
.btn.primary{background:#2875f5;color:white;flex:1}.btn.icon{min-width:38px}.btn.green{background:#197d62;color:white}.btn.secondary{background:#1a294b}
.empty{padding:35px 20px;border:1px dashed var(--line);border-radius:17px;text-align:center;color:var(--muted);background:#14203a6b}
.empty b{display:block;color:var(--ink);margin:8px 0}.empty .emoji{font-size:30px}
nav{position:fixed;bottom:0;left:0;right:0;border-top:1px solid #2b3d64;background:#10182df5;backdrop-filter:blur(12px);display:flex;justify-content:center;padding:9px max(9px,env(safe-area-inset-right)) calc(9px + env(safe-area-inset-bottom))}
.nav-inner{display:flex;width:min(100%,760px);justify-content:space-around}.nav-link{border:0;background:none;color:#8ea1c7;display:flex;flex-direction:column;gap:2px;align-items:center;font:inherit;font-size:11px;min-width:64px;cursor:pointer}.nav-link strong{font-size:19px}.nav-link.active{color:#67a0ff}
.toast{position:fixed;bottom:87px;left:50%;transform:translateX(-50%);background:#28385b;border:1px solid #4b6799;color:white;padding:11px 16px;border-radius:14px;max-width:90%;font-size:13px;z-index:4;box-shadow:0 12px 32px #0005;display:none}
.smallrow{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.smallrow span{color:var(--muted);font-size:12px}.footer{margin-top:30px;text-align:center;color:#8798bf;font-size:11px}
@media(min-width:540px){.hero h1{font-size:38px;max-width:400px}.hero .sticker{font-size:84px;right:35px}.poster{height:155px}}
</style></head>
<body><main class="shell">
<header><div class="brand"><div class="brand-icon">🎬</div><span>Ciné Radar</span></div><div class="status" id="state">● Connexion Telegram</div></header>
<section class="hero"><small>Le cinéma à portée de clic</small><h1>Le bon canal.<br/>Au bon moment.</h1><p>Explore les films, séries et animés. Sauvegarde les chaînes qui te plaisent.</p><div class="sticker">🍿</div></section>
<label class="search"><span aria-hidden="true">🔎</span><input id="search" placeholder="Film, genre, chaîne..." autocomplete="off" aria-label="Rechercher un canal"/></label>
<div class="pills" id="types" aria-label="Catégories">
<button class="pill active" data-type="all">✨ Tout</button><button class="pill" data-type="films">🎬 Films</button><button class="pill" data-type="series">📺 Séries</button><button class="pill" data-type="animes">🎌 Animés</button></div>
<div class="filters">
<select id="genre" aria-label="Genre"><option value="general">Tous les genres</option><option value="action">Action</option><option value="comedie">Comédie</option><option value="romance">Romance</option><option value="horreur">Horreur</option><option value="drame">Drame</option><option value="sciencefiction">Science-fiction</option><option value="policier">Policier</option><option value="shonen">Shōnen</option><option value="seinen">Seinen</option><option value="fantasy">Fantasy</option></select>
<select id="language" aria-label="Langue"><option value="tous">🌍 Toutes langues</option><option value="VF">🇫🇷 VF</option><option value="VOSTFR">💬 VOSTFR</option><option value="VO">🎞 VO</option></select>
<select id="sort" aria-label="Tri"><option value="recent">Nouveautés</option><option value="popular">Popularité</option><option value="active">Activité</option></select></div>
<div class="section"><h2 id="heading">À découvrir</h2><span id="counter">—</span></div>
<div id="cards" class="cards" aria-live="polite"><div class="empty"><div class="emoji">🎬</div><b>Bienvenue sur Ciné Radar</b>Chargement du catalogue…</div></div>
<div class="footer">Ciné Radar · Répertoire de canaux autorisés · © 2026</div>
</main><nav><div class="nav-inner"><button class="nav-link active" data-tab="explore"><strong>🧭</strong>Explorer</button><button class="nav-link" data-tab="favorites"><strong>⭐</strong>Favoris</button><button class="nav-link" data-tab="new"><strong>🆕</strong>Nouveautés</button><button class="nav-link" data-tab="profile"><strong>👤</strong>Profil</button></div></nav>
<div class="toast" id="toast"></div>
<script>
(function(){
const tg=window.Telegram?.WebApp||null; const initData=tg?.initData||""; let type="all",tab="explore",favIds=new Set(),keyword="",channels=[],timer=0;
if(tg){tg.ready();tg.expand();tg.setHeaderColor?.("#0e1529");tg.setBackgroundColor?.("#090e1e");}
const $=id=>document.getElementById(id);
const toast=message=>{const el=$("toast");el.textContent=message;el.style.display="block";setTimeout(()=>{el.style.display="none";},3200);};
function empty(title,subtitle){const target=$("cards");target.textContent="";const box=document.createElement("div");box.className="empty";box.style.gridColumn="1/-1";const emoji=document.createElement("div");emoji.className="emoji";emoji.textContent="🍿";const h=document.createElement("b");h.textContent=title;box.append(emoji,h,document.createTextNode(subtitle));target.append(box);}
async function request(path,options={}){
 const headers={"X-Telegram-Init-Data":initData,...(options.body?{"content-type":"application/json"}:{})};
 const r=await fetch(path,{...options,headers,cache:"no-store"});
 const data=await r.json().catch(()=>({error:"Réponse illisible"}));
 if(!r.ok)throw new Error(data.error||"Erreur réseau");
 return data;
}
function button(label,kind,action){const b=document.createElement("button");b.className="btn "+kind;b.textContent=label;b.addEventListener("click",action);return b;}
function render(list){
 const root=$("cards");root.textContent="";
 $("counter").textContent=list.length+" canal"+(list.length>1?"aux":"");
 if(!list.length){empty("Aucun canal disponible","Les canaux sont publiés après validation de leurs droits. Essaie un autre filtre.");return;}
 for(const c of list){
  const card=document.createElement("article");card.className="card";
  const poster=document.createElement("div");poster.className="poster";poster.textContent=c.content_type==="animes"?"🎌":c.content_type==="series"?"📺":"🎥";
  const badge=document.createElement("span");badge.className="label";badge.textContent=c.language||"VF";poster.append(badge);
  const info=document.createElement("div");info.className="card-info";
  const title=document.createElement("h3");title.textContent=c.title;
  const sub=document.createElement("div");sub.className="caption";sub.textContent=(c.genre||"Cinéma")+" • "+(c.description||"Canal approuvé").slice(0,62);
  const actions=document.createElement("div");actions.className="card-actions";
  actions.append(button("Ouvrir ↗","primary",()=>{if(tg?.openTelegramLink)tg.openTelegramLink(c.link);else window.open(c.link,"_blank","noopener");}),
    button(favIds.has(c.id)?"★":"☆","icon",async()=>{try{const r=await request("/api/favorite",{method:"POST",body:JSON.stringify({id:c.id})});if(r.favorite)favIds.add(c.id);else favIds.delete(c.id);render(channels);}catch(e){toast(e.message);}}),
    button("↗","icon",()=>{const url="https://t.me/share/url?url="+encodeURIComponent(c.link)+"&text="+encodeURIComponent("🎬 "+c.title+" • Découvert sur Ciné Radar");if(tg?.openTelegramLink)tg.openTelegramLink(url);else window.open(url,"_blank","noopener");}));
  info.append(title,sub,actions);card.append(poster,info);root.append(card);
 }
}
async function load(){
 if(!initData){$("state").textContent="Ouvrir dans Telegram";empty("Mini App Telegram","Ouvre cette Mini App depuis le menu de ton bot pour accéder à ton catalogue et à tes favoris.");return;}
 try{
 $("state").textContent="● Connexion…";
 const query=new URLSearchParams({type,genre:$("genre").value,language:$("language").value,sort:$("sort").value,q:keyword,tab});
 const result=await request("/api/catalog?"+query.toString());
 channels=result.channels;favIds=new Set(result.favorite_ids);render(channels);
 $("state").textContent="● Connecté";$("heading").textContent=tab==="favorites"?"Mes favoris":tab==="new"?"Nouveautés":tab==="profile"?"Mon profil":"À découvrir";
 }catch(e){$("state").textContent="● Indisponible";empty("Connexion impossible",e.message);}}
for(const b of document.querySelectorAll("[data-type]"))b.onclick=()=>{type=b.dataset.type;for(const x of document.querySelectorAll("[data-type]"))x.classList.toggle("active",x===b);load();};
for(const id of ["genre","language","sort"])$(id).addEventListener("change",load);
$("search").addEventListener("input",e=>{keyword=e.target.value.slice(0,80);clearTimeout(timer);timer=setTimeout(load,350);});
for(const n of document.querySelectorAll("[data-tab]"))n.onclick=()=>{
 tab=n.dataset.tab;for(const x of document.querySelectorAll("[data-tab]"))x.classList.toggle("active",x===n);
 if(tab==="profile"){if(!initData){empty("Mini App Telegram","Ouvre depuis le bot.");return;}request("/api/profile").then(p=>{
  channels=[];$("heading").textContent="Mon profil";$("counter").textContent="";const root=$("cards");root.textContent="";
  const box=document.createElement("div");box.className="empty";box.style.gridColumn="1/-1";
  box.textContent="👤 "+p.first_name+" · "+p.favorites+" favoris · "+p.referrals+" invitations";
  const b=button("🎁 Mon lien de parrainage","primary",()=>{if(tg?.close)tg.close();toast("Ouvre /parrainage dans le bot.");});box.append(document.createElement("p"),b);root.append(box);
 }).catch(e=>toast(e.message));return;}
 load();
};
load();
})();
</script></body></html>`;
