import test from "node:test";
import assert from "node:assert/strict";
import {
  bookmakerPolicy,bookmakerDecision,bookmakerRestrictionReply,
  trustedOddsFromFeed,findVerifiedOddsCombinations,reconcileKickoffs,
  compressTelegramImage,answerRelevanceGuard,limitClarificationQuestions,
  durableConversationSummary,assessTranscriptQuality,cleanupSpokenTranscript,
  safeContextualFallback,sensitiveImageRequest,sayConversation,intentFor,extractSpokenCorrection,resolveVoiceConfirmation,LINKS
} from "../index.js";

test("exclusions : aucune plateforme non approuvée dans les alternatives",()=>{
 const policy=bookmakerPolicy("melbet,linebet","linebet,betclic,1win");
 assert.deepEqual(policy.excluded,["melbet","linebet"]);
 assert.deepEqual(policy.approved,["betclic","1win"]);
 const check=bookmakerDecision("Je veux Melbet",policy);
 assert.equal(check.excluded,true);
 assert.match(bookmakerRestrictionReply(check),/non recommandée/);
 assert.ok(!bookmakerRestrictionReply(check).includes("https://"));
});
test("cotes : flux horodaté et opérateurs uniquement autorisés",()=>{
 const now=new Date("2026-11-17T10:00:00Z");
 const feed={updated_at:"2026-11-17T09:59:00Z",odds:[
   {event_id:"arsenal-chelsea",selection:"1X",bookmaker:"1win",decimal_odds:2.50,kickoff_utc:"2026-11-17T19:00:00Z"},
   {event_id:"lyon-marseille",selection:"Over 2.5",bookmaker:"betclic",decimal_odds:4,kickoff_utc:"2026-11-17T20:00:00Z"},
   {event_id:"x-y",selection:"1",bookmaker:"unknown",decimal_odds:3,kickoff_utc:"2026-11-17T20:00:00Z"}
 ]};
 const valid=trustedOddsFromFeed(feed,now);
 assert.equal(valid.length,2);
 assert.equal(findVerifiedOddsCombinations(valid,10)[0].total,10);
 assert.equal(trustedOddsFromFeed({...feed,updated_at:"2026-11-16T10:00:00Z"},now).length,0);
});
test("cotes : ne pas associer deux marchés d'un même match",()=>{
 const result=findVerifiedOddsCombinations([
  {eventId:"same",price:2.5},{eventId:"same",price:4}
 ],10);
 assert.deepEqual(result,[]);
});
test("horaires : conflit supérieur à 5 minutes détecté sans publier l'heure",()=>{
 const list=[{home:"Arsenal",away:"Chelsea",kickoff:"2026-11-17T19:00:00Z"}];
 const conflict=reconcileKickoffs(list,[{home_team:"Arsenal FC",away_team:"Chelsea",event_date:"2026-11-17T20:00:00Z"}]);
 assert.equal(conflict.conflicts.length,1);
 assert.equal(conflict.safe.length,0);
 const matching=reconcileKickoffs(list,[{home_team:"Arsenal",away_team:"Chelsea",event_date:"2026-11-17T19:02:00Z"}]);
 assert.equal(matching.safe[0].scheduleVerified,true);
});
test("images : re-encodage JPEG sous limite sans recours au transfert NVCF",async()=>{
 const source={mime:"image/png",bytes:new Uint8Array(150000)};
 let encoded=0;
 const result=await compressTelegramImage(source,{codec:{
  decode:async()=>({width:25,height:25,data:new Uint8Array(25*25*4).fill(255)}),
  encode:async()=>{encoded++;return new Uint8Array(80000)}
 }});
 assert.equal(result.mime,"image/jpeg");
 assert.equal(result.bytes.length,80000);
 assert.equal(result.compressed,true);
 assert.equal(encoded,1);
});
test("images : fichier excessivement gros refusé avant allocation mémoire",async()=>{
 const result=await compressTelegramImage({mime:"image/jpeg",bytes:new Uint8Array(180000)},{
  codec:{decode:async()=>({width:10000,height:10000,data:[]})}
 });
 assert.equal(result,null);
});
test("confidentialité : capture avec code OTP ne part pas directement à l'IA",()=>{
 assert.equal(sensitiveImageRequest("Regarde la capture avec mon code OTP"),true);
 assert.equal(sensitiveImageRequest("Je t'envoie une image de ma carte bancaire"),true);
 assert.equal(sensitiveImageRequest("Voici la photo du match"),false);
});
test("cohérence : une installation hors sujet est corrigée",()=>{
 const answer=answerRelevanceGuard("Voici les résultats des matchs.","Comment installer l'application ?");
 assert.match(answer,/installer.html/);
});
test("cohérence : la cote totale ne devient pas un score exact",()=>{
 const answer=answerRelevanceGuard("Le score exact est 2-1","Je veux une cote dix");
 assert.match(answer,/Cote totale/);
});
test("questions : une seule clarification, sans effacer les faits",()=>{
 const answer=limitClarificationQuestions("Quel bookmaker ?\nQuel pays ?\nTu as un code ?","Aide-moi");
 assert.equal((answer.match(/\?/g)||[]).length,1);
});
test("mémoire longue : résumé utile sans codes secrets",()=>{
 const summary=durableConversationSummary([],"","Je veux installer l'application","Le code SMS : 123456");
 assert.match(summary,/installation/);
 assert.ok(!summary.includes("123456"));
});
test("ASR : indice heuristique distinct d'une probabilité certifiée",()=>{
 const normal=assessTranscriptQuality("Je cherche le lien du canal Telegram");
 assert.equal(normal.quality,"clear");
 assert.equal(normal.reliabilityIndex,1);
 const low=assessTranscriptQuality("euh euh euh",{transcript_origin:"ctc_fallback"});
 assert.equal(low.quality,"uncertain");
 assert.ok(low.reliabilityIndex<.75);
});
test("ASR : nettoyer les hésitations, sans remplacer une marque inconnue",()=>{
 assert.match(cleanupSpokenTranscript("euh, je veux Linebett"),/Linebett/);
});
test("secours : demande d'installation garde la page officielle",()=>{
 assert.match(safeContextualFallback("Installe l'application",[]),/installer.html/);
 assert.match(safeContextualFallback("coupon",[]),/pronos.html/);
});
test("envoi : réclamer chaque fragment avant de le publier",async()=>{
 const claims=new Set(),received=[],finals=[];
 const send=async(_chat,text)=>{received.push(text);return {message_id:received.length+100}};
 const options={updateId:777,send,receiptReader:async()=>new Set(),receiptWriter:async()=>{},
   claimPart:async(_u,index)=>{if(claims.has(index))return false;claims.add(index);return true;},
   finalizePart:async(_u,index)=>finals.push(index)};
 const text="Bonjour ".repeat(160);
 await sayConversation(111,text,"",{},options);
 const before=received.length;
 await sayConversation(111,text,"",{},options);
 assert.equal(received.length,before);
 assert.equal(finals.length,before);
});

test("confirmation du vocal : le texte corrigé conserve son intention",()=>{
 const spoken="Je veux les coupons du jour";
 const confirmed="oui";
 assert.notEqual(intentFor(confirmed),intentFor(spoken));
 assert.equal(intentFor(spoken),"pronos");
 const changed=extractSpokenCorrection("Non, j'ai dit Linebet");
 assert.equal(changed,"Linebet");
 const recovered=resolveVoiceConfirmation("Non, j'ai dit Linebet","Je veux m'inscrire sur Bedclicker");
 assert.equal(recovered.resolved,true);
 assert.equal(intentFor(recovered.text),"signup");
 assert.equal(resolveVoiceConfirmation("oui",spoken).text,spoken);
});
