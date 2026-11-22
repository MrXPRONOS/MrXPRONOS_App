// Durée unique des copies privées livrées par Ciné Radar.
// Le déclencheur de nettoyage vérifie les échéances chaque minute ;
// Telegram peut occasionnellement retarder une suppression en cas de limite API.
export const PRIVATE_COPY_LIFETIME_HOURS = 12;
export const PRIVATE_COPY_LIFETIME_MS = PRIVATE_COPY_LIFETIME_HOURS * 60 * 60 * 1000;
// Les livraisons antérieures au changement gardaient une promesse de 24 h.
// Un reçu attesté après coup doit respecter l'échéance annoncée au moment réel
// de cet envoi, pas la date de sa réconciliation administrative.
export const PRIVATE_COPY_12H_CUTOVER_UTC = '2026-11-22T05:14:44Z';
export function privateCopyExpirySqlModifier(sentAt) {
 const text=String(sentAt||'').trim().replace(' ','T');
 const date=/Z$|[+-]\d{2}:\d{2}$/.test(text)?text:text+'Z';
 const time=Date.parse(date);
 if(!Number.isFinite(time))throw Error('invalid_sent_at');
 return time < Date.parse(PRIVATE_COPY_12H_CUTOVER_UTC)?'+24 hours':'+12 hours';
}


function cleanTitle(title) {
 return String(title || 'Votre vidéo Ciné Radar').replace(/[\u0000-\u001f\u007f]+/g,' ').trim().slice(0,100);
}
export function copyExpiryCaption(title,{now=Date.now()}={}) {
 const expiry=new Date(now+PRIVATE_COPY_LIFETIME_MS);
 if(!Number.isFinite(expiry.getTime()))throw Error('invalid_expiry_time');
 const iso=expiry.toISOString();
 const date=iso.slice(8,10)+'/'+iso.slice(5,7)+'/'+iso.slice(0,4);
 const hour=iso.slice(11,16);
 return '🎬 '+cleanTitle(title)+'\n\n'+
  '⏳ Cette vidéo sera supprimée automatiquement de ce chat 12 heures après son envoi.\n'+
  '🕒 Suppression prévue : '+date+' à '+hour+' (UTC).\n'+
  '💾 Pour la conserver, transfère-la dans « Messages enregistrés » avant cette heure.';
}
