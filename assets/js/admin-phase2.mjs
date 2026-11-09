/* Mr XPRONOS — Phase 2 : operator screens. No network access or mutations of business data. */
import { renderSafeCmsMarkdown } from "./admin-public-markdown.mjs";
const byId=id=>document.getElementById(id);
const elt=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n};
const formatCount=value=>Number(value||0).toLocaleString("fr-FR");
const safeImageUrl=value=>{
 const raw=String(value??"").trim();
 if(!raw)return "";
 try{const url=new URL(raw,location.href);return url.protocol==="https:"||url.origin===location.origin?url.href:""}catch{return ""}
};
const statusClass=value=>/gagn|succ|réuss|sent|publi|actif|à jour/i.test(value)?"ok":/perd|échou|fail|retard|expir|désactiv|cancel/i.test(value)?"danger":"neutral";
const pending=new Set();
function queue(name){
 if(pending.has(name))return;
 pending.add(name);
 requestAnimationFrame(()=>{pending.delete(name);try{enhance(name)}catch(error){console.warn("Phase 2 UI ("+name+")",error)}});
}
function pill(text,extra){
 const node=elt("span","mx2-pill mx2-"+(extra||statusClass(text)),text);
 return node;
}
function readableTable(root){
 root.querySelectorAll("table").forEach(table=>{
  if(!table.querySelector("thead th"))return;
  table.classList.add("mx2-responsive-table");
  const headings=[...table.querySelectorAll("thead th")].map(th=>th.textContent.trim());
  for(const tr of table.querySelectorAll("tbody tr")){
   if(tr.dataset.mx2Labels==="1")continue;
   [...tr.children].forEach((cell,i)=>{if(cell.tagName==="TD")cell.dataset.label=headings[i]||"Détail"});
   tr.dataset.mx2Labels="1";
  }
 });
}
function enhancePronos(root){
 const panel=root.querySelector(".admin-pronostics-panel");
 const list=root.querySelector("#pList");
 if(!panel||!list)return;
 let toolbar=panel.querySelector(".mx2-pronos-toolbar");
 if(!toolbar){
  toolbar=elt("div","mx2-pronos-toolbar");
  const label=elt("span","mx2-eyebrow","AFFICHAGE");
  const buttons=elt("div","mx2-segment");
  for(const [value,title] of [["cards","Fiches"],["table","Tableau"]]){
   const b=elt("button","mx2-segment-button",title);
   b.type="button";b.dataset.view=value;
   b.addEventListener("click",()=>{
    panel.dataset.mx2View=value;
    try{localStorage.setItem("mx.admin.pronos.view",value)}catch{}
    applyPronoView();
   });
   buttons.append(b);
  }
  toolbar.append(label,buttons);
  list.before(toolbar);
  try{panel.dataset.mx2View=localStorage.getItem("mx.admin.pronos.view")==="table"?"table":"cards"}
  catch{panel.dataset.mx2View="cards"}
 }
 function applyPronoView(){
  const view=panel.dataset.mx2View==="table"?"table":"cards";
  const cards=list.querySelector(".mx2-pronos-cards"),table=list.querySelector(".admin-pronostics-table-scroll");
  if(cards)cards.hidden=view!=="cards";
  if(table)table.hidden=view!=="table";
  toolbar.querySelectorAll("[data-view]").forEach(button=>{
   const selected=button.dataset.view===view;
   button.setAttribute("aria-pressed",String(selected));
   button.classList.toggle("is-active",selected);
  });
 }
 const table=list.querySelector("table");
 if(!table){toolbar.hidden=true;return}
 toolbar.hidden=false;
 if(table.dataset.mx2CardsCreated!=="1"){
  table.dataset.mx2CardsCreated="1";
  const rows=[...table.querySelectorAll("tbody tr")];
  const grid=elt("div","mx2-pronos-cards");
  let won=0,lost=0,pending=0;
  for(const tr of rows){
   const cells=[...tr.querySelectorAll(":scope > td")];if(cells.length<5)continue;
   const status=(cells[4].textContent||"En attente").trim();
   if(/gagn/i.test(status))won++;else if(/perd/i.test(status))lost++;else pending++;
   const article=elt("article","mx2-match-card");
   const top=elt("div","mx2-match-top");
   const competition=elt("span","mx2-match-league",cells[0].querySelector("small")?.textContent||"Football");
   top.append(competition,pill(status));
   const teams=elt("div","mx2-match-teams");
   const pair=cells[0].querySelector(".admin-team-pair");
   const names=pair?[...pair.querySelectorAll("b")].map(n=>n.textContent):[];
   const logos=pair?[...pair.querySelectorAll("b")].map((name,i)=>i===0?(name.previousElementSibling?.tagName==="IMG"?name.previousElementSibling:null):(name.nextElementSibling?.tagName==="IMG"?name.nextElementSibling:null)):[];
   for(let i=0;i<2;i++){
    const side=elt("div","mx2-team");
    const imgUrl=safeImageUrl(logos[i]?.getAttribute("src"));
    if(imgUrl){
     const img=elt("img","mx2-team-logo");img.src=imgUrl;img.loading="lazy";img.alt="";img.onerror=()=>img.hidden=true;side.append(img);
    }else side.append(elt("span","mx2-team-placeholder","⚽"));
    side.append(elt("strong","mx2-team-name",names[i]||"Équipe "+(i+1)));
    teams.append(side);
    if(i===0)teams.append(elt("span","mx2-versus","VS"));
   }
   const metrics=elt("div","mx2-match-metrics");
   for(const [key,value] of [["Pronostic",cells[1].textContent],["Confiance",cells[2].textContent],["Score",cells[3].textContent]]){
    const item=elt("div","mx2-match-metric");
    item.append(elt("small","",key),elt("b","",value?.trim()||"—"));metrics.append(item);
   }
   article.append(top,teams,metrics);grid.append(article);
  }
  const summary=elt("div","mx2-mini-summary");
  summary.append(pill(formatCount(rows.length)+" matchs","neutral"),pill(won+" gagnés","ok"),pill(lost+" perdus","danger"),pill(pending+" en attente","neutral"));
  grid.prepend(summary);
  list.prepend(grid);
 }
 applyPronoView();
 readableTable(list);
}
function enhanceCms(root,prefix){
 const group=root.querySelector(".admin-cms-editor-fields");
 const content=byId(prefix+"_content");
 if(!group||!content)return;
 if(!group.querySelector(".mx2-editor-main")){
  const form=elt("div","mx2-editor-main");
  while(group.firstChild)form.append(group.firstChild);
  const preview=elt("aside","mx2-editor-preview");
  preview.setAttribute("aria-label","Aperçu de la publication");
  const top=elt("div","mx2-preview-top");
  top.append(elt("strong","","Aperçu en direct"),elt("span","mx2-pill mx2-neutral","Brouillon local"));
  const img=elt("img","mx2-editor-cover");img.alt="Illustration de la publication";img.hidden=true;
  const header=elt("h3","mx2-editor-preview-title","Titre de la publication");
  const info=elt("p","mx2-preview-meta","Aucun contenu enregistré");
  const body=elt("div","mx2-rendered-markdown");
  preview.append(top,img,header,info,body);
  group.append(form,preview);
  const update=()=>{
   header.textContent=byId(prefix+"_title")?.value.trim()||"Titre de la publication";
   const status=byId(prefix+"_status")?.value==="published"?"Publié":"Brouillon";
   const active=byId(prefix+"_active")?.value==="false"?" · Masqué":"";
   top.lastElementChild.textContent=status+active;
   info.textContent=(byId(prefix+"_category")?.value.trim()||"Sans catégorie")+" · "+
     (content.value.trim().split(/\s+/).filter(Boolean).length||0)+" mots";
   const url=safeImageUrl(byId(prefix+"_image")?.value.trim());
   if(url){img.hidden=false;if(img.src!==url)img.src=url}
   else{img.hidden=true;img.removeAttribute("src")}
   const md=content.value.trim();
   body.innerHTML=md?renderSafeCmsMarkdown(md):"<p>Le contenu apparaîtra ici pendant la rédaction.</p>";
  };
  img.addEventListener("error",()=>{img.hidden=true});
  root.addEventListener("input",update);
  root.addEventListener("change",update);
  root.addEventListener("click",event=>{
   if(event.target.closest("[data-id],.mx-revision-choice,.mx-block-toolbar"))queueMicrotask(update);
  });
  update();
 }
 // Existing CMS search/filters and duplicate buttons remain fully functional.
 root.querySelectorAll("[data-id]").forEach(card=>{
  if(card.dataset.mx2Card)return;
  card.dataset.mx2Card="1";card.classList.add("mx2-content-card");
  const detail=card.querySelector(".muted");
  const metadata=detail?.textContent||"";
  const title=card.querySelector("div[style*='font-weight']")||card.firstElementChild;
  if(title)title.classList.add("mx2-content-title");
  if(detail){
   const row=elt("div","mx2-content-metadata");
   row.append(pill(/\bpublished\b/i.test(metadata)?"Publié":"Brouillon",
     /\bpublished\b/i.test(metadata)?"ok":"neutral"));
   if(/Désactivé/i.test(metadata))row.append(pill("Masqué","danger"));
   detail.after(row);
  }
  if(card.tagName!=="BUTTON"&&!card.hasAttribute("tabindex")){
   card.tabIndex=0;card.setAttribute("role","button");
   card.setAttribute("aria-label","Modifier "+(title?.textContent||"le contenu"));
   card.addEventListener("keydown",event=>{
    if((event.key==="Enter"||event.key===" ") && event.target===card){
     event.preventDefault();card.click();
    }
   });
  }
 });
}
function enhancePush(root){
 const card=root.querySelector(":scope > .card");
 const status=root.querySelector("#push_status");
 const title=root.querySelector("#push_title");
 if(!card||!status||!title)return;
 if(!card.querySelector(".mx2-push-layout")){
  const lead=card.querySelector(":scope > p.muted");
  if(!lead)return;
  const layout=elt("div","mx2-push-layout");
  const form=elt("div","mx2-push-compose");
  const preview=elt("aside","mx2-push-preview");
  const overline=elt("div","mx2-eyebrow","PRÉVISUALISATION — AUCUN ENVOI");
  const device=elt("div","mx2-push-device");
  const deviceTop=elt("div","mx2-push-device-head","MR XPRONOS · Notification");
  const deviceTitle=elt("strong","mx2-push-device-title","Titre de la notification");
  const deviceText=elt("p","mx2-push-device-text","Le message apparaîtra ici pendant la rédaction.");
  const deviceLink=elt("small","mx2-push-device-url","mrxpronos.github.io");
  const foot=elt("p","mx2-push-preview-note","Sélectionne une audience avant l’envoi.");
  device.append(deviceTop,deviceTitle,deviceText,deviceLink);preview.append(overline,device,foot);
  const counts=elt("div","mx2-push-counters");
  const titleCounter=elt("span","","Titre : 0 / 110");
  const messageCounter=elt("span","","Message : 0 / 700");
  counts.append(titleCounter,messageCounter);
  // Move existing form controls without replacing any element or event listener.
  while(lead.nextElementSibling && lead.nextElementSibling!==status){
   form.append(lead.nextElementSibling);
  }
  form.append(counts);
  layout.append(form,preview);lead.after(layout);
  const update=()=>{
   const message=byId("push_body")?.value||"";
   deviceTitle.textContent=title.value.trim()||"Titre de la notification";
   deviceText.textContent=message.trim()||"Le message apparaîtra ici pendant la rédaction.";
   titleCounter.textContent="Titre : "+title.value.length+" / 110";
   messageCounter.textContent="Message : "+message.length+" / 700";
   const url=byId("push_url")?.value||"";
   try{deviceLink.textContent=new URL(url).hostname}catch{deviceLink.textContent="Lien non renseigné"}
   const mode=byId("push_audience")?.value||"";
   foot.textContent=mode==="all"?"Audience : tous les abonnés · confirmation requise avant tout envoi":
    mode==="user"?"Audience : "+(byId("push_user_id")?.value.trim()||"abonné non renseigné"):
    "Choisis une audience avant l’envoi.";
   foot.classList.toggle("mx2-important",mode==="all");
  };
  root.addEventListener("input",update);
  root.addEventListener("change",update);
  root.addEventListener("click",event=>{
   if(event.target.closest("#push_new,#subs_list button"))queueMicrotask(update);
  });
  update();
 }
 readableTable(root);
}
function enhanceVip(root){
 const table=root.querySelector("table"),card=root.querySelector(":scope > .card");
 if(!table||!card)return;
 if(!card.querySelector(".mx2-vip-summary")){
  const heading=card.querySelector("h4");
  const summary=elt("div","mx2-vip-summary");
  const toolbar=elt("div","mx2-vip-toolbar");
  const search=elt("input");search.type="search";search.placeholder="Rechercher un identifiant ou un code";
  search.setAttribute("aria-label","Rechercher parmi les accès VIP chargés");
  const filter=elt("select");filter.setAttribute("aria-label","Filtrer les accès VIP");
  for(const [value,label] of [["all","Tous les statuts"],["active","Actifs"],["expired","Expirés"],["disabled","Désactivés"]]){
   const option=elt("option","",label);option.value=value;filter.append(option);
  }
  const count=elt("p","mx2-filter-count");count.setAttribute("role","status");
  toolbar.append(search,filter,count);
  const rows=[...table.querySelectorAll("tbody tr")];
  const stateOf=tr=>{
   const expiry=Date.parse(tr.dataset.expires||"");
   const active=(tr.dataset.active||"").toLowerCase()==="true"||
     (!tr.dataset.active&&tr.children[3]?.textContent?.trim().toLowerCase()==="oui");
   if(!active)return "disabled";
   if(Number.isFinite(expiry)&&expiry<Date.now())return "expired";
   return "active";
  };
  const translated={active:"Actif",expired:"Expiré",disabled:"Désactivé"};
  const refresh=()=>{
   const totals={active:0,expired:0,disabled:0};
   const q=search.value.trim().toLocaleLowerCase("fr");
   let visible=0;
   for(const tr of rows){
    const state=stateOf(tr);totals[state]++;
    if(tr.dataset.mx2Vip!=="1"){
     tr.dataset.mx2Vip="1";
     const cell=tr.children[3];
     cell?.replaceChildren(pill(translated[state],state==="active"?"ok":state==="expired"?"danger":"neutral"));
    }
    const matches=(filter.value==="all"||state===filter.value)
      && (!q||[tr.children[0]?.textContent,tr.children[1]?.textContent].join(" ").toLocaleLowerCase("fr").includes(q));
    tr.hidden=!matches;if(matches)visible++;
   }
   summary.replaceChildren();
   for(const [key,label] of [["active","Actifs"],["expired","Expirés"],["disabled","Désactivés"]]){
    const box=elt("div","mx2-vip-stat");
    box.append(elt("strong","",formatCount(totals[key])),elt("small","",label));
    summary.append(box);
   }
   count.textContent=visible+" accès affiché(s) sur "+rows.length+" derniers chargés.";
  };
  search.addEventListener("input",refresh);filter.addEventListener("change",refresh);
  heading?.after(summary,toolbar);
  table.classList.add("mx2-vip-table");
  refresh();
 }
 readableTable(root);
}
function enhanceHealth(root){
 readableTable(root);
 for(const table of root.querySelectorAll("table")){
  const header=table.querySelector("thead")?.textContent||"";
  if(!/État/.test(header))continue;
  const index=[...table.querySelectorAll("thead th")].findIndex(th=>/État/.test(th.textContent));
  if(index<0)continue;
  for(const row of table.querySelectorAll("tbody tr")){
   const cell=row.children[index];if(!cell||cell.dataset.mx2State)return;
   const state=cell.textContent.trim();if(!state)continue;
   cell.dataset.mx2State="1";cell.replaceChildren(pill(state));
  }
 }
}
function enhanceAudit(root){
 readableTable(root);
 root.querySelectorAll("details").forEach(detail=>detail.classList.add("mx2-details"));
}
function enhance(name){
 const root=byId("tab-"+name);if(!root)return;
 if(name==="pronostics")enhancePronos(root);
 else if(name==="articles")enhanceCms(root,"a");
 else if(name==="conseils")enhanceCms(root,"c");
 else if(name==="push")enhancePush(root);
 else if(name==="vip")enhanceVip(root);
 else if(name==="health")enhanceHealth(root);
 else if(name==="audit")enhanceAudit(root);
 else readableTable(root);
}
const names=["pronostics","articles","conseils","push","vip","health","audit","bonus","infos","media","users","incidents"];
for(const name of names){
 const root=byId("tab-"+name);if(!root)continue;
 const obs=new MutationObserver(()=>queue(name));
 obs.observe(root,{subtree:true,childList:true});
 queue(name);
}
window.addEventListener("mx:admin-tab",event=>queue(event.detail?.name||"overview"));
