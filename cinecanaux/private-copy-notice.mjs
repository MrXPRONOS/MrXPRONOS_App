// Durée unique des copies privées livrées par Ciné Radar.
// Le déclencheur de nettoyage vérifie les échéances chaque minute ;
// Telegram peut occasionnellement retarder une suppression en cas de limite API.
export const PRIVATE_COPY_LIFETIME_HOURS = 12;
export const PRIVATE_COPY_LIFETIME_MS = PRIVATE_COPY_LIFETIME_HOURS * 60 * 60 * 1000;

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
