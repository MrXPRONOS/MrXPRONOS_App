import {adminMfaStatus,beginAdminTotp,completeAdminTotp} from "./admin-mfa-flow.mjs";

// Non-blocking enrollment: AAL2 server enforcement is enabled only after verified enrollment.
export async function initAdminMfaControl(sb,container){
  if(!container||container.querySelector("[data-admin-mfa-setup]"))return;
  // Neon Managed Better Auth has not shipped this legacy Supabase TOTP API.
  // Do not offer enrollment that cannot be completed. Keep database admin RLS enforced.
  if(!sb?.auth?.mfa?.getAuthenticatorAssuranceLevel)return;
  const button=document.createElement("button");
  button.type="button";button.dataset.adminMfaSetup="1";button.className="admin-btn outline";
  button.textContent="Sécurité du compte · MFA";container.appendChild(button);
  button.addEventListener("click",async()=>{
    button.disabled=true;
    let overlay;
    try{
      const status=await adminMfaStatus(sb);
      overlay=document.createElement("div");overlay.setAttribute("role","dialog");
      overlay.setAttribute("aria-modal","true");overlay.setAttribute("aria-label","Authentification renforcée");
      overlay.style.cssText="position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.88);padding:3rem 1rem;overflow:auto";
      const box=document.createElement("section");
      box.style.cssText="max-width:440px;margin:auto;background:#171c28;color:#fff;padding:24px;border-radius:12px";
      const title=document.createElement("h3");title.textContent="Sécurité administrateur — Double authentification";
      const info=document.createElement("p");info.style.whiteSpace="pre-line";
      const done=document.createElement("button");done.type="button";done.textContent="Fermer";
      done.onclick=()=>overlay.remove();box.append(title,info,done);
      if(status.currentLevel==="aal2")info.textContent="MFA vérifié pour cette session.";
      else{
        let factorId;
        if(status.verifiedFactors.length){
          factorId=status.verifiedFactors[0].id;
          info.textContent="Saisis le code à six chiffres de ton application Authenticator.";
        }else{
          const enroll=await beginAdminTotp(sb);factorId=enroll.factorId;
          info.textContent="Scanne le QR code dans Authenticator puis vérifie les six chiffres.";
          if(/^data:image\/svg\+xml(?:;base64|;utf8)?,/i.test(enroll.qrCode)){
            const img=document.createElement("img");img.src=enroll.qrCode;
            img.alt="QR de configuration de la double authentification";
            img.style.cssText="display:block;max-width:230px;width:100%;background:#fff;margin:14px auto";
            box.insertBefore(img,done);
          }else info.textContent+="\nQR indisponible. Vérifie la configuration MFA.";
        }
        const field=document.createElement("input");field.type="text";field.inputMode="numeric";
        field.autocomplete="one-time-code";field.maxLength=6;field.placeholder="Code à 6 chiffres";
        field.setAttribute("aria-label","Code TOTP");
        const verify=document.createElement("button");verify.type="button";verify.textContent="Vérifier";
        verify.onclick=async()=>{
          verify.disabled=true;
          try{
            await completeAdminTotp(sb,factorId,field.value);
            field.value="";info.textContent="Deuxième facteur vérifié. Actualise la page pour renouveler la session.";
            verify.remove();
          }catch(err){
            field.value="";info.textContent="Vérification refusée : "+String(err?.message||"code incorrect");verify.disabled=false;
          }
        };
        box.insertBefore(field,done);box.insertBefore(verify,done);
      }
      overlay.appendChild(box);document.body.appendChild(overlay);
    }catch(err){
      window.alert("MFA indisponible : "+String(err?.message||"erreur"));
      overlay?.remove();
    }finally{button.disabled=false;}
  });
}
