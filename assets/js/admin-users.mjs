import {adminConfirm} from "./admin-phase3.mjs";
// Administration of delegated staff. Role RLS and owner checks happen server-side.
const roles={owner:"Propriétaire",editor:"Éditeur",communications:"Communication",viewer:"Lecture seule"};
export async function mountAdminUsers(sb,root){
 if(!root)return;
 root.replaceChildren();
 const panel=document.createElement("section");panel.className="card";
 panel.innerHTML=`<h3>Équipe administratrice</h3>
  <p class="muted">Seul le propriétaire peut accorder ou modifier les accès. Un compte Supabase Auth existant est requis.</p>
  <div class="users-v4-summary" role="group" aria-label="Synthèse des comptes chargés">
   <div><strong id="users-v4-total">0</strong><span>Comptes chargés</span></div>
   <div><strong id="users-v4-active">0</strong><span>Accès actifs</span></div>
   <div><strong id="users-v4-disabled">0</strong><span>Accès désactivés</span></div>
  </div>
  <div class="admin-filter-row">
   <div><label for="role-user-id">Identifiant utilisateur (UUID)</label><input id="role-user-id" placeholder="UUID du compte Supabase" autocomplete="off"></div>
   <div><label for="role-kind">Rôle</label><select id="role-kind">
     <option value="viewer">Lecture seule</option><option value="editor">Éditeur CMS</option>
     <option value="communications">Communication / Push</option><option value="owner">Propriétaire</option>
   </select></div>
   <div><label for="role-active">Accès</label><select id="role-active">
     <option value="true">Actif</option><option value="false">Désactivé</option>
   </select></div>
  </div>
  <button type="button" class="btn btn-primary" id="role-save">Enregistrer l'accès</button>
  <p role="status" id="role-status" class="muted"></p>
  <div class="users-v4-toolbar" role="group" aria-label="Filtres de la liste des administrateurs">
   <div><label for="users-v4-search">Recherche</label><input id="users-v4-search" type="search" placeholder="Email ou identifiant UUID" autocomplete="off"></div>
   <div><label for="users-v4-role">Rôle</label><select id="users-v4-role">
    <option value="all">Tous les rôles</option><option value="owner">Propriétaire</option>
    <option value="editor">Éditeur</option><option value="communications">Communication</option>
    <option value="viewer">Lecture seule</option></select></div>
   <div><label for="users-v4-state">État</label><select id="users-v4-state">
    <option value="all">Tous les états</option><option value="active">Actifs</option>
    <option value="disabled">Désactivés</option></select></div>
   <p id="users-v4-counter" class="users-v4-counter" role="status" aria-live="polite"></p>
  </div>
  <div class="admin-pronostics-table-scroll users-v4-scroll"><table id="role-table" class="users-v4-table">
    <thead><tr><th>Compte</th><th>Rôle</th><th>Statut</th><th>Action</th></tr></thead><tbody></tbody>
  </table></div>`;
 root.append(panel);
 const $=id=>panel.querySelector("#"+id);
 const message=text=>{$("role-status").textContent=text;};
 const {data:{user}}=await sb.auth.getUser();
 const self=user?.id;
 const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
 let busy=false;
 const filter=()=>{
  const q=$("users-v4-search").value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  const role=$("users-v4-role").value,state=$("users-v4-state").value;
  const all=[...$("role-table").querySelectorAll("tbody tr")];
  let shown=0;
  for(const row of all){
   const visible=(!q||row.dataset.userSearch.includes(q))&&
    (role==="all"||row.dataset.userRole===role)&&
    (state==="all"||row.dataset.userState===state);
   row.hidden=!visible;if(visible)shown++;
  }
  $("users-v4-counter").textContent=shown+" / "+all.length+
   " compte(s) affiché(s) parmi les comptes chargés (250 maximum).";
 };
 for(const id of ["users-v4-search","users-v4-role","users-v4-state"])$(id).addEventListener("input",filter);
 const load=async()=>{
  message("Chargement…");
  const {data,error}=await sb.from("admin_users")
    .select("user_id,email,active,access_role").order("created_at",{ascending:false}).limit(250);
  if(error){message("Lecture impossible : "+error.message);return;}
  const tbody=$("role-table").querySelector("tbody");tbody.replaceChildren();
  const accounts=data||[];
  $("users-v4-total").textContent=String(accounts.length);
  $("users-v4-active").textContent=String(accounts.filter(x=>x.active===true).length);
  $("users-v4-disabled").textContent=String(accounts.filter(x=>x.active!==true).length);
  for(const row of accounts){
   const tr=document.createElement("tr");
   tr.dataset.userSearch=[row.email,row.user_id,roles[row.access_role]].filter(Boolean)
    .join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
   tr.dataset.userRole=row.access_role||"viewer";
   tr.dataset.userState=row.active===true?"active":"disabled";
   for(const text of [row.email||row.user_id,roles[row.access_role]||row.access_role,
     row.active?"Actif":"Désactivé"]){
    const td=document.createElement("td");td.textContent=String(text||"—");tr.append(td);
   }
   const td=document.createElement("td"),edit=document.createElement("button");
   edit.type="button";edit.className="btn btn-secondary";edit.textContent="Modifier";
   edit.addEventListener("click",()=>{
    $("role-user-id").value=row.user_id;
    $("role-kind").value=row.access_role||"viewer";
    $("role-active").value=row.active?"true":"false";
    $("role-save").focus();
   });
   td.append(edit);tr.append(td);tbody.append(tr);
  }
  message((data?.length||0)+" comptes administrateur(s) chargés.");
  filter();
 };
 $("role-save").addEventListener("click",async()=>{
  if(busy)return;
  const uid=$("role-user-id").value.trim().toLowerCase(),
   role=$("role-kind").value,active=$("role-active").value==="true";
  if(!uuid.test(uid)){message("Identifiant utilisateur invalide.");return;}
  if(uid===self&&(!active||role!=="owner")){
   message("Impossible de désactiver ou rétrograder ton propre compte propriétaire.");return;
  }
  if(!Object.hasOwn(roles,role))return;
  if(!await adminConfirm("Confirmer le rôle "+roles[role]+" pour ce compte ?\n"+uid+
    (active?"\nCompte actif":"\nCompte désactivé")))return;
  busy=true;$("role-save").disabled=true;
  try{
   const {error}=await sb.from("admin_users").upsert({
    user_id:uid,access_role:role,active
   },{onConflict:"user_id"});
   if(error)throw error;
   await sb.from("audit_log").insert({actor_user_id:self,action:"admin_role_changed",
    details:{target_user_id:uid,role,active}});
   await load();
  }catch(err){message("Modification refusée : "+String(err?.message||err));}
  finally{busy=false;$("role-save").disabled=false;}
 });
 await load();
}
