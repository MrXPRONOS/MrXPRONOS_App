import test from "node:test";
import assert from "node:assert/strict";
import {intentFor,publishedPicks,exactScorePicks,handleRequest,eligibleBusinessMessage,LINKS,buildTelegramMessage,telegramHtml,buttonForUrl,PROJECT_KNOWLEDGE,knowledgePrompt,responseLinks,PARTNER_LINKS,partnerFromMessage,providerChoiceFromHistory,signupMessage,guidanceFollowup,sitemapUrls,pageForQuestion,NVIDIA_MODELS,runNvidiaFailover,parseAiReply,aiButtons,assistantFacts,aiLinkCatalog,contextualPresentation,contextualDestinations,polishTelegramText,newcomerWelcomeMessage,shouldWelcomeNewcomer,normalizeClientFrench,analyzeClientIntent,safetyResponse,ambiguousPartnerQuestion,redactSensitiveText,verifiedReplyReview,recordModelHealth,modelInCooldown,splitTelegramReply,guidedMode,guidedResponse,telegramMediaKind,selectMedia,getTelegramMedia,analyzeTelegramImage,transcribeTelegramAudio,MEDIA_MODELS,sayConversation} from "../index.js";

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
test("les liens Markdown autorisés deviennent des liens cliquables dans le texte",()=>{
 const body=buildTelegramMessage("[Retrouver les pronostics]("+LINKS.pronos+")");
 assert.match(body.text,/<a href="https:\/\/mrxpronos\.github\.io\/MrXPRONOS_App\/pronos\.html">Retrouver les pronostics<\/a>/);
 assert.equal(body.reply_markup,undefined);
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
  "mistralai/mistral-large-4-1t-a52b",
  "nvidia/nemotron-3-ultra-550b-a55b",
  "poolside/laguna-xs-2.1"
 ]);
 assert.equal(NVIDIA_MODELS.at(-1),"meta/muse-glimmer-30b");
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
  perModelTimeoutMs:2000, // test artificiel de 10 erreurs immédiates
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
  perModelTimeoutMs:2000,
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
 const facts=await assistantFacts("Je veux les coupons du jour",[],{now,loadJson:async(url)=>{calls++;return url.endsWith("/data.json")?data:null}});
 assert.equal(calls,2); // data.json + second source schedule for consistency
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
 assert.match(rendered.text,/<b>Code promo : XPVIP<\/b>/);
 assert.match(rendered.text,/Repère le champ <b>Code promo<\/b>/);
 assert.ok(!rendered.text.includes("https://"));
});
test("inscription : ne pas dupliquer XPVIP lorsqu'il est déjà proposé",()=>{
 const q="Je veux m'inscrire sur 1xbet";
 const text=contextualPresentation("Utilise le code XPVIP s'il est accepté.",q);
 assert.equal((text.match(/Code promo : XPVIP/g)||[]).length,1);
 assert.ok(!text.includes('si le champ existe'));
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

test("l'IA ne peut imposer un bouton hors sujet même officiel",()=>{
 assert.deepEqual(contextualDestinations("Je veux m'inscrire sur Linebet",[],["pronos","channel","bonus","partner_melbet"]),[PARTNER_LINKS.linebet]);
 assert.deepEqual(contextualDestinations("Je veux consulter le site",[],["pronos","bonus"]),[LINKS.accueil]);
 assert.deepEqual(contextualDestinations("Comment rejoindre le canal ?",[],["partner_1xbet","bonus"]),[LINKS.channel]);
 assert.deepEqual(contextualDestinations("Comment ça va ?",[],["pronos","bonus","channel"]),[]);
});


test("formatage : une ligne vide après un titre important sans changer le sens",()=>{
 const result=polishTelegramText("**Résumé du match**\nLe match commence demain.","Analyse ce match");
 assert.equal(result,"**Résumé du match**\n\nLe match commence demain.");
 assert.match(telegramHtml(result),/<b>Résumé du match<\/b>\n\nLe match commence demain/);
});
test("formatage : code promotionnel et conditions lisibles",()=>{
 const text=contextualPresentation("Utilise XPVIP et termine le formulaire.","Je veux m'inscrire sur line bet");
 const html=telegramHtml(text);
 assert.match(html,/<b>📝 Inscription Linebet<\/b>\n\n/);
 assert.match(html,/<b>XPVIP<\/b>/);
 assert.match(html,/<b>Code promo : XPVIP<\/b>/);
 assert.match(html,/Repère le champ <b>Code promo<\/b>/);
 assert.ok(text.includes("\n\n🎁"));
 assert.ok(!/si (?:le|un) champ (?:existe|appara)/i.test(text));
});
test("formatage : étapes sur des lignes distinctes",()=>{
 const text=polishTelegramText("1. Ouvre le compte 2. Complète ton profil 3. Vérifie ton identité.","Aide-moi à créer un compte");
 assert.match(text,/1\. Ouvre le compte\n2\. Complète ton profil\n3\. Vérifie ton identité/);
});
test("formatage : citation de prudence et espace avant",()=>{
 const text=polishTelegramText("**Analyse**\nVoici les éléments importants.\n⚠️ Aucun gain garanti, le pari comporte des risques.","Analyse du match");
 const html=telegramHtml(text);
 assert.match(html,/<b>Analyse<\/b>\n\n/);
 assert.match(html,/<blockquote>⚠️ Aucun gain garanti, le pari comporte des risques\.<\/blockquote>/);
 assert.ok(text.includes("\n\n> ⚠️"));
});
test("formatage : autres styles Telegram restent utilisables",()=>{
 const input="**Important**\n\n*Précision* et ~~ancien~~ ; ||détail masqué||\n> Exemple de citation";
 const html=telegramHtml(polishTelegramText(input,"Explique-moi"));
 assert.match(html,/<b>Important<\/b>/);
 assert.match(html,/<i>Précision<\/i>/);
 assert.match(html,/<s>ancien<\/s>/);
 assert.match(html,/<tg-spoiler>détail masqué<\/tg-spoiler>/);
 assert.match(html,/<blockquote>Exemple de citation<\/blockquote>/);
});
test("formatage : salutations brèves sans paragraphes artificiels",()=>{
 assert.equal(polishTelegramText("Salut 😊","cc"),"Salut 😊");
 assert.equal(contextualPresentation("Avec plaisir 😊","Merci !"),"Avec plaisir 😊");
});
test("formatage : les blocs longs gagnent un paragraphe",()=>{
 const text="La forme des équipes est importante pour évaluer la rencontre. Il faut aussi examiner les absences et le calendrier chargé des joueurs. Les statistiques du championnat donnent du contexte mais ne garantissent pas une victoire à coup sûr. Garde une mise adaptée à ton budget.";
 const result=polishTelegramText(text,"Quels conseils ?");
 assert.ok(result.includes("\n\n"),result);
 assert.equal(result.replace(/\n\n/g," ").replace(/\s+/g," ").trim(),text);
});
test("formatage : texte HTML non fiable toujours échappé après traitement",()=>{
 const text=polishTelegramText("**Consigne**\n<script>test</script>","Important ?");
 const html=telegramHtml(text);
 assert.ok(!html.includes("<script>"));
 assert.match(html,/&lt;script&gt;test&lt;\/script&gt;/);
});


test("première étape : une ligne VIDE entre présentation et 1. Inscription",()=>{
 const raw="Voici le lien direct pour ouvrir Melbet. Une fois sur le site, 1. Inscription : ouvre le formulaire.";
 const formatted=polishTelegramText(raw,"Je veux m'inscrire sur Melbet");
 assert.match(formatted,/Une fois sur le site,\n\n1\. Inscription/);
 assert.ok(!/site,[ \t]+1\. Inscription/.test(formatted));
});
test("première étape seule : insérer aussi le paragraphe vide",()=>{
 const raw="Voici le lien. Une fois sur le site, 1. inscription";
 const out=polishTelegramText(raw,"Comment m'inscrire ?");
 assert.match(out,/site,\n\n1\. inscription/);
 assert.equal(polishTelegramText(out,"Comment m'inscrire ?"),out);
});
test("numérotation avec virgule reconnue et normalisée",()=>{
 const out=polishTelegramText("Une fois sur le site, 1, Inscription. 2, Coordonnées. 3, Validation.","Aide-moi à m'inscrire");
 assert.match(out,/site,\n\n1\. Inscription\.\n2\. Coordonnées\.\n3\. Validation/);
});
test("étapes multiples avec une première étape déjà à la ligne",()=>{
 const out=polishTelegramText("Voici le lien.\n1. Inscription\n2. Complète le formulaire","Aide-moi");
 assert.match(out,/Voici le lien\.\n\n1\. Inscription\n2\. Complète/);
 assert.equal(polishTelegramText(out,"Aide-moi"),out);
});
test("mise en forme : ne pas casser cotes, dates, noms de marques ou code 1X",()=>{
 const raw="Le marché 1X et la cote 1.50 sont affichés. Match le 17.11 à 18h.";
 assert.equal(polishTelegramText(raw,"Cotes du match"),raw);
});
test("code promo : le champ est indiqué directement, sans conditionnel sur sa présence",()=>{
 const text=contextualPresentation("Voici le lien. Code promo : XPVIP, si le champ existe.","Je veux m'inscrire sur Melbet");
 assert.match(text,/🎁 \*\*Code promo : XPVIP\*\*/);
 assert.match(text,/Repère le champ \*\*Code promo\*\* du formulaire et saisis \*\*XPVIP\*\*/);
 assert.ok(!/si (?:le|un) champ/i.test(text),text);
 assert.equal((text.match(/Code promo : XPVIP/g)||[]).length,1);
 assert.ok(!text.includes("XPVIP, ."));
});
test("le code promo est placé dans son propre bloc sous le guide",()=>{
 const text=contextualPresentation("Voici le lien. Une fois sur le site, 1. Inscription. 2. Renseigne ton profil.",
   "Je veux m'inscrire sur Linebet");
 assert.match(text,/site,\n\n1\. Inscription\.\n2\. Renseigne ton profil\.\n\n🎁 \*\*Code promo : XPVIP\*\*/);
 assert.ok(!text.includes("si le champ existe"));
});
test("une ancienne étape promo conditionnelle n'est pas répétée",()=>{
 const text=contextualPresentation("Une fois sur le site, 1. Inscription. 2. Si le champ existe, saisis XPVIP. 3. Vérifie ton compte.",
   "Je veux m'inscrire sur Melbet");
 assert.match(text,/1\. Inscription\.\n2\. Vérifie ton compte\./);
 assert.equal((text.match(/Code promo : XPVIP/g)||[]).length,1);
 assert.ok(!text.includes("Si le champ existe"));
});
test("les consignes d'inscription préservent le reste de la phrase de l'IA",()=>{
 const text=contextualPresentation("Utilise XPVIP et termine le formulaire.","Je veux m'inscrire sur 1xbet");
 assert.ok(text.includes("Termine le formulaire."),text);
 assert.ok(text.includes("Code promo : XPVIP"),text);
});
test("le texte de secours place aussi la première étape sous une ligne vide",()=>{
 const raw=signupMessage("melbet");
 const formatted=polishTelegramText(raw,"Je veux m'inscrire sur Melbet");
 assert.match(formatted,/législation locale\) :\n\n1\. Ouvre/);
 assert.match(formatted,/🎁 \*\*Code promo : XPVIP\*\*/);
});

test("messages longs : 2 à 5 messages découpés proprement",()=>{
 const reply=Array(12).fill("**Sujet important**\n\n"+("Explication claire. ".repeat(22))).join("\n\n");
 const chunks=splitTelegramReply(reply,{target:500,maxParts:5});
 assert.ok(chunks.length>1&&chunks.length<=5,chunks.length);
 assert.ok(chunks.every(x=>x.length<=3500));
 assert.ok(chunks[0].includes("Sujet important"));
});
test("messages courts : pas de découpage inutile",()=>{
 assert.deepEqual(splitTelegramReply("Merci beaucoup !"),["Merci beaucoup !"]);
 assert.deepEqual(splitTelegramReply(""),[]);
});
test("guidage : une seule étape et confirmation à chaque message",()=>{
 const reply="Étape 1 : Ouvre le lien.\nÉtape 2 : Remplis les données.\nÉtape 3 : Confirme le compte.";
 const result=guidedResponse(reply,"Guide-moi étape par étape");
 assert.ok(result.includes("Étape 1"),result);
 assert.ok(!result.includes("Étape 2"),result);
 assert.ok(result.includes("fait"),result);
});
test("guidage : la réponse fait poursuit le guide, pas une nouvelle FAQ",()=>{
 const history=[{role:"assistant",content:"**Étape 1**\n\nOuvre le lien.\n\n*Quand c’est fait, réponds « fait ». *"}];
 assert.equal(guidedMode("fait",history),true);
 const reply=guidedResponse("Renseigne ton nom.","fait",history);
 assert.ok(reply.includes("Étape 2"),reply);
 assert.ok(!reply.includes("Étape 3"),reply);
});
test("guidage : la réponse brève ordinaire n'active pas le mode guidé",()=>{
 assert.equal(guidedMode("bonjour",[]),false);
 assert.equal(guidedMode("fait",[]),false);
});
test("image : Telegram accepte photo et document image",()=>{
 assert.equal(telegramMediaKind({photo:[{file_id:"p1"}]}),"image");
 assert.equal(selectMedia({photo:[{file_id:"a",file_size:120},{file_id:"b",file_size:560}]}).fileId,"b");
 assert.equal(selectMedia({document:{file_id:"b",mime_type:"image/png",file_size:2}}).mime,"image/png");
 assert.equal(telegramMediaKind({voice:{file_id:"v1"}}),"voice");
 assert.equal(selectMedia({voice:{file_id:"v1"}}).mime,"audio/ogg");
});
test("Telegram : téléchargement privé, jamais URL avec token vers NVIDIA",async()=>{
 const visited=[];
 const data=await getTelegramMedia({fileId:"p1",mime:"image/jpeg",bytes:6},{
  key:"test_secret_token",
  getFile:async(name,body)=>{assert.equal(name,"getFile");assert.equal(body.file_id,"p1");return {file_path:"photos/file_2.jpg",file_size:4};},
  download:async(url)=>{visited.push(url);return {ok:true,headers:{get:()=>null},arrayBuffer:async()=>new Uint8Array([1,2,3,4]).buffer};}
 });
 assert.equal(data.bytes.length,4);
 assert.equal(visited.length,1);
 assert.ok(visited[0].includes("test_secret_token"));
});
test("vision NVIDIA : pièce jointe JPEG, réponse du modèle VL",async()=>{
 let sent=null;
 const result=await analyzeTelegramImage({bytes:new Uint8Array([1,2,3,4]),mime:"image/jpeg"},{
  apiKey:"fake",http:async(url,params)=>{
   assert.ok(url.includes("integrate.api.nvidia.com"));
   sent=JSON.parse(params.body);
   return {ok:true,json:async()=>({choices:[{message:{content:"Le bouton Inscription est visible à droite."}}]})};
  }
 });
 assert.equal(result.model,MEDIA_MODELS.vision[0]);
 assert.equal(result.description,"Le bouton Inscription est visible à droite.");
 assert.equal(sent.messages[0].content[1].type,"image_url");
 assert.ok(sent.messages[0].content[1].image_url.url.startsWith("data:image/jpeg;base64,"));
});
test("vision NVIDIA : photo au-delà de 175 ko passe par un asset privé",async()=>{
 let request=null,assetCalls=0;
 const result=await analyzeTelegramImage({bytes:new Uint8Array(185000),mime:"image/png"},{
  apiKey:"fake",upload:async()=>{assetCalls++;return "12345678-1234-1234-1234-123456789012";},
  http:async(url,params)=>{
   request={url,params};
   return {ok:true,json:async()=>({choices:[{message:{content:"Je vois un tableau."}}]})};
  }
 });
 assert.equal(assetCalls,1);
 assert.equal(result.description,"Je vois un tableau.");
 assert.ok(request.params.headers["NVCF-INPUT-ASSET-REFERENCES"]);
 assert.ok(JSON.parse(request.params.body).messages[0].content[1].image_url.url.includes(";asset_id,"));
});
test("audio NVIDIA : WAV transcrit avec Nemotron Omni",async()=>{
 let requested=null;
 const result=await transcribeTelegramAudio({bytes:new Uint8Array([82,73,70,70]),mime:"audio/wav"},{
  asrUrl:"",apiKey:"fake",http:async(url,opts)=>{
   requested=JSON.parse(opts.body);
   return {ok:true,json:async()=>({choices:[{message:{content:"Je veux les pronostics du jour."}}]})};
  }
 });
 assert.equal(result.transcript,"Je veux les pronostics du jour.");
 assert.equal(requested.model,MEDIA_MODELS.voice);
 assert.equal(requested.messages[0].content[0].type,"audio_url");
});
test("audio Ogg : transcription via service ASR configuré",async()=>{
 const req=[];
 const result=await transcribeTelegramAudio({bytes:new Uint8Array([79,103,103,83]),mime:"audio/ogg"},{
  apiKey:"fake",asrUrl:"https://asr.example.com/v1/audio/transcriptions",
  http:async(url,options)=>{
   req.push({url,method:options.method});
   return {ok:true,json:async()=>({text:"Bonjour, comment ça va ?"})};
  }
 });
 assert.equal(result.transcript,"Bonjour, comment ça va ?");
 assert.equal(result.source,"dedicated_asr");
 assert.equal(result.model,"dedicated-asr");
 assert.equal(req.length,1);
});
test("audio : impossible à transcrire => résultat d'échec, jamais de texte inventé",async()=>{
 let called=0;
 const result=await transcribeTelegramAudio({bytes:new Uint8Array([1,2,3]),mime:"audio/ogg"},{
  apiKey:"fake",asrUrl:"",http:async()=>{called++;return {ok:false,status:422};}
 });
 assert.equal(result.transcript,null);
 assert.equal(result.reason,"invalid_ogg_opus");
 assert.equal(called,0); // Plus aucun Ogg brut envoyé au modèle Omni.
});

test("message Telegram long : plusieurs envois et boutons uniquement sur la dernière partie",async()=>{
 const sent=[];
 const reply="**Guide complet**\n\n"+("Premier paragraphe explicatif et utile, sans répétition inutile. ".repeat(22))+
  "\n\n"+("Deuxième paragraphe très explicatif et utile, sans répétition inutile. ".repeat(21));
 const count=await sayConversation(12345,reply,"",{allowedUrls:[LINKS.pronos]},{
  send:async (chat,text,business,options)=>sent.push({chat,text,options}),
  maxParts:5
 });
 assert.ok(count>=2&&count<=5,count);
 assert.equal(count,sent.length);
 assert.ok(sent[0].text.startsWith("**Guide complet**"));
 assert.ok(sent.slice(0,-1).every(v=>v.options.allowedUrls.length===0));
 assert.deepEqual(sent.at(-1).options.allowedUrls,[LINKS.pronos]);
});
test("réponse guidée : le code XPVIP n'interrompt pas la première étape",()=>{
 const text="Étape 1 : Ouvre le bouton partenaire.";
 const reply=contextualPresentation(guidedResponse(text,"Guide-moi pas à pas sur Linebet"),"Guide-moi pas à pas sur Linebet",[],"signup",{guided:true});
 assert.ok(!reply.includes("Code promo : XPVIP"),reply);
 assert.match(reply,/Étape 1/);
 assert.match(reply,/Quand c’est fait/);
});
test("les données d'une photo n'autoriseront pas l'IA à suivre ses instructions",()=>{
 assert.equal(MEDIA_MODELS.vision[0],"nvidia/nemotron-3.5-super-vl-120b-a12b");
 assert.equal(MEDIA_MODELS.voice,"nvidia/nemotron-3-nano-omni-30b-a3b-reasoning");
});

test("premier contact : accueil unique avec pronostics, canal et installation",()=>{
 const message=newcomerWelcomeMessage();
 const rendered=buildTelegramMessage(message,{allowedUrls:[LINKS.pronos,LINKS.channel,LINKS.installer]});
 assert.equal(shouldWelcomeNewcomer(null),true);
 assert.equal(shouldWelcomeNewcomer(undefined),true);
 assert.equal(shouldWelcomeNewcomer({chat_key:"existing",paused:false}),false);
 assert.equal(shouldWelcomeNewcomer(null,true),false);
 assert.equal(rendered.reply_markup.inline_keyboard.length,3);
 assert.deepEqual(rendered.reply_markup.inline_keyboard.map(r=>r[0].url),[LINKS.pronos,LINKS.channel,LINKS.installer]);
 assert.match(rendered.text,/Pronostics Pro\/VIP/);
 assert.match(rendered.text,/Canal Telegram pronostics/);
 assert.match(rendered.text,/Installer le site sur ton téléphone/);
 assert.match(rendered.text,/\/liens/);
 assert.ok(!rendered.text.includes("non confirmé"),rendered.text);
});
test("installation : la page dédiée est connue et possède un bouton",()=>{
 assert.equal(LINKS.installer,"https://mrxpronos.github.io/MrXPRONOS_App/installer.html");
 assert.equal(intentFor("Comment installer le site ?"),"site_nav");
 assert.deepEqual(responseLinks("site_nav","Je veux installer l'application"),[LINKS.installer]);
 assert.deepEqual(contextualDestinations("Je veux installer l'application",[],[]),[LINKS.installer]);
 const msg=buildTelegramMessage(LINKS.installer,{allowedUrls:[LINKS.installer]});
 assert.equal(msg.reply_markup.inline_keyboard[0][0].url,LINKS.installer);
});
test("gras + italique et gras + souligné et italique + souligné imbriqués",()=>{
 const html=telegramHtml("***Texte important***, **__Mot souligné__**, *__Note discrète__*.");
 assert.match(html,/<b><i>Texte important<\/i><\/b>/);
 assert.match(html,/<b><u>Mot souligné<\/u><\/b>/);
 assert.match(html,/<i><u>Note discrète<\/u><\/i>/);
 const triple=telegramHtml("__***Triple style***__");
 assert.match(triple,/<u><b><i>Triple style<\/i><\/b><\/u>/);
});
test("lien sur le texte Clique ici vers la page officielle, sans URL en clair",()=>{
 const raw="Pour l'installation, [clique ici]("+LINKS.installer+").";
 const msg=buildTelegramMessage(raw,{allowedUrls:[LINKS.installer]});
 assert.match(msg.text,/<a href="https:\/\/mrxpronos\.github\.io\/MrXPRONOS_App\/installer\.html">clique ici<\/a>/);
 assert.ok(!msg.text.includes("]("));
 assert.equal(msg.reply_markup,undefined);
});
test("lien inventé ou hors liste supprimé, aucun lien dangereux rendu",()=>{
 const msg=buildTelegramMessage("[clique ici](https://example.net/arnaque)");
 assert.ok(!msg.text.includes("<a href"));
 assert.ok(!msg.text.includes("https://example.net"));
 assert.match(msg.text,/Lien externe non confirmé/);
 assert.match(msg.text,/\/liens/);
});
test("cinq destinations : trois boutons et deux liens ancrés dans le texte",()=>{
 const urls=[LINKS.accueil,LINKS.pronos,LINKS.channel,LINKS.installer,LINKS.bonus];
 const msg=buildTelegramMessage(urls.join("\n"),{allowedUrls:urls});
 assert.equal(msg.reply_markup.inline_keyboard.length,3);
 assert.equal((msg.text.match(/<a href=/g)||[]).length,2);
 assert.ok(!msg.text.includes("https://mrxpronos.github.io/MrXPRONOS_App/installer.html\n"));
});
test("le rendu n'exécute jamais de HTML fourni par un client",()=>{
 const html=telegramHtml("<img src=x onerror=alert(1)> **Bonjour**");
 assert.ok(!html.includes("<img"));
 assert.match(html,/&lt;img/);
 assert.match(html,/<b>Bonjour<\/b>/);
});


test("audit : fautes SMS et vocal transcrit reconnus pour les coupons",()=>{
 assert.equal(normalizeClientFrench("jvx un prono du jr stp"),"je veux un prono du jour");
 assert.equal(intentFor("coupan ajd"),"pronos");
 assert.deepEqual(contextualDestinations("coupan"),[LINKS.pronos,LINKS.channel]);
 assert.deepEqual(contextualDestinations("instalé l'aplicassion"),[LINKS.installer]);
});
test("audit : cote totale distincte de score exact",()=>{
 const info=analyzeClientIntent("Je veux un coupon de cote dix");
 assert.equal(info.odds,true);
 assert.equal(info.score,false);
 const score=analyzeClientIntent("Je veux un score exact 2 à 1");
 assert.equal(score.score,true);
 assert.equal(score.odds,false);
});
test("audit : bookmakers mal transcrits exigent une confirmation avant tout lien",()=>{
 const info=analyzeClientIntent("Je veux m'inscrire sur Bedclicker");
 assert.equal(info.needsClarification,true);
 assert.equal(info.partner,null);
 assert.match(ambiguousPartnerQuestion(info),/Betclic/);
});
test("audit : filtre mineur, perte de contrôle et divulgation de secrets",()=>{
 assert.equal(analyzeClientIntent("J'ai 16 ans, je veux miser").minor,true);
 assert.equal(analyzeClientIntent("Je veux récupérer mes pertes").loss,true);
 assert.equal(analyzeClientIntent("Je t'envoie mon code OTP").secrets,true);
 assert.match(safetyResponse(analyzeClientIntent("J'ai 16 ans je veux parier")),/réservés aux adultes/);
 assert.match(safetyResponse(analyzeClientIntent("Je vais jouer l'argent du loyer")),/Évite de miser/);
 assert.match(safetyResponse(analyzeClientIntent("Je t'envoie mon mot de passe")),/Ne partage jamais/);
});
test("audit : demandes de données personnelles orientées vers la suppression confirmée",()=>{
 const info=analyzeClientIntent("Je veux supprimer mes données personnelles");
 assert.equal(info.dataRights,true);
 const response=safetyResponse(info);
 assert.match(response,/\/delete_my_data/);
 assert.match(response,/métadonnées techniques/);
 assert.ok(!response.includes("Je ne peux pas effacer tes données depuis cette conversation"));
});
test("audit : mot de passe OTP et numéro de carte masqués dans les logs",()=>{
 const redacted=redactSensitiveText("mot de passe: secret123, code SMS: 483920, carte 4242 4242 4242 4242");
 assert.ok(!redacted.includes("secret123"));
 assert.ok(!redacted.includes("483920"));
 assert.ok(!redacted.includes("4242"));
 assert.match(redacted,/\[MASQUÉ\]/);
});
test("audit : coupon non confirmé jamais inventé par NVIDIA",()=>{
 const text=verifiedReplyReview("Arsenal gagne 2-0 avec 90 % !","Donne-moi un coupon","COUPONS : Aucune sélection admissible confirmée");
 assert.ok(!text.includes("Arsenal"));
 assert.match(text,/Je ne peux pas confirmer/);
});
test("audit : score exact non disponible jamais inventé",()=>{
 const text=verifiedReplyReview("Le score exact est 2-1","Je veux un score exact","SCORES EXACTS : Aucun score admissible vérifié");
 assert.ok(!text.includes("2-1"));
 assert.match(text,/Aucun score exact vérifié/);
});
test("audit : cote 10 non vérifiée traitée comme cote combinée",()=>{
 const text=verifiedReplyReview("Voici une cote 10 garantie","Fais-moi une cote 10","COTE TOTALE : pas de cotes réelles");
 assert.match(text,/multipliant les cotes/);
 assert.ok(!text.includes("garantie"));
});
test("audit : même sur simple demande Coupon, les deux destinations apparaissent",()=>{
 assert.deepEqual(contextualDestinations("coupon"),[LINKS.pronos,LINKS.channel]);
 assert.deepEqual(contextualDestinations("C'est quoi un coupon"),[]);
});
test("audit : Telegram préfère une photo exploitable sans upload NVCF",()=>{
 const photo=selectMedia({photo:[{file_id:"grand",file_size:920000},{file_id:"moyen",file_size:94000},{file_id:"petit",file_size:4500}]});
 assert.equal(photo.fileId,"moyen");
});
test("audit : 410 NVCF est une erreur d'upload, pas une image floue",async()=>{
 const result=await analyzeTelegramImage({bytes:new Uint8Array(150000),mime:"image/jpeg"},{
   apiKey:"test",upload:async()=>{throw Error("nvidia_asset_create_410")},
   http:async()=>{throw Error("should_not_be_called")}
 });
 assert.equal(result.description,null);
 assert.equal(result.reason,"asset_410");
});
test("audit : circuit breaker après 2 erreurs NVIDIA temporaires",()=>{
 const health=new Map();
 recordModelHealth(health,"model","http_503",100);
 assert.equal(modelInCooldown(health,"model",110),false);
 recordModelHealth(health,"model","timeout",200);
 assert.equal(modelInCooldown(health,"model",250),true);
 assert.equal(modelInCooldown(health,"model",90300),false);
});
test("audit : succès NVIDIA remet le modèle en service",()=>{
 const health=new Map();
 recordModelHealth(health,"model","timeout",100);
 recordModelHealth(health,"model","timeout",200);
 recordModelHealth(health,"model","ok",250);
 assert.equal(modelInCooldown(health,"model",260),false);
});
test("audit : 410 vision et secret ne contaminent pas les liens clients",()=>{
 assert.deepEqual(contextualDestinations("Je veux un coupon"),[LINKS.pronos,LINKS.channel]);
 const html=telegramHtml("**Attention**\n> *Ne communique jamais ton OTP.*");
 assert.match(html,/<blockquote><i>Ne communique jamais ton OTP/);
});

test("audit : minorité détectée même sans mot parier",()=>{
 assert.equal(analyzeClientIntent("J'ai 17 ans, je peux faire un dépôt ?").minor,true);
 assert.equal(analyzeClientIntent("J'ai 16 ans, j'ai besoin d'un compte").minor,true);
});
test("audit : annuler ou recommencer une assistance pas à pas",()=>{
 assert.equal(intentFor("/stop"),"guide_cancel");
 assert.equal(intentFor("Arrête le guide"),"guide_cancel");
 assert.equal(intentFor("/restart"),"guide_restart");
 assert.equal(intentFor("Recommence depuis le début"),"guide_restart");
});
test("audit : cote dix routée différemment du score exact",()=>{
 assert.equal(intentFor("Je veux une cote dix"),"odds");
 assert.equal(intentFor("Je veux le score exact"),"scores");
 assert.deepEqual(responseLinks("odds","Je cherche une cote 10"),[LINKS.pronos]);
});
