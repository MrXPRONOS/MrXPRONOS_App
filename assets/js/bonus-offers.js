import { BOOKS } from "./bonus-catalogue.js";
const select=document.getElementById("bonus-bookmaker-select");
const grid=document.getElementById("bonus-grid");
const modal=document.getElementById("bonus-modal");
const text=(v)=>String(v??"");
const esc=(v)=>text(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const validLink=u=>{try{const v=new URL(u);return ["https:","http:"].includes(v.protocol)?v.href:""}catch{return ""}};
const imagePath=(book,index)=>"prono-live/assets/bonus-banners/"+book.name.toLowerCase().replace(/[^a-z0-9]+/g,"-")+"-"+(index+1)+".webp";
const active=BOOKS.flatMap(b=>b.bonuses.map((x,i)=>({book:b,offer:x,index:i})));
const desc="Catalogue issu de Prono Live. Les montants, la disponibilité et les conditions n'ont pas été revérifiés pour octobre 2026.";
function render(){
  const chosen=select.value;
  const list=active.filter(x=>chosen==="all"||x.book.name===chosen);
  grid.innerHTML=list.map(({book:b,offer:o,index:i})=>`
  <article class="bonus-premium-card bonus-bookmaker-card" data-book="${esc(b.name)}">
    <div class="bonus-card-head">
      <img src="${esc(b.logo.replace("../",""))}" alt="Logo ${esc(b.name)}" loading="lazy">
      <span class="bonus-card-badge">${esc(o[0])}</span>
    </div>
    <div class="bonus-card-body">
      <small class="mx-offer-book">${esc(b.name)}</small>
      <h3>${esc(o[1])}</h3>
      <strong class="mx-offer-value">${esc(o[2])}</strong>
      <p>${esc(o[3])}</p>
      <span class="mx-offer-status">À confirmer auprès du bookmaker</span>
      <div class="bonus-actions">
        <button class="btn btn-primary" type="button" data-book="${esc(b.name)}" data-index="${i}">Voir les détails</button>
        <a class="btn btn-secondary" href="${esc(validLink(o[6]))}" target="_blank" rel="noopener noreferrer">Conditions officielles</a>
      </div>
    </div>
  </article>`).join("");
  if(!list.length)grid.innerHTML='<p>Aucune promotion trouvée.</p>';
}
select.innerHTML='<option value="all">Tous les bookmakers (30 offres)</option>'+BOOKS.map(b=>'<option value="'+esc(b.name)+'">'+esc(b.name)+' (5 offres)</option>').join("");
select.addEventListener("change",render);
grid.addEventListener("click",event=>{
  const button=event.target.closest("button[data-index]");
  if(!button)return;
  const b=BOOKS.find(b=>b.name===button.dataset.book), i=Number(button.dataset.index),o=b?.bonuses[i];
  if(!o)return;
  document.getElementById("bonus-modal-image").src=imagePath(b,i);
  document.getElementById("bonus-modal-image").alt="Visuel promotionnel de "+b.name;
  document.getElementById("bonus-modal-image").onerror=(e)=>{e.currentTarget.src=b.logo.replace("../","");e.currentTarget.onerror=null};
  document.getElementById("bonus-modal-title").textContent=b.name+" · "+o[1]+" · "+o[2];
  document.getElementById("bonus-modal-description").innerHTML=
    '<p>'+esc(o[3])+'</p><h4>Conditions mentionnées dans Prono Live</h4><ul>'+
    o[4].map(t=>'<li>'+esc(t)+'</li>').join('')+
    '</ul><h4>Marche à suivre</h4><ol>'+o[5].map(t=>'<li>'+esc(t)+'</li>').join('')+
    '</ol><p class="mx-offer-warning">'+esc(desc)+'</p>';
  document.getElementById("bonus-modal-footer").innerHTML='<a href="'+esc(validLink(o[6]))+'" target="_blank" rel="noopener noreferrer">Consulter les conditions officielles ↗</a> · Code partenaire : '+esc(b.code);
  const link=document.getElementById("bonus-modal-link");
  link.href=validLink(b.url);link.rel="sponsored noopener noreferrer";
  modal.style.display="flex";
});
window.closeBonusModal=()=>modal.style.display="none";
document.querySelectorAll('[data-copy],#bonus-copy-code').forEach(btn=>{
  btn.addEventListener("click",async()=>{
    try{await navigator.clipboard.writeText("XPVIP");const prior=btn.textContent;btn.textContent="Code copié !";setTimeout(()=>btn.textContent=prior,1700)}
    catch{window.prompt("Copiez le code promo :", "XPVIP")}
  });
});
render();
