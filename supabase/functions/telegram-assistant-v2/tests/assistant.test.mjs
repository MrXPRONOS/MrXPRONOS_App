import test from "node:test";
import assert from "node:assert/strict";
import {intentFor,publishedPicks,exactScorePicks,handleRequest,eligibleBusinessMessage,LINKS,buildTelegramMessage,telegramHtml,buttonForUrl} from "../index.js";

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
 assert.ok(body.text.includes("<b>Clique sur le bouton ci-dessous.</b>"));
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
