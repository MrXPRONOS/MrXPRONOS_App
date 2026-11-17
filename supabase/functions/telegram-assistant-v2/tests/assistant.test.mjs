import test from "node:test";
import assert from "node:assert/strict";
import {intentFor,publishedPicks,exactScorePicks,handleRequest,eligibleBusinessMessage,LINKS,buildTelegramMessage,telegramHtml,buttonForUrl,PROJECT_KNOWLEDGE,knowledgePrompt,responseLinks,PARTNER_LINKS,partnerFromMessage,providerChoiceFromHistory,signupMessage,guidanceFollowup,sitemapUrls,pageForQuestion,NVIDIA_MODELS,runNvidiaFailover,parseAiReply,aiButtons,assistantFacts,aiLinkCatalog,contextualPresentation,contextualDestinations} from "../index.js";

test("orientation des messages",()=>{
 assert.equal(intentFor("Je veux les coupons du jour"),"pronos");
 assert.equal(intentFor("Top scores exacts"),"scores");
 assert.equal(intentFor("Comment rejoindre les canaux ?"),"canaux");
 assert.equal(intentFor("Je veux parler à un responsable"),"human");
 assert.equal(intentFor("Bonjour"),"welcome");
});
test("seules les selections a venir sont proposees",()=>{
 const now=new Date("2026-11-07T05:00:00Z");
 const feed={matches:[
 {date:"2026-11-07",event_date:"2026-11-07T20:00:00Z",category:"pro",recommendation_eligible:true,home_team:"A",away_team:"B",prediction:{confidence:.82}},
 {date:"2026-11-07",event_date:"2026-11-07T03:00:00Z",category:"vip",recommendation_eligible:true,home_team:"C",away_team:"D",prediction:{confidence:.94}},
 {date:"2026-11-07",event_date:"2026-11-07T21:00:00Z",category:"vip",is_finished:true,recommendation_eligible:true,home_team:"E",away_team:"F",prediction:{confidence:.95}}
 ]};
 assert.equal(publishedPicks(feed,now).length,1);
});
test("filtrage des scores exacts expirés",()=>{
 const data={date:"2026-11-07",status:"published",simple:[{home:"A",away:"B",score:"1:0",kickoff_utc:"2026-11-07T20:00:00Z",probability:.09}]};
 assert.equal(exactScorePicks(data,new Date("2026-11-07T05:00:00Z")).length,1);
 assert.equal(exactScorePicks(data,new Date("2026-11-07T22:00:00Z")).length,0);
});
test("endpoint en attente des secrets ferme",async()=>{
 const r=await handleRequest(new Request("https://example.org",{method:"POST",body:"{}"}));
 assert.equal(r.status,503);
});
test("liens publics",()=>assert.equal(LINKS.telegram,"https://t.me/mr_xpronos"));

test("routage conseils et coupons via commandes",()=>{
 assert.equal(intentFor("/coupons"),"pronos");
 assert.equal(intentFor("/conseils"),"conseil");
 assert.equal(intentFor("Comment analyser un match ?"),"conseil");
});
test("Business : propriétaire, droits, validité temporelle et destinataire",()=>{
 const now=Date.parse("2026-11-14T20:00:00Z");
 const base={business_connection_id:"bc123",chat:{type:"private",id:9002},from:{id:9002,is_bot:false},date:Math.floor((now-60000)/1000)};
 const connection={id:"bc123",is_enabled:true,user:{id:42},rights:{can_reply:true}};
 assert.equal(eligibleBusinessMessage(base,connection,42,now),true);
 assert.equal(eligibleBusinessMessage(base,{...connection,is_enabled:false},42,now),false);
 assert.equal(eligibleBusinessMessage(base,{...connection,rights:{can_reply:false}},42,now),false);
 assert.equal(eligibleBusinessMessage(base,connection,99,now),false);
 assert.equal(eligibleBusinessMessage({...base,from:{id:42}},connection,42,now),false);
 assert.equal(eligibleBusinessMessage({...base,date:Math.floor((now-25*3600000)/1000)},connection,42,now),false);
 assert.equal(eligibleBusinessMessage({...base,chat:{type:"group",id:9002}},connection,42,now),false);
});

test("formatage Telegram : gras, italique, barré, souligné, spoiler et citation",()=>{
 const rich=telegramHtml("**Gras** *italique* ~~barré~~ __souligné__ ||secret||\n> Une citation");
 assert.match(rich,/<b>Gras<\/b>/);
 assert.match(rich,/<i>italique<\/i>/);
 assert.match(rich,/<s>barré<\/s>/);
 assert.match(rich,/<u>souligné<\/u>/);
 assert.match(rich,/<tg-spoiler>secret<\/tg-spoiler>/);
 assert.match(rich,/<blockquote>Une citation<\/blockquote>/);
});
test("HTML hostile est échappé",()=>{
 const rich=telegramHtml("<script>alert('x')</script> & **OK**");
 assert.ok(!rich.includes("<script>"));
 assert.ok(rich.includes("&lt;script&gt;"));
 assert.ok(rich.includes("&amp; <b>OK</b>"));
});
test("liens officiels remplacés par des boutons dédupliqués",()=>{
 const body=buildTelegramMessage("Pronos : "+LINKS.pronos+"\nEncore : "+LINKS.pronos);
 assert.equal(body.reply_markup.inline_keyboard.length,1);
 assert.equal(body.reply_markup.inline_keyboard[0][0].url,LINKS.pronos);
 assert.equal(body.reply_markup.inline_keyboard[0][0].style,"primary");
 assert.ok(!body.text.includes("https://"));
 assert.ok(!body.text.includes("Clique sur le bouton"));
});
test("boutons couleurs et label contextuels",()=>{
 assert.equal(buttonForUrl(LINKS.conseils).style,"success");
 assert.equal(buttonForUrl(LINKS.contact,"Réclamation urgente").style,"danger");
 assert.equal(buttonForUrl(LINKS.accueil).style,"primary");
});
test("ne jamais envoyer de lien externe non vérifié",()=>{
 const bad=buildTelegramMessage("Clique : https://evil.invalid/surprise");
 assert.equal(bad.reply_markup,undefined);
 assert.ok(!bad.text.includes("https://evil.invalid"));
});
test("liens Markdown officiels deviennent aussi des boutons",()=>{
 const body=buildTelegramMessage("[Retrouver les pronostics]("+LINKS.pronos+")");
 assert.equal(body.reply_markup.inline_keyboard[0][0].url,LINKS.pronos);
 assert.ok(!body.text.includes("]("));
});
test("commande de démonstration du formatage",()=>{
 assert.equal(intentFor("/format"),"format");
 assert.equal(intentFor("/apercu"),"format");
 assert.equal(intentFor("/forme"),"format");
 assert.equal(intentFor("/form"),"format");
 assert.equal(intentFor("/format@AssistantTestBot"),"format");
});

test("mémoire : faits officiels du projet",()=>{
 assert.equal(PROJECT_KNOWLEDGE.promo,"XPVIP");
 assert.match(PROJECT_KNOWLEDGE.categories,/gratuitement/);
 assert.match(PROJECT_KNOWLEDGE.confidence,/79 %/);
 assert.match(PROJECT_KNOWLEDGE.schedule,/aucun nombre ni coupon quotidien garanti/);
 assert.ok(knowledgePrompt().includes("mrxpronosfr"));
 assert.equal(LINKS.channel,"https://t.me/mrxpronosfr");
});
test("FAQ précise : code, accès, catégories, fréquence et confiance",()=>{
 assert.equal(intentFor("C'est quoi ton code promo ?"),"bonus");
 assert.equal(intentFor("Les pronostics sont gratuits ?"),"access");
 assert.equal(intentFor("Quelle différence entre Pro et VIP ?"),"categories");
 assert.equal(intentFor("Des coupons chaque jour ?"),"schedule");
 assert.equal(intentFor("Que signifie 79% de confiance ?"),"method");
});
test("aucun bouton décoratif sur les réponses simples",()=>{
 for(const [q,category] of [
  ["bonjour","welcome"],["Quel est le code promo ?","bonus"],
  ["Les pronostics sont gratuits ?","access"],
  ["Quels conseils pour analyser un match ?","conseil"],
  ["Merci","general"],["Je veux parler à un responsable","human"]]){
   assert.deepEqual(responseLinks(category,q),[],q);
   const body=buildTelegramMessage("Réponse informative "+LINKS.accueil,{allowedUrls:responseLinks(category,q)});
   assert.equal(body.reply_markup,undefined,q);
   assert.ok(!body.text.includes("https://"),q);
 }
});
test("boutons contextuels : coupons, scores, résultats, canal, bonus",()=>{
 const examples=[
  ["pronos","Je veux les coupons du jour",LINKS.pronos],
  ["scores","Montre les scores exacts",LINKS.scores],
  ["resultats","Montre les résultats",LINKS.historique],
  ["canaux","Comment rejoindre votre canal ?",LINKS.channel],
  ["bonus","Où trouver les offres bonus ?",LINKS.bonus]
 ];
 for(const [intent,q,url] of examples) {
  const urls=responseLinks(intent,q);
  assert.ok(urls.includes(url),q);
  const view=buildTelegramMessage("Accès : "+url,{allowedUrls:urls});
  assert.equal(view.reply_markup.inline_keyboard[0][0].url,url);
 }
});
test("les boutons conseils ne sont pas automatiques",()=>{
 assert.deepEqual(responseLinks("conseil","Comment analyser un match ?"),[]);
 assert.deepEqual(responseLinks("conseil","Donne-moi le lien du guide"),[LINKS.conseils]);
});
test("pas de texte promotionnel sous les boutons",()=>{
 const result=buildTelegramMessage("Voici les pronostics : "+LINKS.pronos,{allowedUrls:[LINKS.pronos]});
 assert.equal(result.reply_markup.inline_keyboard.length,1);
 assert.ok(!result.text.includes("Clique sur le bouton"));
});

test("accusés de réception : merci et d'accord",()=>{
 assert.equal(intentFor("Merci !"),"thanks");
 assert.equal(intentFor("merci beaucoup"),"thanks");
 assert.equal(intentFor("daccord"),"ack");
});
test("intention inscription et lien partenaire",()=>{
 assert.equal(intentFor("Je veux m'inscrire sur 1xbet aide moi"),"signup");
 assert.equal(intentFor("ouvrir un compte Melbet"),"signup");
 assert.equal(intentFor("Donne ton lien affilié Betwinner"),"partner");
 assert.equal(partnerFromMessage("sur 1xbet"),"1xbet");
 assert.equal(partnerFromMessage("Melbet"),"melbet");
 assert.equal(partnerFromMessage("Linebet"),"linebet");
 assert.equal(partnerFromMessage("Alicenet"),null);
});
test("sources exactes : URL partenaire 1xbet et code XPVIP",()=>{
 assert.equal(PARTNER_LINKS["1xbet"],"https://reffpa.com/L?tag=d_2054511m_1573c_&site=2054511&ad=1573");
 const reply=signupMessage("1xbet");
 assert.match(reply,/Inscription 1xBet/);
 assert.match(reply,/XPVIP/);
 assert.match(reply,/18\+/);
 assert.ok(reply.includes(PARTNER_LINKS["1xbet"]));
});
test("pas de lien inventé pour un partenaire inconnu",()=>{
 const reply=signupMessage(null);
 assert.ok(reply.includes("Sur quel bookmaker"));
 assert.ok(!reply.includes("https://"));
});
test("boutons partenaires uniquement pour demandes pertinentes",()=>{
 const link=PARTNER_LINKS["1xbet"];
 assert.deepEqual(responseLinks("signup","Je veux m'inscrire sur 1xbet"),[link]);
 const body=buildTelegramMessage(signupMessage("1xbet"),{allowedUrls:[link]});
 assert.equal(body.reply_markup.inline_keyboard[0][0].url,link);
 assert.ok(!body.text.includes("https://"));
 assert.deepEqual(responseLinks("thanks","Merci !"),[]);
});
test("sitemap restreint aux pages officielles",()=>{
 const xml='<urlset><url><loc>https://mrxpronos.github.io/MrXPRONOS_App/pronos.html</loc></url><url><loc>https://external.example/evil</loc></url><url><loc>javascript:alert(1)</loc></url><url><loc>https://mrxpronos.github.io/MrXPRONOS_App/pronos.html</loc></url></urlset>';
 assert.deepEqual(sitemapUrls(xml),[LINKS.pronos]);
 assert.equal(pageForQuestion("Où lire les analyses ?"),LINKS.analyses);
 assert.deepEqual(responseLinks("site_nav","plan du site"),[LINKS.sitemap]);
});
test("suivi d'inscription à l'étape suivante",()=>{
 const history=[{role:"user",content:"je veux m'inscrire sur 1xbet"},{role:"assistant",content:"Inscription 1xBet : 1. Ouvre le lien"}];
 const followup=guidanceFollowup("Ensuite ?",history);
 assert.ok(followup && followup.includes("Inscription"));
 assert.equal(guidanceFollowup("Merci",history),null);
});
test("pronostic dupliqué sur le même match supprimé",()=>{
 const now=new Date("2026-11-17T01:00:00Z");
 const example={date:"2026-11-17",event_date:"2026-11-17T20:00:00Z",category:"pro",recommendation_eligible:true,home_team:"Kuwait",away_team:"Honduras",prediction:{confidence:.85,prediction:"1X"}};
 assert.equal(publishedPicks({matches:[example,{...example,category:"vip",prediction:{confidence:.89,prediction:"1X"}}]},now).length,1);
});


test("priorité NVIDIA : 10 modèles fixes et distincts",()=>{
 assert.equal(NVIDIA_MODELS.length,10);
 assert.equal(new Set(NVIDIA_MODELS).size,10);
 assert.deepEqual(NVIDIA_MODELS.slice(0,3),[
  "minimaxai/minimax-m3.1-flash",
  "nvidia/nemotron-3-ultra-550b-a55b",
  "nvidia/nemotron-3.5-super-vl-120b-a12b"
 ]);
 assert.equal(NVIDIA_MODELS.at(-1),"poolside/laguna-xs-2.1");
});
test("NVIDIA : premier modèle fonctionnel choisi immédiatement",async()=>{
 const called=[];
 const result=await runNvidiaFailover({
  messages:[{role:"user",content:"Bonjour"}],apiKey:"fake-local-key",
  signalFactory:()=>undefined,
  fetchImpl:async (_url,options)=>{
    const body=JSON.parse(options.body);
    called.push(body.model);
    assert.equal(body.reasoning_effort,undefined);
    assert.ok(body.max_tokens>=1000);
    return {ok:true,status:200,json:async()=>({choices:[{message:{content:"Bonjour !"},finish_reason:"stop"}]})};
  }
 });
 assert.equal(result.text,"Bonjour !");
 assert.equal(result.model,NVIDIA_MODELS[0]);
 assert.deepEqual(called,[NVIDIA_MODELS[0]]);
 assert.deepEqual(result.attempts,[{model:NVIDIA_MODELS[0],status:"ok"}]);
});
test("NVIDIA : 400 et réponse vide entraînent passage au modèle suivant",async()=>{
 const called=[];
 const result=await runNvidiaFailover({
  messages:[{role:"user",content:"Bonjour"}],apiKey:"fake-local-key",
  signalFactory:()=>undefined,
  fetchImpl:async (_url,options)=>{
    const model=JSON.parse(options.body).model;called.push(model);
    if(called.length===1) return {ok:false,status:400};
    if(called.length===2) return {ok:true,status:200,json:async()=>({choices:[{message:{content:null},finish_reason:"length"}]})};
    return {ok:true,status:200,json:async()=>({choices:[{message:{content:[{type:"text",text:"Réponse du troisième modèle."}]},finish_reason:"stop"}]})};
  }
 });
 assert.equal(result.model,NVIDIA_MODELS[2]);
 assert.deepEqual(called,NVIDIA_MODELS.slice(0,3));
 assert.deepEqual(result.attempts.map(x=>x.status),["http_400","empty_length","ok"]);
});
test("NVIDIA : 403, 429 et timeout ne bloquent pas les secours",async()=>{
 let count=0;
 const result=await runNvidiaFailover({
  messages:[{role:"user",content:"test"}],apiKey:"fake-local-key",
  signalFactory:()=>undefined,
  fetchImpl:async()=>{
    count++;
    if(count===1) return {ok:false,status:403};
    if(count===2) return {ok:false,status:429};
    if(count===3) throw Object.assign(new Error("slow"),{name:"TimeoutError"});
    return {ok:true,status:200,json:async()=>({choices:[{message:{content:"OK"},finish_reason:"stop"}]})};
  }
 });
 assert.equal(result.model,NVIDIA_MODELS[3]);
 assert.deepEqual(result.attempts.map(x=>x.status),["http_403","http_429","timeout","ok"]);
});
test("NVIDIA : clé invalide et crédits épuisés arrêtent les tentatives",async()=>{
 for(const status of [401,402]) {
  let called=0;
  const result=await runNvidiaFailover({
   messages:[{role:"user",content:"test"}],apiKey:"fake-local-key",signalFactory:()=>undefined,
   fetchImpl:async()=>{called++;return {ok:false,status};}
  });
  assert.equal(called,1);
  assert.equal(result.reason,"account_error");
  assert.equal(result.attempts[0].status,"http_"+status);
 }
});
test("NVIDIA : les dix échecs sont essayés dans l'ordre si le délai le permet",async()=>{
 const names=[];
 const result=await runNvidiaFailover({
  messages:[{role:"user",content:"test"}],apiKey:"fake-local-key",
  signalFactory:()=>undefined,
  overallBudgetMs:29000,
  fetchImpl:async (_url,options)=>{names.push(JSON.parse(options.body).model);return {ok:false,status:422};}
 });
 assert.deepEqual(names,[...NVIDIA_MODELS]);
 assert.equal(result.reason,"all_failed");
 assert.equal(result.attempts.length,10);
});
test("NVIDIA : absence de clé signalée sans appel réseau",async()=>{
 let called=false;
 const result=await runNvidiaFailover({apiKey:"",fetchImpl:async()=>{called=true;}});
 assert.equal(called,false);
 assert.equal(result.reason,"missing_key");
 assert.deepEqual(result.attempts,[]);
});
test("NVIDIA : limite temporelle arrête les modèles restants",async()=>{
 let clock=0;
 const result=await runNvidiaFailover({
  messages:[{role:"user",content:"test"}],apiKey:"fake-local-key",
  now:()=>clock,
  overallBudgetMs:3000,
  signalFactory:()=>undefined,
  fetchImpl:async()=>{clock+=2500;return {ok:false,status:500};}
 });
 assert.equal(result.reason,"time_budget");
 assert.equal(result.attempts.length,1);
});

test("bookmakers avec espaces, tirets, majuscules et variantes usuelles",()=>{
 const aliases=[
  ["line bet","linebet"],["LINE BET","linebet"],["Line-Bet","linebet"],["line_bet","linebet"],
  ["linebet","linebet"],["bet winner","betwinner"],["mel bet","melbet"],
  ["1 x bet","1xbet"],["1xbet","1xbet"],["1 win","1win"],["bet clic","betclic"]
 ];
 for(const [phrase,expected] of aliases)assert.equal(partnerFromMessage(phrase),expected,phrase);
 for(const unrelated of ["Alicenet","ligne de bus","lineage","mon problème"])assert.equal(partnerFromMessage(unrelated),null,unrelated);
});
test("inscription Line Bet correctement reconnue et liée au bon partenaire",()=>{
 const question="Je veux m'inscrire sur line bet, aide-moi.";
 assert.equal(intentFor(question),"signup");
 const provider=partnerFromMessage(question);
 assert.equal(provider,"linebet");
 const answer=signupMessage(provider);
 assert.match(answer,/Inscription Linebet/);
 assert.deepEqual(responseLinks("signup",question),[PARTNER_LINKS.linebet]);
 const rendered=buildTelegramMessage(answer,{allowedUrls:responseLinks("signup",question)});
 assert.equal(rendered.reply_markup.inline_keyboard[0][0].url,PARTNER_LINKS.linebet);
});
test("réponse réduite au nom d'un bookmaker après demande de précision",()=>{
 const history=[{role:"user",content:"Je veux m'inscrire"},{role:"assistant",content:"Sur quel bookmaker souhaites-tu t'inscrire ?"}];
 assert.equal(providerChoiceFromHistory("line bet",history),"linebet");
 assert.equal(providerChoiceFromHistory("Melbet",history),"melbet");
 assert.equal(providerChoiceFromHistory("line bet",[{role:"assistant",content:"Salut !"}]),null);
 assert.equal(providerChoiceFromHistory("Je veux m'inscrire sur line bet",history),null);
});
test("salutation courte reconnue séparément de la commande de démarrage",()=>{
 assert.equal(intentFor("cc"),"welcome");
 assert.equal(intentFor("/start"),"welcome");
 assert.equal(intentFor("Bonjour !"),"welcome");
});

test("réponses NVIDIA : extraction JSON compatible avec les modèles",()=>{
 const json=parseAiReply('{"reply":"Merci, avec plaisir 😊","buttons":[]}');
 assert.equal(json.reply,"Merci, avec plaisir 😊");
 assert.equal(json.structured,true);
 assert.deepEqual(json.buttons,[]);
 const fenced=parseAiReply('{"reply":"Voici le lien.","buttons":["pronos"]}');
 assert.equal(fenced.reply,"Voici le lien.");
 assert.deepEqual(fenced.buttons,["pronos"]);
 const free=parseAiReply("Salut, que puis-je faire pour toi ?");
 assert.equal(free.structured,false);
 assert.ok(free.reply.startsWith("Salut"));
});
test("l'IA choisit les boutons sans promotion automatique",()=>{
 assert.deepEqual(aiButtons(["pronos","bonus"],"Merci !"),[]);
 assert.deepEqual(aiButtons(["pronos"],"Le code promo, c'est quoi ?"),[]);
 assert.deepEqual(aiButtons(["pronos"],"Je veux les coupons du jour"),[LINKS.pronos]);
 assert.deepEqual(aiButtons(["channel"],"Comment rejoindre le canal Telegram ?"),[LINKS.channel]);
 assert.deepEqual(aiButtons(["partner_linebet"],"Je veux m'inscrire sur line bet"),[PARTNER_LINKS.linebet]);
 assert.deepEqual(aiButtons(["partner_melbet"],"Je veux m'inscrire sur line bet"),[]);
 assert.deepEqual(aiButtons(["site_trompeur"],"Quel est le lien ?"),[]);
});
test("l'IA peut proposer le lien après un choix de bookmaker dans l'historique",()=>{
 const history=[{role:"user",content:"Je veux m'inscrire"},{role:"assistant",content:"Sur quel bookmaker souhaites-tu t'inscrire ?"}];
 assert.deepEqual(aiButtons(["partner_linebet"],"line bet",history),[PARTNER_LINKS.linebet]);
});
test("contexte IA : faits de pronostics publiés uniquement",async()=>{
 const now=new Date("2026-11-17T02:00:00Z");
 let calls=0;
 const data={matches:[
  {date:"2026-11-17",event_date:"2026-11-17T18:00:00Z",category:"pro",recommendation_eligible:true,home_team:"Kuwait",away_team:"Honduras",prediction:{confidence:.85,prediction:"1X"}},
  {date:"2026-11-17",event_date:"2026-11-17T17:00:00Z",category:"vip",recommendation_eligible:false,home_team:"Fake",away_team:"Match",prediction:{confidence:.95}}
 ]};
 const facts=await assistantFacts("Je veux les coupons du jour",[],{now,loadJson:async()=>{calls++;return data}});
 assert.equal(calls,1);
 assert.ok(facts.includes("Kuwait"));
 assert.ok(!facts.includes("Fake"));
 assert.ok(facts.includes("pronos.html"));
});
test("contexte IA : évite d'inventer quand la source est inaccessible",async()=>{
 const now=new Date("2026-11-17T02:00:00Z");
 const facts=await assistantFacts("Quels coupons aujourd'hui ?",[],{now,loadJson:async()=>null});
 assert.match(facts,/Fichier inaccessible/);
 assert.ok(!facts.includes("Kuwait"));
});
test("contexte IA : bookmaker et navigation vérifiée",async()=>{
 const facts=await assistantFacts("Je veux m'inscrire sur line bet",[]);
 assert.ok(facts.includes("Linebet"));
 assert.ok(facts.includes(PARTNER_LINKS.linebet));
 const urls=aiLinkCatalog();
 assert.ok(urls.includes("partner_1xbet"));
 assert.ok(urls.includes("sitemap"));
});

test("inscription : l'IA peut oublier XPVIP, le serveur le rappelle et ajoute le bouton",()=>{
 const q="Je veux m'inscrire sur line bet, aide-moi";
 const raw="Ouvre le formulaire d'inscription puis complète les informations demandées.";
 const final=contextualPresentation(raw,q);
 assert.match(final,/\*\*XPVIP\*\*/);
 assert.match(final,/Inscription Linebet/);
 assert.deepEqual(contextualDestinations(q,[],[]),[PARTNER_LINKS.linebet]);
 const rendered=buildTelegramMessage(final+"\n"+PARTNER_LINKS.linebet,{allowedUrls:contextualDestinations(q,[],[])});
 assert.equal(rendered.reply_markup.inline_keyboard[0][0].url,PARTNER_LINKS.linebet);
 assert.match(rendered.text,/<b>📝 Inscription Linebet<\/b>/);
 assert.match(rendered.text,/<b>XPVIP<\/b>/);
 assert.match(rendered.text,/<i>si accepté par le bookmaker<\/i>/);
 assert.ok(!rendered.text.includes("https://"));
});
test("inscription : ne pas dupliquer XPVIP lorsqu'il est déjà proposé",()=>{
 const q="Je veux m'inscrire sur 1xbet";
 const text=contextualPresentation("Utilise le code XPVIP s'il est accepté.",q);
 assert.equal((text.match(/XPVIP/g)||[]).length,1);
 assert.deepEqual(contextualDestinations(q,[],[]),[PARTNER_LINKS["1xbet"]]);
});
test("code promo : réponse courte mise en gras, aucun bouton parasite",()=>{
 const q="Quel est ton code promo ?";
 const out=contextualPresentation("Notre code est XPVIP.",q);
 assert.match(telegramHtml(out),/<b>XPVIP<\/b>/);
 assert.deepEqual(contextualDestinations(q,[],["pronos","bonus"]),[]);
});
test("aucun bouton décoratif dans la conversation",()=>{
 for(const q of ["Merci !","cc","Salut","Ok","Parfait","Comment ça va ?"]){
  assert.deepEqual(contextualDestinations(q,[],["pronos","channel","partner_1xbet"]),[],q);
 }
});
test("coupons : site officiel et canal au bon contexte",()=>{
 const links=contextualDestinations("Je veux les coupons du jour",[],[]);
 assert.deepEqual(links,[LINKS.pronos,LINKS.channel]);
 const rendered=buildTelegramMessage(contextualPresentation("Voici les données disponibles.","Je veux les coupons du jour")+"\n"+links.join("\n"),{allowedUrls:links});
 assert.equal(rendered.reply_markup.inline_keyboard.length,2);
 assert.equal(rendered.reply_markup.inline_keyboard[0][0].style,"primary");
 assert.equal(rendered.reply_markup.inline_keyboard[1][0].style,"success");
 assert.match(rendered.text,/<b>⚽ Pronostics Mr XPRONOS<\/b>/);
});
test("canal et navigation sur le site : bouton adapté seulement à la question",()=>{
 assert.deepEqual(contextualDestinations("Comment rejoindre le canal Telegram ?",[],[]),[LINKS.channel]);
 assert.deepEqual(contextualDestinations("Je veux visiter le site",[],[]),[LINKS.accueil]);
 assert.deepEqual(contextualDestinations("Montre-moi les résultats précédents",[],[]),[LINKS.historique]);
 assert.deepEqual(contextualDestinations("Je veux le guide de conseils",[],[]),[LINKS.conseils]);
});
test("bookmakers : ne jamais pousser un lien d'affiliation non sollicité",()=>{
 assert.deepEqual(contextualDestinations("Tu connais Linebet ?",[],["partner_linebet"]),[]);
 assert.deepEqual(contextualDestinations("Je veux m'inscrire sur Linebet",[],["partner_melbet"]),[PARTNER_LINKS.linebet]);
 assert.deepEqual(contextualDestinations("Le code promo est quoi ?",[],["partner_1xbet"]),[]);
 assert.deepEqual(contextualDestinations("Je veux m'inscrire",[],["partner_linebet"]),[]);
});
test("formatage compatible Telegram : gras italique citation spoiler et barré",()=>{
 const markup="**Titre**\n*Note* et ~~ancien~~\n> Prudence avec les pronostics.\n||Option masquée||";
 const html=telegramHtml(markup);
 assert.match(html,/<b>Titre<\/b>/);
 assert.match(html,/<i>Note<\/i>/);
 assert.match(html,/<s>ancien<\/s>/);
 assert.match(html,/<blockquote>Prudence avec les pronostics.<\/blockquote>/);
 assert.match(html,/<tg-spoiler>Option masquée<\/tg-spoiler>/);
});
test("inscription : réponse courte à la suite d'un bookmaker choisi",()=>{
 const hist=[{role:"user",content:"Je veux m'inscrire"},{role:"assistant",content:"Sur quel bookmaker veux-tu t'inscrire ?"}];
 const q="line bet";
 assert.deepEqual(contextualDestinations(q,hist,[]),[PARTNER_LINKS.linebet]);
 const final=contextualPresentation("Commence par ouvrir le formulaire.",q,hist);
 assert.match(final,/XPVIP/);
});
