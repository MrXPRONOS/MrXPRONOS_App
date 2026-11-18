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


const baseFetch=globalThis.fetch;
let asrText='bonjour';
globalThis.fetch=async (url,opt={})=>{
 const address=String(url);
 if(address.startsWith('https://api.telegram.org/bot')&&address.endsWith('/getFile'))
  return success({ok:true,result:{file_path:'voice/test.ogg',file_size:80}});
 if(address.startsWith('https://api.telegram.org/file/bot'))
  return {ok:true,status:200,headers:{get:()=>String(80)},arrayBuffer:async()=>new Uint8Array(80).fill(1).buffer};
 if(address.startsWith('https://asr.sandbox.invalid/'))
  return success({text:asrText,language:'fr'});
 if(address==='https://integrate.api.nvidia.com/v1/chat/completions'){
  const body=JSON.parse(opt.body||'{}');
  const q=String(body.messages?.at(-1)?.content||'');
  if(/histoire du poisson lune|idee du weekend/i.test(q))
    return success({choices:[{message:{content:JSON.stringify({reply:'',buttons:[],scope:'out_of_scope'})},finish_reason:'stop'}]});
  if(/wopti wopti blabla/i.test(q))
    return success({choices:[{message:{content:JSON.stringify({reply:'',buttons:[],scope:'unclear'})},finish_reason:'stop'}]});
 }
 return baseFetch(url,opt);
};

const samples=[
 ['Je veux les coupons du jour','in_scope'],
 ['Tu peux me donner un score exact ?','in_scope'],
 ['Comment créer un compte Melbet ?','in_scope'],
 ['Comment installer le site sur Android ?','in_scope'],
 ['Je veux le dossier Mr XPRONOS F','in_scope'],
 ['Je cherche une page Facebook de Mr XPRONOS','in_scope'],
 ['Je veux savoir comment coder un bot de pronostics','in_scope'],
 ['Quel temps fera-t-il demain à Lomé ?','out_of_scope'],
 ['Donne une recette de riz au gras','out_of_scope'],
 ['Aide-moi à écrire mon CV','out_of_scope'],
 ['Je veux faire de la musculation','out_of_scope'],
 ['Mon téléphone est en panne','out_of_scope'],
 ['Explique les cryptomonnaies','out_of_scope'],
 ['Quel visa pour voyager en France ?','out_of_scope'],
 ['Tu peux m’aider à installer une application Windows ?','unknown'],
 ['Combien coûte un terrain à côté de Lomé ?','out_of_scope'],
 ['Je cherche un conseil pour élever des poulets','out_of_scope'],
 ['Je veux parler de mes problèmes de santé','out_of_scope'],
 ['Donne-moi le pronostic du match de tennis Nadal Djokovic','out_of_scope'],
 ['Tu peux m\'aider à installer Telegram sur Android ?','out_of_scope'],
 ['Comment installer notre site sur Android ?','in_scope'],
 ['Comment installer Telegram pour recevoir les pronostics ?','in_scope'],
 ['Donne-moi le prix du Bitcoin pour payer 1xbet','in_scope'],
 ['Quel est le meilleur iPhone ?','out_of_scope'],
 ['Tu as des conseils ?','unknown'],
 ['...','unclear'],
 ['bonjour','in_scope']
];

test('scope classification: conservative rule engine does not misroute known topics',()=>{
 const mistakes=[];
 for(const [question,expected] of samples){
   const got=assistant.classifyClientScope(question).scope;
   if(got!==expected)mistakes.push({question,expected,got});
 }
 assert.deepEqual(mistakes,[]);
});

test('real Telegram handler: silent off-topic alerts, clear voice retry request, and continued conversations',async()=>{
 let serial=0;
 const transcript=[];
 const idAdmin=999000;
 const send=async (id,question,{voice=false}={})=>{
   const before=outbound.length;
   const update={update_id:992000+serial,message:{
     message_id:5000+serial,chat:{id,type:'private'},date:Math.floor(Date.now()/1000),
     from:{id,is_bot:false,first_name:'Scenario'},
     ...(voice?{voice:{file_id:'voice-'+serial,file_size:80,mime_type:'audio/ogg'}}:{text:question})
   }};
   serial++;
   let error;
   try{await assistant.handleUpdate(update);}catch(e){error=String(e);}
   const yours=outbound.slice(before).filter(m=>m.chat_id===id);
   const admin=outbound.slice(before).filter(m=>m.chat_id===idAdmin);
   const result={id,question:voice?'[vocal]':question,reply:yours.map(m=>m.content).join(' | '),
     admin:admin.map(m=>m.content).join(' | '),buttons:yours.flatMap(m=>m.buttons.flat().map(b=>b.text)),error};
   transcript.push(result);
   return result;
 };
 const off=await send(970011,'Peux-tu me dire la météo à Lomé demain ?');
 assert.equal(off.reply,'','No welcome nor automatic reply when first message is off-topic');
 assert.match(off.admin,/QUESTION HORS DOMAINE/);
 assert.match(off.admin,/970011/);
 assert.match(off.admin,/météo|meteo/i);
 assert.match(off.admin,/\/reply 970011/);
 const inScope=await send(970011,'Je veux les pronostics du jour');
 assert.match(inScope.reply,/Bienvenue chez Mr XPRONOS/);
 assert.ok(inScope.buttons.includes('⚽ Voir les pronostics'));
 assert.equal(inScope.admin,'','Return to domain requires no alert');
 const again=await send(970011,'Comment cuisiner du riz au gras ?');
 assert.equal(again.reply,'','Off-topic does not receive an AI answer');
 assert.match(again.admin,/QUESTION HORS DOMAINE/);
 const comeback=await send(970011,'Et les coupons VIP ?');
 assert.ok(comeback.reply,'Relevant followup after an off-topic message must work');
 assert.equal(comeback.admin,'');
 const gibberish=await send(970012,'...');
 assert.match(gibberish.reply,/pas bien compris ton message/i);
 assert.equal(gibberish.admin,'');
 const typo=await send(970013,'Bonjour');
 assert.ok(typo.reply);
 assert.equal(typo.admin,'');
 const privacy=await send(970014,'Je veux supprimer mes données personnelles');
 assert.match(privacy.reply,/confidentialit|donn.e|supprim/i);
 assert.equal(privacy.admin,'');
 // The first voice test deliberately has NO transcription provider.
 // Force both credentials off to avoid inherited CI settings contaminating it.
 const savedNvidia=process.env.MX_ASSISTANT_NVIDIA_KEY;
 const savedAsr=process.env.MX_ASSISTANT_ASR_URL;
 process.env.MX_ASSISTANT_ASR_URL='';
 process.env.MX_ASSISTANT_NVIDIA_KEY='';
 const newVocal=await send(970015,'',{voice:true});
 process.env.MX_ASSISTANT_NVIDIA_KEY=savedNvidia;
 process.env.MX_ASSISTANT_ASR_URL=savedAsr||'';
 assert.equal(newVocal.reply.replace(/\s+/g,' ').trim(),assistant.VOICE_NOT_UNDERSTOOD_REPLY);
 assert.equal(newVocal.admin,'');
 const afterVocal=await send(970015,'Je veux le code promo');
 assert.match(afterVocal.reply,/XPVIP/);
 assert.equal(afterVocal.admin,'');
 process.env.MX_ASSISTANT_ASR_URL='https://asr.sandbox.invalid/v1/audio/transcriptions';
 process.env.MX_ASSISTANT_ASR_KEY='sandbox-asr-key';
 // Ambiguous phonetic brand: ASR returned content, but its quality is flagged uncertain.
 asrText='Bedclicker';
 const uncertain=await send(970016,'',{voice:true});
 assert.equal(uncertain.reply.replace(/\s+/g,' ').trim(),assistant.VOICE_NOT_UNDERSTOOD_REPLY);
 assert.ok(!uncertain.reply.includes('J’ai compris'),uncertain.reply);
 assert.equal(uncertain.admin,'');
 asrText='Je voudrais une recette de riz avec des légumes';
 const offVocal=await send(970017,'',{voice:true});
 assert.equal(offVocal.reply,'','Clearly unrelated *understood* voice should be referred silently');
 assert.match(offVocal.admin,/QUESTION HORS DOMAINE/);
 assert.match(offVocal.admin,/Vocal transcrit/);
 process.env.MX_ASSISTANT_ASR_URL='';
 const semantic=await send(970018,'Raconte moi une histoire du poisson lune');
 assert.equal(semantic.reply,'');
 assert.match(semantic.admin,/QUESTION HORS DOMAINE/);
 const unclear=await send(970019,'wopti wopti blabla');
 assert.match(unclear.reply,/pas bien compris ton message/);
 assert.equal(unclear.admin,'');
 const sessions=store('mx_telegram_assistant_chats');
 assert.ok(!sessions.some(x=>x.chat_key==='970011'&&x.paused===true),'Do not pause off-topic clients');
 const userHistory=store('mx_telegram_assistant_messages').filter(x=>x.chat_key==='970011');
 assert.ok(userHistory.some(x=>x.role==='user'&&/météo|meteo/i.test(x.content)),'Owner gets accessible history');
 assert.ok(!userHistory.some(x=>x.role==='assistant'&&/météo|meteo/i.test(x.content)),'No fake bot reply logged');
 const issues=transcript.filter(x=>x.error);
 console.log('MX_SCOPE_ROUTING_AUDIT '+JSON.stringify({
   messages:transcript.length,offTopicAlerts:transcript.filter(x=>x.admin.includes('QUESTION HORS DOMAINE')).length,
   silent:transcript.filter(x=>!x.reply).length,errors:issues,
   voiceRetries:transcript.filter(x=>x.reply.includes('ton vocal')).length,
   sample:transcript.map(x=>({q:x.question,bot:x.reply.slice(0,160),admin:x.admin.slice(0,90)}))
 }));
 assert.deepEqual(issues,[]);
});
