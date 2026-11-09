function unwrap(response,operation){
  if(response?.error)throw Error(operation+": "+(response.error.message||"échec"));
  if(!response?.data)throw Error(operation+": réponse vide");
  return response.data;
}
export function validateTotpCode(value){
  const code=String(value||"").trim();
  if(!/^\d{6}$/.test(code))throw Error("Code TOTP invalide : six chiffres attendus");
  return code;
}
export async function adminMfaStatus(sb){
  const assurance=unwrap(await sb.auth.mfa.getAuthenticatorAssuranceLevel(),"Assurance MFA");
  const factors=unwrap(await sb.auth.mfa.listFactors(),"Facteurs MFA");
  return {currentLevel:assurance.currentLevel,nextLevel:assurance.nextLevel,
    verifiedFactors:(factors.totp||[]).filter(x=>x.status==="verified")};
}
export async function beginAdminTotp(sb){
  const result=unwrap(await sb.auth.mfa.enroll({factorType:"totp",friendlyName:"Mr XPRONOS administration"}),"Enrôlement TOTP");
  if(!result.id||!result.totp?.qr_code)throw Error("Réponse TOTP incomplète");
  return {factorId:result.id,qrCode:result.totp.qr_code};
}
export async function completeAdminTotp(sb,factorId,enteredCode){
  if(!factorId)throw Error("Facteur MFA manquant");
  return unwrap(await sb.auth.mfa.challengeAndVerify({factorId,code:validateTotpCode(enteredCode)}),"Vérification TOTP");
}
export async function stepUpAdminTotp(sb,enteredCode){
  const {verifiedFactors}=await adminMfaStatus(sb);
  if(!verifiedFactors.length)throw Error("Aucun facteur MFA vérifié");
  return completeAdminTotp(sb,verifiedFactors[0].id,enteredCode);
}
