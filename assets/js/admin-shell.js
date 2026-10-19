/* Navigation shell: no Supabase calls; business logic remains in admin-real.js. */
const workspace = document.getElementById("app");
const sidebar = document.getElementById("admin-sidebar");
const openButton = document.getElementById("sidebar-open");
const closeButton = document.getElementById("sidebar-close");
const backdrop = document.getElementById("sidebar-backdrop");
const nav = document.querySelector(".sidebar-nav");
const screenTitles = {
 overview:["Vue générale","Vue centralisée des visiteurs, signaux et performances.","PILOTAGE"],
 pronostics:["Pronostics","Consulter les pronostics et leurs résultats.","PILOTAGE"],
 push:["Notifications Push","Diffuser des notifications et gérer les abonnés.","COMMUNICATION"],
 vip:["Gestion VIP","Gérer les accès et les avantages des membres.","COMMUNICATION"],
 articles:["Articles","Créer et modifier les publications du blog.","CONTENUS"],
 conseils:["Conseils","Éditer les contenus éducatifs et les guides.","CONTENUS"],
 bonus:["Bonus et bookmakers","Gérer les offres, bonus et partenaires.","CONTENUS"],
 infos:["Informations","Publier les actualités et communications.","CONTENUS"],
 media:["Médiathèque","Importer, retrouver et sélectionner les images et vidéos.","CONTENUS"],
 health:["Automatisations","Surveiller les tâches programmées et leur état.","SYSTÈME"],
 audit:["Journal d’audit","Consulter les actions et les modifications.","SYSTÈME"]
};
function closeMenu(){
 workspace?.classList.remove("menu-open");
 backdrop.hidden=true;
 openButton?.setAttribute("aria-expanded","false");
}
function openMenu(){
 workspace?.classList.add("menu-open");
 backdrop.hidden=false;
 openButton?.setAttribute("aria-expanded","true");
 closeButton?.focus();
}
openButton?.addEventListener("click",openMenu);
closeButton?.addEventListener("click",()=>{closeMenu();openButton?.focus()});
backdrop?.addEventListener("click",()=>{closeMenu();openButton?.focus()});
window.addEventListener("keydown",event=>{
 if(event.key==="Escape"&&workspace?.classList.contains("menu-open")){
  closeMenu();openButton?.focus();
 }
});
const media = window.matchMedia("(min-width: 821px)");
media.addEventListener?.("change",()=>{if(media.matches)closeMenu()});
function handleSection(tabName){
 const tab = screenTitles[tabName]?tabName:"overview";
 const [title,description,group]=screenTitles[tab];
 document.getElementById("view-title").textContent=title;
 document.getElementById("view-description").textContent=description;
 document.getElementById("breadcrumb").textContent=group;
 document.title=title+" | Administration Mr XPRONOS";
 document.querySelectorAll(".nav-item").forEach(button=>{
  const active=button.dataset.tab===tab;
  button.setAttribute("aria-current",active?"page":"false");
  button.classList.toggle("active",active);
 });
 document.getElementById("btnPublish").hidden=!["articles","conseils","bonus","infos"].includes(tab);
 closeMenu();
 if(tab==="overview"){
  const frame=document.getElementById("supervisionFrame");
  if(frame&&!frame.src&&frame.dataset.src)frame.src=frame.dataset.src;
 }
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
