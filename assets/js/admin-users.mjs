// Administration of delegated staff. Role RLS and owner checks happen server-side.
const roles={owner:"Propriétaire",editor:"Éditeur",communications:"Communication",viewer:"Lecture seule"};
export async function mountAdminUsers(sb,root){
 if(!root)return;
 root.replaceChildren();
 const panel=document.createElement("section");panel.className="card";
 panel.innerHTML=`<h3>Équipe administratrice</h3>
  <p class="muted">Seul le propriétaire peut accorder ou modifier les accès. Un compte Supabase Auth existant est requis.</p>
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
  <div class="admin-pronostics-table-scroll"><table id="role-table">
    <thead><tr><th>Compte</th><th>Rôle</th><th>Statut</th><th>Action</th></tr></thead><tbody></tbody>
  </table></div>`;
 root.append(panel);
 const $=id=>panel.querySelector("#"+id);
 const message=text=>{$("role-status").textContent=text;};
 const {data:{user}}=await sb.auth.getUser();
 const self=user?.id;
 const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
 let busy=false;
 const load=async()=>{
  message("Chargement…");
  const {data,error}=await sb.from("admin_users")
    .select("user_id,email,active,access_role").order("created_at",{ascending:false}).limit(250);
  if(error){message("Lecture impossible : "+error.message);return;}
  const tbody=$("role-table").querySelector("tbody");tbody.replaceChildren();
  for(const row of data||[]){
   const tr=document.createElement("tr");
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
  if(!confirm("Confirmer le rôle "+roles[role]+" pour ce compte ?\n"+uid+
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
