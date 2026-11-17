import test from 'node:test';
import assert from 'node:assert/strict';

// Execute the REAL handleUpdate function in a closed sandbox.
// NVIDIA / PostgREST / Telegram are deterministic mocks. No customer messages,
// production DB mutations, fake account creation or real bets.
process.env.MX_ASSISTANT_TELEGRAM_TOKEN='sandbox-token-not-real';
process.env.MX_ASSISTANT_ADMIN_ID='999000';
process.env.MX_ASSISTANT_NVIDIA_KEY='sandbox-nvidia-not-real';
process.env.MX_ASSISTANT_TELEGRAM_WEBHOOK_SECRET='sandbox-secret-not-real';
process.env.SUPABASE_URL='https://sandbox.invalid';
process.env.SUPABASE_SERVICE_ROLE_KEY='sandbox-service-role-not-real';

const db=new Map(), outbound=[], aiCalls=[], operations=[];
const store=name=>{if(!db.has(name))db.set(name,[]);return db.get(name);};
let ids=1,messageId=1,assistant;
const success=(body,status=200)=>({
 ok:status>=200&&status<300,status,
 json:async()=>body,text:async()=>body===null?'':JSON.stringify(body)
});
const tableMatch=(path)=>path.split('?')[0];
const decodeEq=(q,k)=>{
 const x=q.get(k);return x?.startsWith('eq.')?decodeURIComponent(x.slice(3)):undefined;
};
function postgrest(url,opt){
 const u=new URL(url),table=tableMatch(u.pathname.slice('/rest/v1/'.length)),q=u.searchParams;
 const method=opt.method||'GET',data=opt.body?JSON.parse(opt.body):null;
 const rows=store(table);
 const query=()=>rows.filter(r=>{
  for(const key of ['chat_key','update_id','source','status','model']){
   const v=decodeEq(q,key);if(v!==undefined&&String(r[key])!==String(v))return false;
  }
  const created=q.get('created_at')||q.get('handled_at');
  if(created?.startsWith('gte.')&&Date.parse(r.created_at||r.handled_at||0)<Date.parse(created.slice(4)))return false;
  return true;
 });
 if(method==='GET'){
  let result=query().map(r=>({...r}));
  const order=q.get('order')||'';
  if(order) {const [field,direction]=order.split('.');result.sort((a,b)=>direction==='desc'?String(b[field]).localeCompare(String(a[field]),undefined,{numeric:true}):String(a[field]).localeCompare(String(b[field]),undefined,{numeric:true}));}
  if(q.get('limit'))result=result.slice(0,Number(q.get('limit')));
  const fields=q.get('select');
  if(fields&&fields!=='*'){const keys=fields.split(',');result=result.map(r=>Object.fromEntries(keys.map(k=>[k,r[k]])));}
  return success(result);
 }
 if(method==='POST'){
  const items=Array.isArray(data)?data:[data],out=[];
  for(const item of items){
   const pk=table==='mx_telegram_assistant_updates'?'update_id':
     table==='mx_telegram_assistant_model_events'?'id':
     table==='mx_telegram_assistant_delivery_claims'?'update_id':
     table==='mx_telegram_assistant_delivery_receipts'?'update_id':
     table==='mx_telegram_assistant_messages'?'id':'chat_key';
   let found=(table.includes('delivery_')?null:rows.find(r=>r[pk]===item[pk]));
   if(found){
    if((opt.headers.prefer||'').includes('ignore-duplicates'))continue;
    Object.assign(found,item);out.push({...found});continue;
   }
   const next={...item};
   if(next.id==null)next.id=ids++;
   if(next.created_at==null)next.created_at=new Date().toISOString();
   if(table==='mx_telegram_assistant_updates')next.handled_at=new Date().toISOString();
   rows.push(next);out.push({...next});
  }
  return success(opt.headers.prefer?.includes('return=representation')?out:null);
 }
 if(method==='PATCH'){
  for(const r of query())Object.assign(r,data);
  return success(null);
 }
 if(method==='DELETE'){
  const selected=new Set(query());
  db.set(table,rows.filter(r=>!selected.has(r)));return success(null);
 }
 return success(null,404);
}
function htmlText(html=''){
 return String(html).replace(/<[^>]*>/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/\s+/g,' ').trim();
}
function syntheticNvidia(messages){
 const q=String(messages?.at(-1)?.content||'');
 const norm=assistant.normalizeClientFrench(q);
 const prior=(messages||[]).filter(x=>x.role==='user').slice(0,-1).map(x=>String(x.content||'')).join(' | ');
 const lastMatch=[...prior.matchAll(/(?:real[\s-]*(?:madrid)?[\s-]*(?:barca|barcelone)|psg[\s-]*marseille)/gi)].at(-1)?.[0]||null;
 const reply=(text,buttons=[])=>({reply:text,buttons});
 if(/facebook/i.test(q))return reply('Voici notre page Facebook : '+assistant.LINKS.facebook,['channel']);
 if(/instagram/i.test(q))return reply('Le lien Instagram officiel est '+assistant.LINKS.instagram);
 if(/youtube/i.test(q))return reply('Notre chaîne YouTube est '+assistant.LINKS.youtube);
 if(/threads/i.test(q))return reply('Le compte Threads se trouve ici : '+assistant.LINKS.threads);
 if(/cineXfilms/i.test(q))return reply('Ce lien correspond à un canal de films, pas à Facebook. Notre canal pronostics : '+assistant.LINKS.channel);
 if(/canal/i.test(q))return reply('Rejoins notre canal Telegram officiel ici : '+assistant.LINKS.channel,['channel']);
 if(/pronos|pronostic|vip|pro\b|coupon/i.test(norm))return reply('Je ne peux pas confirmer des coupons pour la date demandée. Consulte les publications vérifiées sur '+assistant.LINKS.pronos,['pronos']);
 if(/installer|installation|guide.moi|pas a pas|fait|d.accord|partager|iphone|android|chrome|menu|et ensuite|et apres|code promo|je ne trouve/i.test(norm))
   return reply('**Étape 1**\n\nOuvre la page officielle : '+assistant.LINKS.installer+'.\n\n**Étape 2**\n\nClique sur le menu.', ['installer']);
 if(/lien/i.test(q))return reply('Voici le site : '+assistant.LINKS.accueil,['accueil']);
 if(/score exact|corners?|qui gagne|quel score|ce match|pour ce match/i.test(norm)){
  return reply(lastMatch
   ?'Pour '+lastMatch+', je ne peux pas confirmer un score exact ou une cote live sans source horodatée.'
   :'Je ne peux pas confirmer le score et les corners sans connaître le match précis.');
 }
 return reply(assistant.safeContextualFallback(q));
}
globalThis.fetch=async (url,opt={})=>{
 const address=String(url);
 if(address.startsWith('https://sandbox.invalid/rest/v1/'))return postgrest(address,opt);
 if(address.startsWith('https://api.telegram.org/bot')){
  const method=address.split('/').at(-1),body=JSON.parse(opt.body||'{}');
  operations.push({type:'telegram',method});
  if(method==='sendMessage'){outbound.push({chat_id:body.chat_id,html:body.text,content:htmlText(body.text),buttons:body.reply_markup?.inline_keyboard||[]});return success({ok:true,result:{message_id:messageId++,chat:{id:body.chat_id}}});}
  return success({ok:true,result:true});
 }
 if(address==='https://integrate.api.nvidia.com/v1/chat/completions'){
  const request=JSON.parse(opt.body||'{}');aiCalls.push({model:request.model,question:request.messages?.at(-1)?.content});
  const completion=syntheticNvidia(request.messages);
  return success({choices:[{message:{content:JSON.stringify(completion)},finish_reason:'stop'}]});
 }
 if(address.startsWith('https://mrxpronos.github.io/'))return success(null,404);
 throw new Error('Blocked external request in sandbox: '+address.slice(0,100));
};
assistant=await import('../index.js');

const dialogues=[
  {
    "id": 935001,
    "title": "Liens et boutons successifs",
    "messages": [
      "/start",
      "Je voudrais le lien de votre canal Telegram",
      "Et Facebook ?",
      "Et Instagram ?",
      "Je veux aussi le dossier des films",
      "Le canal Actu Foot ?",
      "/liens",
      "/bookmakers"
    ]
  },
  {
    "id": 935002,
    "title": "Installation, changement d'appareil",
    "messages": [
      "Bonjour",
      "Guide-moi pour installer le site pas à pas",
      "Je suis sur Android",
      "fait",
      "Je ne vois pas le menu",
      "Finalement je passe sur iPhone",
      "Où est le bouton Partager ?",
      "fait",
      "Et ensuite ?"
    ]
  },
  {
    "id": 935003,
    "title": "Inscription et changement de bookmaker",
    "messages": [
      "Je souhaite créer un compte Melbet",
      "Accompagne-moi étape par étape",
      "Je suis sur Chrome",
      "D'accord",
      "fait",
      "Je ne trouve pas le code promo",
      "Je préfère finalement Betwinner",
      "Reprends le guide pour Betwinner",
      "fait"
    ]
  },
  {
    "id": 935004,
    "title": "Pronos du jour et enchaînement",
    "messages": [
      "Quels pronostics sont prévus aujourd'hui ?",
      "Et pour les VIP ?",
      "Qu'est-ce qui a réellement été publié ?",
      "Et demain ?",
      "Tu as une cote vérifiée ?",
      "Donne un score exact du prochain Clasico",
      "Je préfère consulter les pronostics sur le site",
      "Et les recevoir sur ton canal ?"
    ]
  },
  {
    "id": 935005,
    "title": "Détection d'un autre canal et réseaux",
    "messages": [
      "Je veux le lien de votre Facebook",
      "https://t.me/CineXFilms_vf",
      "Ce lien est bien celui de Facebook ?",
      "Alors quel est le vrai Facebook ?",
      "Et YouTube ?",
      "Et Threads ?",
      "Je voudrais tous les réseaux sociaux",
      "Merci beaucoup"
    ]
  },
  {
    "id": 935006,
    "title": "Matchs précis et mémoire du référent",
    "messages": [
      "Que penses-tu du prochain Real Madrid-Barcelone ?",
      "Qui est favori ?",
      "Et les corners pour ce match ?",
      "Le score exact ?",
      "Parlons maintenant de PSG-Marseille",
      "Et ce match, tu prévois quoi ?",
      "Tu as une cote vérifiée pour lui ?",
      "Je préfère les résultats",
      "Le lien de l'historique ?"
    ]
  },
  {
    "id": 935007,
    "title": "Signalement et pause humaine",
    "messages": [
      "Salut",
      "Je voudrais signaler un lien cassé",
      "Le lien Instagram renvoie ailleurs",
      "Je veux parler à un responsable",
      "Est-ce qu'il a vu mon message ?",
      "Je précise que le problème concerne Facebook",
      "Merci pour ton aide"
    ]
  }
];
const scenariosExpected=58;

test('deep conversational baseline: analyse each final Telegram response, buttons and session over 7 dialogues',async()=>{
 const all=[];
 let global=0;
 for(const profile of dialogues){
  const transcript=[];
  for(let i=0;i<profile.messages.length;i++){
   const question=profile.messages[i],startOut=outbound.length,startAi=aiCalls.length;
   let error=null;
   try{
    await assistant.handleUpdate({update_id:970000+global,message:{
      message_id:5000+global,date:Math.floor(Date.now()/1000),
      chat:{id:profile.id,type:'private'},from:{id:profile.id,is_bot:false,first_name:'Dialogue'+profile.id},
      text:question
    }});
   }catch(e){error=String(e);}
   const sent=outbound.slice(startOut).filter(x=>x.chat_id===profile.id);
   const admin=outbound.slice(startOut).filter(x=>x.chat_id===999000);
   const session=store('mx_telegram_assistant_sessions').find(x=>x.chat_key===String(profile.id));
   const reply=sent.map(m=>m.content).join('\n— —\n');
   const urls=sent.flatMap(x=>x.buttons.flat().map(b=>b.url));
   const labels=sent.flatMap(x=>x.buttons.flat().map(b=>b.text));
   const anchorUrls=sent.flatMap(x=>[...x.html.matchAll(/href="([^"]+)"/g)].map(m=>m[1]));
   const call=aiCalls.length>startAi?aiCalls.at(-1):null;
   transcript.push({
     n:i+1,q:question,reply:reply.slice(0,540),
     btn:labels,btnUrls:urls,anchors:anchorUrls,mode:session?.mode||'idle',step:session?.step_number||0,
     admin:admin.length,error,aiCalled:!!call
   });
   global++;
  }
  all.push({title:profile.title,id:profile.id,turns:transcript});
  console.log('MX_DEEP_DIALOGUE '+JSON.stringify({title:profile.title,id:profile.id,turns:transcript}));
 }
 console.log('MX_DEEP_STATS '+JSON.stringify({
  conversations:all.length,messages:global,
  withButtons:all.flatMap(a=>a.turns).filter(t=>t.btn.length).length,
  withAnchors:all.flatMap(a=>a.turns).filter(t=>t.anchors.length).length,
  noReply:all.flatMap(a=>a.turns).filter(t=>!t.reply).length,
  exceptions:all.flatMap(a=>a.turns).filter(t=>!!t.error).length
 }));
 // Lire chaque réponse dans son contexte : qualité du texte, liens, référent,
 // état du guide, changement de sujet, absence de chiffres inventés.
 const flaws=[],checks=[];
 const at=(id,n)=>all.find(x=>x.id===id)?.turns.find(x=>x.n===n);
 const expect=(id,n,label,condition)=>{
   checks.push({id,n,label,pass:!!condition});
   if(!condition){const t=at(id,n);flaws.push({id,n,label,q:t?.q,reply:t?.reply,buttons:t?.btn,mode:t?.mode,step:t?.step});}
 };
 const hasButton=(id,n,url)=>at(id,n)?.btnUrls.includes(url);
 const hasAny=(id,n,part)=>at(id,n)?.reply.toLowerCase().includes(part.toLowerCase());
 const L=assistant.LINKS;
 // Navigation : chaque lien demandé est un vrai bouton, les annuaires ne sont pas
 // un pavé d'URL dans le texte et ne perdent aucun destinataire.
 expect(935001,1,'welcome_3_buttons',at(935001,1)?.btn.length===3);
 expect(935001,2,'channel_button',hasButton(935001,2,L.channel));
 expect(935001,3,'facebook_followup',hasButton(935001,3,L.facebook));
 expect(935001,4,'instagram_followup',hasButton(935001,4,L.instagram));
 expect(935001,5,'film_folder_button',hasButton(935001,5,L.folder_films));
 expect(935001,6,'actu_foot_safe_link',hasButton(935001,6,L.infos));
 expect(935001,7,'directory_all_18_buttons',at(935001,7)?.btn.length===18);
 expect(935001,7,'directory_presentation',hasAny(935001,7,'Annuaire officiel'));
 expect(935001,8,'bookmakers_all_6_buttons',at(935001,8)?.btn.length===6);
 // Guidage : la précision de l'appareil ou une question à l'étape courante
 // ne doit pas supprimer la mémoire, ni avancer sans "fait".
 for(const n of [2,3,4,5,6,7,8,9])expect(935002,n,'install_stays_guided',at(935002,n)?.mode==='guided');
 expect(935002,4,'install_advances_after_fait',at(935002,4)?.step===2);
 expect(935002,5,'install_blocked_same_step',at(935002,5)?.step===2);
 expect(935002,6,'install_switch_resets_to_iphone_1',at(935002,6)?.step===1);
 expect(935002,7,'install_safari_sharing_help',hasAny(935002,7,'Safari')&&hasAny(935002,7,'Partager'));
 expect(935002,8,'install_fait_after_switch_step_2',at(935002,8)?.step===2);
 expect(935002,9,'install_et_ensuite_keeps_step_2',at(935002,9)?.step===2);
 expect(935002,9,'install_no_unverified_installer',!hasAny(935002,9,'Lien externe non confirmé'));
 for(const n of [2,3,4,5,6,7,8,9])expect(935003,n,'signup_stays_guided',at(935003,n)?.mode==='guided');
 expect(935003,4,'signup_daccord_does_not_advance',at(935003,4)?.step===1);
 expect(935003,5,'signup_fait_advances',at(935003,5)?.step===2);
 expect(935003,6,'signup_code_promo_relevant',hasAny(935003,6,'Code promo'));
 expect(935003,7,'signup_new_bookmaker_step1',at(935003,7)?.step===1&&hasAny(935003,7,'Betwinner'));
 expect(935003,8,'signup_restart_step1',at(935003,8)?.step===1&&hasAny(935003,8,'Betwinner'));
 expect(935003,9,'signup_fait_then_step2',at(935003,9)?.step===2);
 // Pronostics, cotes et suivi court : ne pas mélanger VIP et demain.
 expect(935004,2,'vip_answer_specific',hasAny(935004,2,'VIP')&&!hasAny(935004,2,'pour demain'));
 expect(935004,3,'published_picks_uncertainty',/publi|confirm/i.test(at(935004,3)?.reply||''));
 expect(935004,4,'tomorrow_reference',hasAny(935004,4,'demain'));
 expect(935004,5,'no_invented_odds',/vérifi|confirmer|ne dispose/i.test(at(935004,5)?.reply||''));
 expect(935004,6,'no_guaranteed_score',!/score.*garanti.*[0-9]-[0-9]/i.test(at(935004,6)?.reply||''));
 expect(935004,7,'pronos_button',hasButton(935004,7,L.pronos));
 expect(935004,8,'channel_followup_button',hasButton(935004,8,L.channel));
 // Faux canal de films, puis clarification, puis différents réseaux.
 expect(935005,2,'external_telegram_explained',hasAny(935005,2,'Telegram'));
 expect(935005,3,'facebook_is_not_telegram',hasAny(935005,3,'pas vers Facebook')&&hasButton(935005,3,L.facebook));
 expect(935005,4,'true_facebook_button',hasButton(935005,4,L.facebook));
 expect(935005,5,'youtube_button',hasButton(935005,5,L.youtube));
 expect(935005,6,'threads_button',hasButton(935005,6,L.threads));
 expect(935005,7,'social_6_buttons',at(935005,7)?.btn.length===6);
 // Deux rencontres différentes : les pronoms et les relances doivent suivre
 // le match le plus récent, sans réintroduire Real-Barça après PSG-OM.
 expect(935006,1,'real_match_ack',hasAny(935006,1,'Real Madrid'));
 expect(935006,2,'fav_ref_real',hasAny(935006,2,'Real Madrid'));
 expect(935006,3,'corners_ref_real',hasAny(935006,3,'Real Madrid')&&hasAny(935006,3,'corners'));
 expect(935006,5,'new_subject_psg',hasAny(935006,5,'PSG'));
 expect(935006,6,'followup_psg',hasAny(935006,6,'PSG')&&!hasAny(935006,6,'Real Madrid'));
 expect(935006,7,'odds_ref_psg',hasAny(935006,7,'PSG')||hasAny(935006,7,'cotes'));
 expect(935006,8,'results_button',hasButton(935006,8,L.historique));
 expect(935006,9,'history_followup_button',hasButton(935006,9,L.historique));
 // Assistance : signalement puis bonne compréhension de la pause humaine.
 expect(935007,2,'report_asks_which_link',hasAny(935007,2,'Quel bouton'));
 expect(935007,3,'instagram_report_not_generic',hasAny(935007,3,'signalement'));
 expect(935007,3,'instagram_and_contact_buttons',hasButton(935007,3,L.instagram)&&hasButton(935007,3,L.contact));
 expect(935007,5,'no_fake_human_read_receipt',hasAny(935007,5,'pas de confirmation de lecture'));
 expect(935007,7,'human_pause_maintained',hasAny(935007,7,'attente'));
 // Texte final lisible : bannir les fragments de Markdown et les URL externes
 // prétendument non confirmées alors que l'annuaire les connaît.
 for(const p of all)for(const t of p.turns){
   const malformed=/Lien externe non confirmé|2\*\*|sur\s*\./i.test(t.reply);
   expect(p.id,t.n,'readable_final_output',!malformed);
 }
 console.log('MX_DEEP_QUALITY '+JSON.stringify({
   dialogues:all.length,turns:global,checked:checks.length,
   passed:checks.filter(c=>c.pass).length,failed:flaws.length,flaws
 }));
 assert.equal(all.length,7);
 assert.equal(global,scenariosExpected);
 assert.ok(all.flatMap(x=>x.turns).every(x=>!x.error),'No uncaught errors');
 assert.deepEqual(flaws,[],'Full conversational semantics and final Telegram buttons must pass');
});
