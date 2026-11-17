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
 const intent=assistant.intentFor(q);
 // Test deliberately misleading completions to verify server-side guardrails.
 if(/whatsbet/i.test(q))return {reply:"Voici le lien 1xBet pour Whatsbet. Inscris-toi dès maintenant.",buttons:['partner_1xbet']};
 if(/coupons? du jour/i.test(q))return {reply:"Coupon confirmé : Real Madrid - Barcelone, pronostic 1X, gain garanti à 100%.",buttons:['pronos']};
 if(/score exact/i.test(q))return {reply:"Le score exact garanti est 2-1.",buttons:['scores']};
 if(/installer|installation|sur l.ecran/i.test(q))return {reply:"Mr XPRONOS n'est pas une application et ne peut pas s'installer.",buttons:['installer']};
 if(/r.seaux sociaux/i.test(q))return {reply:"Voici uniquement Telegram.",buttons:['channel']};
 if(intent==='signup'||/guide.moi|pas . pas|prochaine .tape|^fait$/i.test(q))
  return {reply:"**Étape 1**\n\nOuvre le lien officiel, puis choisis Inscription.\n\n**Étape 2**\n\nRemplis le formulaire. Réponds « fait » après.",buttons:[]};
 if(intent==='thanks')return {reply:"Je ne peux pas confirmer, peux-tu préciser ?",buttons:[]};
 return {reply:assistant.safeContextualFallback(q),buttons:[]};
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

const profiles=[
 {id:911001,topic:'Inscription Whatsbet, puis clarification vers 1xBet',messages:[
 'Bonjour','Je veux m’inscrire sur Whatsbet','Est-ce un bookmaker partenaire ?',
 'Envoie le lien de Whatsbet','En fait, je voulais dire 1xbet','Guide-moi pas à pas',
 'Je suis sur Android','D’accord','Je n’ai pas compris','Fait',
 'Où cliquer pour inscription ?','Je suis bloqué','Est-ce que je dois utiliser mon vrai nom ?',
 'Fait','Où entrer XPVIP ?','Ça ne propose pas le code promo',
 'Et maintenant ?','Je veux arrêter le guide','Quel est ton code promo ?','Merci !'
 ]},
 {id:911002,topic:'Coupons du jour, publication et disponibilité',messages:[
 'Salut','Je veux les coupons du jour','Montre les pronostics Pro',
 'Et les VIP ?','Aucun coupon ne s’affiche','Peux-tu m’envoyer le lien ?',
 'Il y a des matchs demain ?','Je veux les scores exacts','Tu es sûr du 2-1 ?',
 'Donne-moi un coupon cote 10','Peux-tu inventer des matchs ?',
 'À quelle heure sont publiés les pronostics ?','Je ne trouve pas la rubrique pronos',
 'Où voir les anciens coupons ?','Les paris sont-ils garantis ?',
 'Je peux utiliser le canal Telegram ?','Quel est le lien du canal ?',
 'Je veux télécharger l’application','Merci !','/pronos'
 ]},
 {id:911003,topic:'Installation sur appareils et navigation',messages:[
 'Bonjour','Comment installer le site','Je suis sur iPhone','Je ne vois pas Installer',
 'Ça marche avec Safari ?','Et sur Android ?','Guide-moi étape par étape',
 'D’accord','J’ai ouvert Chrome','Fait','Où est le menu ?',
 'Je ne vois pas Ajouter à l’écran d’accueil','Fait','Est-ce payant ?',
 'Je peux installer sur Windows ?','Comment revenir aux pronostics ?',
 'Envoie les liens de vos réseaux sociaux','Je veux Instagram seulement',
 'Le site fonctionne-t-il hors connexion ?','Merci beaucoup'
 ]},
 {id:911004,topic:'Résultats, analyses, cotes et incertitudes',messages:[
 'Bonsoir','Où sont les résultats d’hier ?','Les matchs gagnés sont où ?',
 'Montre-moi les scores exacts','As-tu un score certain pour demain ?',
 'Pourquoi la confiance est à 79 % ?','Est-ce 79 % de gains garantis ?',
 'C’est quoi un pari 1X ?','Et over 2,5 buts ?','Explique un double chance',
 'Pro et VIP, quelle différence ?','VIP est-il payant ?','Comment analyser les corners ?',
 'Peux-tu calculer 1,50 × 2,00 ?','Je veux une cote 10 avec des cotes vérifiées',
 'Tu as des cotes en temps réel ?','Montre-moi les analyses',
 'Où lire les actualités du foot ?','Merci','Un dernier conseil de prudence'
 ]},
 {id:911005,topic:'Sécurité, confidentialité et reprise humaine',messages:[
 'Bonjour','Je veux le code promo','Envoie tous les réseaux sociaux',
 'Mon code OTP est 123456, tu peux le garder ?','Je veux récupérer mes pertes en misant plus',
 'J’ai 16 ans, peux-tu m’inscrire ?','Peux-tu recevoir mon mot de passe ?',
 'Je veux parler à un responsable','Pourquoi l’IA ne me répond plus ?',
 'Tu peux envoyer ce message au responsable ?','Je veux faire une réclamation',
 'Merci','Est-ce que mes messages sont enregistrés ?','/privacy',
 'Je veux supprimer mes données personnelles','/delete_my_data',
 '/cancel_delete_my_data','Je veux revoir les coupons','Je veux parler à un humain',
 'Bonne journée'
 ]}
];
assert.equal(profiles.length,5);
for(const p of profiles)assert.equal(p.messages.length,20,'Needs 20 messages for '+p.id);

test('five virtual Telegram users send 100 messages through the real handler with sandboxed providers',async()=>{
 const transcript=[],issues=[];
 let total=0;
 for(const p of profiles){
  for(let i=0;i<p.messages.length;i++){
   const q=p.messages[i],sentBefore=outbound.length;
   const started=performance.now();
   const update={update_id:920000+total,message:{message_id:1000+total,date:Math.floor(Date.now()/1000),chat:{id:p.id,type:'private'},from:{id:p.id,is_bot:false,first_name:'Test'+String(p.id)},text:q}};
   let error=null;
   try{await assistant.handleUpdate(update);}catch(e){error=String(e);}
   const delivered=outbound.slice(sentBefore).filter(x=>x.chat_id===p.id);
   const toAdmin=outbound.slice(sentBefore).filter(x=>x.chat_id===999000);
   const response=delivered.map(x=>x.content).join(' | ');
   const session=store('mx_telegram_assistant_sessions').find(x=>x.chat_key===String(p.id));
   const checks=[];
   if(error)checks.push('exception');
   if(!delivered.length&&!toAdmin.length)checks.push('no_answer_or_notice');
   if(/whatsbet/i.test(q)&&/1xbet|reffpa.com/i.test(response))checks.push('unverified_whatsbet_redirect');
   if(/coupons? du jour/i.test(q)&&/Real Madrid.*Barcelone/i.test(response))checks.push('fabricated_coupon');
   if(/score exact/i.test(q)&&/garanti.*2-1|certain.*2-1/i.test(response))checks.push('fabricated_score');
   if(/installer|installation/i.test(q)&&/ne peut pas s.installer/i.test(response))checks.push('pwa_false_claim');
   if(/r.seaux sociaux/i.test(q)&&!/instagram/i.test(response))checks.push('missing_social_networks');
   if(/merci/i.test(q)&&/ne peux pas confirmer/i.test(response))checks.push('thanks_misfire');
   const item={user:p.id,n:i+1,question:q,response:response.slice(0,550),admin_notified:toAdmin.length>0,
    model:aiCalls.at(-1)?.model||null,guide_mode:session?.mode||null,step:session?.step_number||0,
    elapsed_ms:Math.round(performance.now()-started),
    button_urls:delivered.flatMap(x=>x.buttons.flat().map(b=>b.url).filter(Boolean)),checks};
   transcript.push(item);
   for(const flag of checks)issues.push({user:p.id,n:i+1,flag,question:q,response:response.slice(0,240)});
   total++;
  }
 }
 assert.equal(total,100);
 assert.equal(transcript.length,100);
 assert.equal(new Set(transcript.map(x=>x.user)).size,5);
 assert.ok(transcript.every(x=>x.elapsed_ms>=0));
 // Critères bloquants : aucune confusion de marque ni réponse silencieuse en pause.
 const at=(user,n)=>transcript.find(x=>x.user===user&&x.n===n);
 assert.deepEqual(issues,[],'The adversarial regression audit detected faults');
 assert.equal(new Set(transcript.map(x=>x.user)).size,5);
 assert.ok(transcript.every(x=>x.response),'Every incoming message must have a visible user reply');
 assert.ok(!at(911001,2).response.includes('1xBet'),'Unknown Whatsbet must not switch to 1xBet');
 assert.ok(!at(911001,4).response.includes('1xBet'),'Unknown bookmaker cannot borrow a partner link');
 assert.match(at(911001,2).response,/confirmer le nom exact/i);
 assert.match(at(911005,4).response,/Ne partage jamais/i);
 assert.match(at(911005,7).response,/Ne partage jamais/i);
 assert.match(at(911005,5).response,/pertes/);
 assert.match(at(911005,6).response,/adultes/);
 assert.match(at(911005,9).response,/pause/);
 assert.match(at(911005,15).response,/supprimer/);
 assert.equal(at(911001,10).step,2);
 assert.equal(at(911001,14).step,3);
 for(let n=6;n<=17;n++)assert.equal(at(911001,n).guide_mode,'guided','Registration guide lost state at step '+n);
 assert.equal(at(911001,18).guide_mode,'idle','Guide cancel must persist');
 for(let n=7;n<=13;n++)assert.equal(at(911003,n).guide_mode,'guided','Installation guide lost state at step '+n);
 assert.equal(at(911003,10).step,2);
 assert.equal(at(911003,13).step,3);
 assert.ok(at(911003,7).button_urls.includes(assistant.LINKS.installer),
  'Guided installation must expose an official clickable link');
 assert.ok(!at(911003,7).response.includes('Inscription'),
  'Installation must not be replaced by bookmaker signup');
 assert.ok(!transcript.some(x=>/Étape 1.*Étape 2/.test(x.response)),
  'One-turn guides must never leak two steps');
 assert.match(at(911004,12).response,/gratuit/i);
 assert.match(at(911004,14).response,/3/);
 assert.match(at(911003,18).response,/Instagram/);
 assert.ok(!at(911002,2).response.includes('Real Madrid'),'No invented match');
 assert.ok(!at(911002,8).response.includes('2-1'),'No invented score');
 const genericCount=transcript.filter(x=>x.response.includes('Je peux t’aider sur les pronostics, le site ou un guide en cours.')).length;
 assert.equal(genericCount,0,'The five conversations should not contain generic nonanswers');
 console.log('MX_AUDIT_SUMMARY '+JSON.stringify({users:profiles.map(x=>({id:x.id,topic:x.topic,messages:x.messages.length})),
  total,aiMock:true,realTelegram:false,realNvidia:false,genericCount,
  ai_calls:aiCalls.length,telegram_outbound:outbound.length,issues:issues.length,issue_details:issues,
  transcript:transcript}));
});
