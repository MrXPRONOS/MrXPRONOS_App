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


function update(id,userId,question){
 return {update_id:960000+id,message:{message_id:4000+id,date:Math.floor(Date.now()/1000),
 chat:{id:userId,type:'private'},from:{id:userId,is_bot:false,first_name:'TestHub'},
 text:question}};
}
function received(fromIndex,chatId){
 return outbound.slice(fromIndex).filter(x=>x.chat_id===chatId);
}
function linkSet(sent){
 const links=sent.flatMap(m=>[
  ...m.buttons.flat().map(x=>x.url),
  ...[...m.html.matchAll(/href="([^"]+)"/g)].map(x=>x[1].replace(/&amp;/g,'&'))
 ]);
 return new Set(links);
}
test('link hub: real Telegram handler sends welcome, complete links, folder, bookmakers, news and previews',async()=>{
 const subscriber=9961001,admin=999000;
 const steps=['/start','/liens','/dossier','/actufoot','/bookmakers','/accueil'];
 const traces=[];
 for(let i=0;i<steps.length;i++){
  const before=outbound.length;
  await assistant.handleUpdate(update(i,subscriber,steps[i]));
  const messages=received(before,subscriber);
  assert.ok(messages.length,'No response to '+steps[i]);
  traces.push({cmd:steps[i],messages});
 }
 const welcome=traces[0].messages;
 assert.equal(welcome.length,1,'First /start sends one welcome message');
 const w=welcome[0].content;
 assert.match(w,/Bienvenue chez Mr XPRONOS/);
 assert.match(w,/\/liens/);
 const welcomeLinks=linkSet(welcome);
 for(const u of [assistant.LINKS.pronos,assistant.LINKS.installer,assistant.LINKS.channel])
  assert.ok(welcomeLinks.has(u),'New subscriber missing '+u);
 assert.equal(welcomeLinks.size,3,'Welcome must show exactly three main links');
 const all=traces[1].messages;
 const allLinks=linkSet(all);
 const expected=assistant.officialLinksUrls();
 for(const u of expected)assert.ok(allLinks.has(u),'Missing hub link '+u);
 assert.ok(allLinks.has(assistant.LINKS.folder_films),'Official folder missing');
 assert.equal(expected.length,18);
 assert.ok(all[0].content.includes('Bookmakers partenaires'));
 assert.match(all[0].content,/canal Telegram Actu Foot/i);
 assert.ok(!all[0].content.includes('lien non vérifié retiré'));
 assert.equal(all[0].buttons.flat().length,18,'The entire official hub must use Telegram buttons');
 assert.equal(all[0].buttons.length,9,'Two buttons per row, readable on phones');
 assert.ok(traces[2].messages[0].buttons.flat().some(b=>b.url===assistant.LINKS.folder_films));
 assert.ok(traces[3].messages[0].buttons.flat().some(b=>b.url===assistant.LINKS.infos),
  'Missing Actu Foot channel must fallback to verified website news URL');
 assert.match(traces[3].messages[0].content,/adresse.*pas encore confirmée/i);
 const book=linkSet(traces[4].messages);
 assert.equal(book.size,6,'Six officially configured partner URLs');
 const a=traces[5].messages[0];
 assert.match(a.content,/Bienvenue chez Mr XPRONOS/);
 assert.equal(linkSet([a]).size,3);
 const before=outbound.length;
 await assistant.handleUpdate(update(6,admin,'/testaccueil'));
 const preview=received(before,admin);
 assert.equal(preview.length,1);
 assert.match(preview[0].content,/Aperçu du nouvel abonné/);
 assert.match(preview[0].content,/Bienvenue chez Mr XPRONOS/);
 assert.equal(linkSet(preview).size,3);
 const callsBefore=operations.filter(x=>x.method==='setMyCommands').length;
 const beforeSync=outbound.length;
 await assistant.handleUpdate(update(7,admin,'/synccommandes'));
 const afterSync=operations.filter(x=>x.method==='setMyCommands').length;
 assert.equal(afterSync,callsBefore+1,'Admin must refresh Telegram shortcut menu');
 assert.match(received(beforeSync,admin)[0]?.content||'',/Menu Telegram mis à jour/);
 assert.ok(assistant.telegramShortcutCommands().some(x=>x.command==='liens'));
 assert.ok(assistant.telegramShortcutCommands().some(x=>x.command==='accueil'));
 console.log('MX_HUB_AUDIT '+JSON.stringify({
  tested:steps.concat('/testaccueil','/synccommandes'),
  hubLinks:expected.length,
  firstWelcomeButtons:welcomeLinks.size,
  previewButtons:linkSet(preview).size,
  folder:assistant.LINKS.folder_films,
  footballNewsFallback:assistant.LINKS.infos,
  partnerCount:book.size,
  lastStatus:'PASS'
 }));
});
test('unsafe URL stays excluded; /liens is understandable',()=>{
 const sample=assistant.buildTelegramMessage('Clique ici : https://malicious.invalid/bet');
 assert.equal(sample.reply_markup,undefined);
 assert.ok(!sample.text.includes('https://malicious.invalid'));
 assert.match(sample.text,/\/liens/);
 assert.equal(assistant.intentFor('donne tous les liens'),'links');
 assert.equal(assistant.intentFor('liste des bookmakers'),'partners');
 assert.equal(assistant.intentFor('dossier Mr XPRONOS F'),'folder');
});


test('REGRESSION: rendering keeps our channel clickable after a client sends a different Telegram channel',()=>{
 const question='https://t.me/CineXFilms_vf';
 const generated='Ce lien mène vers un canal films/séries, pas vers Mr XPRONOS.\n\n'+
   'Notre canal officiel : https://t.me/mrxpronosfr\n\nBesoin d’un prono, des résultats ou d’autre chose ?';
 const intent=assistant.intentFor(question);
 const destinations=assistant.contextualDestinations(question,[],[],intent);
 assert.deepEqual(destinations,[],'Original no-context scenario reproduced');
 const view=assistant.buildTelegramMessage(generated,{allowedUrls:destinations});
 assert.match(view.text,/Notre canal officiel/);
 assert.match(view.text,/<a href="https:\/\/t\.me\/mrxpronosfr">/);
 assert.ok(!view.text.includes('Lien externe non confirmé'),view.text);
 assert.ok(!view.text.includes('lien non vérifié retiré'));
 assert.ok(view.reply_markup?.inline_keyboard?.flat().some(b=>b.url===assistant.LINKS.channel),
  'An explicitly offered official channel must be a Telegram button');
});

test('Official URLs survive contextual button restrictions, unknown links do not',()=>{
 const urls=[
  assistant.LINKS.channel,assistant.LINKS.telegram,
  assistant.LINKS.pronos,assistant.LINKS.installer,
  assistant.LINKS.infos,assistant.LINKS.facebook,
  assistant.LINKS.instagram,assistant.LINKS.youtube,
  assistant.LINKS.threads,assistant.LINKS.whatsapp,
  assistant.LINKS.folder_films
 ];
 for(const url of urls){
  const view=assistant.buildTelegramMessage('Voici le lien officiel : '+url,{allowedUrls:[]});
  assert.ok(view.reply_markup?.inline_keyboard?.flat().some(b=>b.url===url),
    'Expected named official link as a button: '+url+' : '+view.text);
  assert.ok(!view.text.includes('Lien externe non confirmé'),'False warning for '+url);
 }
 const unknown=assistant.buildTelegramMessage('Notre canal ? https://t.me/unknown_external_channel_42',{allowedUrls:[]});
 assert.match(unknown.text,/Lien externe non confirmé/);
 assert.ok(!unknown.text.includes('<a href='));
 const wrongBrand=assistant.PARTNER_LINKS['1xbet'];
 const blocked=assistant.buildTelegramMessage('Voici un partenaire : '+wrongBrand,{allowedUrls:[]});
 assert.ok(!blocked.text.includes('<a href=')&&!blocked.reply_markup,'Unsolicited bookmaker remains blocked');
 const permitted=assistant.buildTelegramMessage('Partenaire autorisé : '+wrongBrand,{allowedUrls:[wrongBrand]});
 assert.ok(permitted.reply_markup?.inline_keyboard?.flat().some(b=>b.url===wrongBrand));
});

test('Final rendered responses remain readable with restrictive contextual URL budget',()=>{
 const cases=[
  {label:'official channel',answer:'Notre canal officiel : '+assistant.LINKS.channel,allowedUrls:[]},
  {label:'Facebook',answer:'Voici notre Facebook : '+assistant.LINKS.facebook,allowedUrls:[assistant.LINKS.instagram]},
  {label:'dossier',answer:'Dossier Mr XPRONOS F : '+assistant.LINKS.folder_films,allowedUrls:[]},
  {label:'installation',answer:'Installer le site : '+assistant.LINKS.installer,allowedUrls:[]}
 ];
 for(const item of cases){
  const msg=assistant.buildTelegramMessage(item.answer,{allowedUrls:item.allowedUrls});
  assert.ok(msg.reply_markup?.inline_keyboard?.flat().length===1,item.label+': '+msg.text);
  assert.ok(!/lien externe non confirmé|lien non vérifié retiré/i.test(msg.text),item.label+': '+msg.text);
 }
});
