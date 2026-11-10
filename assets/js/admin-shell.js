/* Navigation shell: no Supabase calls; business logic remains in admin-real.js. */
const workspace = document.getElementById("app");
const sidebar = document.getElementById("admin-sidebar");
const openButton = document.getElementById("sidebar-open");
const closeButton = document.getElementById("sidebar-close");
const backdrop = document.getElementById("sidebar-backdrop");
const collapseButton = document.getElementById("sidebar-collapse");
const mobileMenuButton = document.getElementById("mobile-nav-menu");
const nav = document.querySelector(".sidebar-nav");
const screenTitles = {
 overview:["Tableau de bord","Vue d’ensemble de la plateforme Mr XPRONOS.","ACCUEIL"],
 pronostics:["Pronostics","Consulter les pronostics et leurs résultats.","PILOTAGE"],
 push:["Notifications Push","Diffuser des notifications et gérer les abonnés.","COMMUNICATION"],
 vip:["Gestion VIP","Gérer les accès et les avantages des membres.","COMMUNICATION"],
 articles:["Articles","Créer et modifier les publications du blog.","CONTENUS"],
 conseils:["Conseils","Éditer les contenus éducatifs et les guides.","CONTENUS"],
 bonus:["Bonus et bookmakers","Gérer les offres, bonus et partenaires.","CONTENUS"],
 infos:["Informations","Publier les actualités et communications.","CONTENUS"],
 media:["Médiathèque","Importer, retrouver et sélectionner les images et vidéos.","CONTENUS"],
 health:["Automatisations","Surveiller les tâches programmées et leur état.","SYSTÈME"],
 incidents:["Incidents","Créer, suivre et résoudre les incidents.","SYSTÈME"],
 users:["Administrateurs","Déléguer les accès et contrôler les rôles.","SYSTÈME"],
 audit:["Journal d’audit","Consulter les actions et les modifications.","SYSTÈME"]
};
function closeMenu(){
 workspace?.classList.remove("menu-open");
 document.body.classList.remove("admin-menu-visible");
 if(backdrop)backdrop.hidden=true;
 openButton?.setAttribute("aria-expanded","false");
 mobileMenuButton?.setAttribute("aria-expanded","false");
}
function openMenu(){
 if(window.matchMedia("(min-width: 821px)").matches)return;
 workspace?.classList.add("menu-open");
 document.body.classList.add("admin-menu-visible");
 if(backdrop)backdrop.hidden=false;
 openButton?.setAttribute("aria-expanded","true");
 mobileMenuButton?.setAttribute("aria-expanded","true");
 closeButton?.focus();
}
openButton?.addEventListener("click",openMenu);
mobileMenuButton?.addEventListener("click",openMenu);
closeButton?.addEventListener("click",()=>{closeMenu();openButton?.focus()});
backdrop?.addEventListener("click",()=>{closeMenu();openButton?.focus()});
window.addEventListener("keydown",event=>{
 if(!workspace?.classList.contains("menu-open"))return;
 if(event.key==="Escape"){
  closeMenu();
  (mobileMenuButton&&window.matchMedia("(max-width: 640px)").matches?mobileMenuButton:openButton)?.focus();
  return;
 }
 if(event.key!=="Tab"||!sidebar)return;
 const tabbables=Array.from(sidebar.querySelectorAll('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])'))
  .filter(el=>el.getClientRects().length>0);
 if(!tabbables.length)return;
 const first=tabbables[0],last=tabbables[tabbables.length-1];
 if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
 else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
});
const media = window.matchMedia("(min-width: 821px)");
media.addEventListener?.("change",()=>{if(media.matches)closeMenu()});

// Compact desktop sidebar is a display preference; no Supabase state is changed.
const collapsePreferenceKey="mx.admin.sidebar.collapsed";
function applyCollapsed(collapsed,persist=false){
 const compact=Boolean(collapsed);
 workspace?.classList.toggle("sidebar-collapsed",compact);
 collapseButton?.setAttribute("aria-expanded",String(!compact));
 collapseButton?.setAttribute("aria-label",compact?"Déployer le menu latéral":"Réduire le menu latéral");
 collapseButton?.setAttribute("title",compact?"Déployer le menu":"Réduire le menu");
 if(persist){try{localStorage.setItem(collapsePreferenceKey,compact?"1":"0");}catch{}}
}
try{applyCollapsed(localStorage.getItem(collapsePreferenceKey)==="1");}catch{applyCollapsed(false);}
collapseButton?.addEventListener("click",()=>{
 applyCollapsed(!workspace?.classList.contains("sidebar-collapsed"),true);
});

// Labels stay understandable to assistive technologies when the sidebar is compact.
document.querySelectorAll(".sidebar-nav .nav-item").forEach(item=>{
 const label=item.textContent.trim().replace(/\\s+/g," ");
 if(label){item.setAttribute("title",label);if(!item.hasAttribute("aria-label"))item.setAttribute("aria-label",label);}
});
document.querySelector(".sidebar-external")?.setAttribute("aria-label","Voir le site public");
function handleSection(tabName){
 const tab = screenTitles[tabName]?tabName:"overview";
 const [title,description,group]=screenTitles[tab];
 workspace?.classList.toggle("mx-home-active",tab==="overview");
 document.getElementById("view-title").textContent=title;
 document.getElementById("view-description").textContent=description;
 document.getElementById("breadcrumb").textContent=group;
 document.title=title+" | Administration Mr XPRONOS";
 document.querySelectorAll(".nav-item").forEach(button=>{
  const active=button.dataset.tab===tab;
  button.setAttribute("aria-current",active?"page":"false");
  button.classList.toggle("active",active);
 });
 document.querySelectorAll(".admin-mobile-nav .tab").forEach(button=>{
  const active=button.dataset.tab===tab;
  button.classList.toggle("active",active);
  button.setAttribute("aria-current",active?"page":"false");
 });
 document.getElementById("btnPublish").hidden=!["articles","conseils","bonus","infos"].includes(tab);
 closeMenu();
 // The legacy supervision iframe stays unloaded until explicitly requested.
 // This avoids two scrollable dashboards and costly duplicate data requests.
}
window.addEventListener("mx:admin-tab",event=>handleSection(event.detail?.name));
nav?.addEventListener("click",event=>{
 const button=event.target.closest("button[data-tab]");
 if(!button)return;
 closeMenu();
});
document.querySelector(".sidebar-brand")?.addEventListener("click",event=>{
 event.preventDefault();window.MXAdminNavigate?.("overview");
});

document.getElementById("admin-detailed-supervision")?.addEventListener("toggle",event=>{
 if(!event.currentTarget.open)return;
 const frame=document.getElementById("supervisionFrame");
 if(frame&&!frame.getAttribute("src")&&frame.dataset.src)frame.src=frame.dataset.src;
});
