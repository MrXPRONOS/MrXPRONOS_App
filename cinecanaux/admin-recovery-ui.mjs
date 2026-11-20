// T02 owner-only CinéX reconciliation panel (existing signed api() and el() helpers).
export const ADMIN_RECOVERY_CSS=String.raw`
.ad-cinex-recover{border:1px solid #3d5a78;border-radius:12px;padding:12px;margin:12px 0;background:#0c2035}
.ad-cinex-recover h4{font-size:13px;margin:0 0 7px}
.ad-cinex-recover p{font-size:12px;color:#bbcee4;margin:5px 0}
.ad-cinex-recover button{font-size:12px;margin:5px 5px 5px 0}
.ad-cinex-recover label{display:block;font-size:11px;margin-top:5px;color:#d9e7f9}
.ad-cinex-recover input[type=number],.ad-cinex-recover input[type=datetime-local]{display:block;width:100%;max-width:300px;padding:8px;background:#193553;border:1px solid #507293;color:white;border-radius:8px}
.ad-cinex-recover .ad-cinex-case{border-top:1px solid #34526d;padding:10px 0}
`;
export const ADMIN_RECOVERY_HTML=String.raw`
<section class="ad-cinex-recover" id="ad-cinex-recover">
 <h4>🎬 Récupération sécurisée des téléchargements</h4>
 <p>Un envoi dont le résultat Telegram est incertain n'est jamais renvoyé automatiquement. Pour confirmer un envoi existant, vérifie d'abord le numéro du message effectivement reçu dans la discussion privée.</p>
 <button type="button" id="ad-cinex-recover-refresh">Actualiser les dossiers</button>
 <p id="ad-cinex-recover-status" role="status">Contrôle des demandes…</p>
 <div id="ad-cinex-recover-cases"></div>
</section>
`;
export const ADMIN_RECOVERY_JS=String.raw`
(()=>{
 const root=document.getElementById('ad-cinex-recover'),status=document.getElementById('ad-cinex-recover-status');
 if(!root||!status)return;
 const list=document.getElementById('ad-cinex-recover-cases');
 const names={libraries:'Vidéothèques',series:'Séries',classics:'Films classiques',franchise:'Fast and Furious'};
 const add=(tag,text,cls)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=String(text);return e;};
 async function refresh(){
  status.textContent='Lecture des dossiers en attente…';
  try{
   const data=await api('/api/admin/cinex/recovery');
   list.replaceChildren();
   const cases=Array.isArray(data.cases)?data.cases:[];
   for(const record of cases){
    const row=add('div',undefined,'ad-cinex-case');
    row.append(add('strong',(names[record.family]||record.family)+' — demande #'+Number(record.job_id)));
    row.append(add('p','Déjà envoyés : '+Number(record.sent||0)+' · En attente : '+Number(record.queued||0)+' · Résultat incertain : '+Number(record.uncertain||0)+' · En cours : '+Number(record.in_flight||0)));
    if(record.resume_safe){
     const btn=add('button','Reprendre uniquement les copies non envoyées');
     btn.type='button';
     btn.onclick=async()=>{
      if(!confirm('Réactiver cette demande sans renvoyer aucun message incertain ?'))return;
      btn.disabled=true;
      try{const out=await api('/api/admin/cinex/recovery',{action:'resume_safe',family:record.family,job_id:record.job_id});status.textContent=out.ok?'Reprise sécurisée enregistrée.':'Reprise refusée.';await refresh();}
      catch(e){status.textContent='Reprise refusée : '+String(e.message||e);btn.disabled=false}
     };
     row.append(btn);
    }
    if(record.uncertain||record.in_flight||record.family==='classics'){
     const toggle=add('button','Confirmer une copie déjà reçue');
     toggle.type='button';
     const form=add('div');form.hidden=true;
     toggle.onclick=()=>{form.hidden=!form.hidden};
     row.append(toggle);
     const itemLabel=add('label','Numéro du fichier (épisode/partie)');
     const item=document.createElement('input');item.type='number';item.min='1';item.step='1';
     if(record.family!=='classics'){itemLabel.append(item);form.append(itemLabel);}
     const messageLabel=add('label','Numéro exact du message Telegram reçu par le destinataire');
     const message=document.createElement('input');message.type='number';message.min='1';message.step='1';message.required=true;
     messageLabel.append(message);form.append(messageLabel);
     const timeLabel=add('label','Date et heure réelles de réception (heure de cet appareil)');
     const time=document.createElement('input');time.type='datetime-local';time.required=true;
     timeLabel.append(time);form.append(timeLabel);
     const checkLabel=add('label','');
     const check=document.createElement('input');check.type='checkbox';
     checkLabel.append(check,document.createTextNode(' Je certifie avoir vérifié cette copie déjà reçue. Aucun nouvel envoi ne sera effectué.'));
     form.append(checkLabel);
     const send=add('button','Enregistrer la preuve, sans envoyer');send.type='button';
     send.onclick=async()=>{
      const iso=time.value?new Date(time.value).toISOString().slice(0,19)+'Z':null;
      if(!check.checked||!iso||!Number.isSafeInteger(Number(message.value))||Number(message.value)<=0||(record.family!=='classics'&&(!Number.isSafeInteger(Number(item.value))||Number(item.value)<=0))){status.textContent='Renseigne une preuve complète, valide et vérifiée.';return}
      if(!confirm('Confirmer un message déjà livré ? Une mauvaise référence de message rendrait la suppression ultérieure dangereuse.'))return;
      send.disabled=true;
      try{const result=await api('/api/admin/cinex/recovery',{action:'confirm_existing_copy',family:record.family,job_id:record.job_id,item:Number(item.value),message_id:Number(message.value),sent_at:iso,confirmed_existing_copy:true});status.textContent=result.ok?'Copie existante enregistrée. Aucun renvoi.':'Réconciliation refusée.';await refresh();}
      catch(e){status.textContent='Réconciliation refusée : '+String(e.message||e);send.disabled=false}
     };
     form.append(send);row.append(form);
    }
    list.append(row);
   }
   if(!cases.length)list.append(add('p','Aucun téléchargement en révision manuelle.'));
   if(Number(data.owner_archive_review||0))list.append(add('p',Number(data.owner_archive_review)+' copie(s) de l’archive propriétaire exigent un transfert manuel de l’original par le propriétaire vers le bot, sans renvoi automatique.'));
   status.textContent=cases.length+' dossier(s) de téléchargement en cours de diagnostic.';
  }catch(e){status.textContent='Diagnostic indisponible : '+String(e.message||e)}
 }
 document.getElementById('ad-cinex-recover-refresh').onclick=refresh;
 const scope=document.getElementById('private');
 if(scope){
  const watcher=new MutationObserver(()=>{if(!scope.hidden){watcher.disconnect();refresh();}});
  watcher.observe(scope,{attributes:true,attributeFilter:['hidden']});
  if(!scope.hidden){watcher.disconnect();refresh()}
 }
})();
`;
