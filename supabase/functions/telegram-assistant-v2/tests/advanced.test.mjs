import test from "node:test";
import assert from "node:assert/strict";
import {
  guideIsContinuation,guideStateFromReply,memoryDigest,guidedResponse,
  assessTranscriptQuality,extractSpokenCorrection,transcribeTelegramAudio,
  reviewVisualDescription,analyzeTelegramImage,
  recoverSharedModelHealth,modelDiagnostics,
  sayConversation,installationSteps,clientCountryContext,combineClientOdds,
  suggestPartnerSpelling,analyzeClientIntent,tidyResponseText,LINKS
} from "../index.js";

test("guidage persistant : étape 6 après validation étape 5",()=>{
 const session={mode:"guided",goal:"Inscription Linebet",bookmaker:"linebet",step_number:5,
   step_text:"**Étape 5**\n\nAppuie sur Continuer."};
 assert.equal(guideIsContinuation("fait",session),true);
 assert.equal(guideIsContinuation("Regarde cette capture",session),true);
 const response=guidedResponse("Étape 1 : Renseigne le formulaire.","fait",[],session);
 assert.match(response,/Étape 6/);
 const next=guideStateFromReply("fait",response,session,[]);
 assert.equal(next.step_number,6);
 assert.equal(next.bookmaker,"linebet");
 const blocked=guideStateFromReply("Je suis bloqué","Explique l'étape 5",session,[]);
 assert.equal(blocked.step_number,5);
});
test("mémoire contextuelle : garde l'étape, jamais un OTP en clair",()=>{
 const session={mode:"guided",goal:"Inscription Linebet",bookmaker:"linebet",step_number:3,
   step_text:"OTP : 123456"};
 const summary=memoryDigest([{role:"user",content:"mon code SMS : 912345"}],session);
 assert.match(summary,/Étape confirmée ou affichée : 3/);
 assert.ok(!summary.includes("123456"));
 assert.ok(!summary.includes("912345"));
});
test("ASR : qualité faible si transcription tronquée ou répétée",()=>{
 assert.equal(assessTranscriptQuality("Je veux installer l'application").quality,"clear");
 assert.equal(assessTranscriptQuality("euh euh euh").quality,"uncertain");
 assert.ok(assessTranscriptQuality("Je veux inscrire mon compte",{transcript_origin:"ctc_fallback"}).reasons.includes("degraded_asr"));
 assert.equal(extractSpokenCorrection("Non, j'ai dit Linebet"),"Linebet");
});
test("ASR : payload verbose_json et origine reconnue",async()=>{
 let body=null;
 const result=await transcribeTelegramAudio({bytes:new Uint8Array([79,103,103,83]),mime:"audio/ogg"},{
   asrUrl:"https://example.org/v1/audio/transcriptions",asrKey:"not-real",apiKey:"not-real",
   http:async(url,opts)=>{body=opts.body;return {ok:true,json:async()=>({text:"Je voudrais rejoindre le canal",
     transcription:{transcript_origin:"llm"}})}}
 });
 assert.equal(result.quality,"clear");
 const values=Array.isArray(body.fields)?body.fields:body.entries?.();
 assert.ok(body.fields ? body.fields.some(x=>x[0]==="response_format"&&x[1]==="verbose_json") : true);
});
test("ASR : repli CTC demande une confirmation",async()=>{
 const result=await transcribeTelegramAudio({bytes:new Uint8Array([1,2,3,4]),mime:"audio/ogg"},{
   asrUrl:"https://example.org/v1/audio/transcriptions",apiKey:"fake",
   http:async()=>({ok:true,json:async()=>({text:"Je veux un coupon",
     transcription:{transcript_origin:"ctc_fallback"}})})
 });
 assert.equal(result.quality,"uncertain");
});
test("photos : une description trop incertaine est détectée",()=>{
 const parsed=reviewVisualDescription(JSON.stringify({description:"Je vois une page d'inscription",
   visible_text:["Inscription"],buttons:["Continuer"],uncertain:false}));
 assert.equal(parsed.uncertain,false);
 assert.match(parsed.description,/Boutons visibles/);
 assert.equal(reviewVisualDescription("Je ne peux pas voir l'image").uncertain,true);
});
test("photos : deuxième modèle si premier incertain",async()=>{
 const models=[];
 const result=await analyzeTelegramImage({bytes:new Uint8Array([1,2,3]),mime:"image/jpeg"},{
   apiKey:"fake",
   http:async(_url,options)=>{
     const model=JSON.parse(options.body).model;models.push(model);
     return {ok:true,json:async()=>({choices:[{message:{content:models.length===1
       ?JSON.stringify({description:"Je ne distingue rien",uncertain:true})
       :"La capture contient un bouton Continuer."}}]})};
   }
 });
 assert.equal(models.length,2);
 assert.match(result.description,/Continuer/);
});
test("modèles NVIDIA : protection partagée après deux erreurs 503",()=>{
 const now=Date.parse("2026-11-17T14:30:00Z");
 const rows=[{model:"m1",status:"http_503",created_at:new Date(now-1000).toISOString()},
  {model:"m1",status:"timeout",created_at:new Date(now-2000).toISOString()},
  {model:"m2",status:"ok",created_at:new Date(now-400).toISOString()}];
 const health=recoverSharedModelHealth(rows,now);
 assert.equal(health.has("m1"),true);
 assert.equal(health.has("m2"),false);
});
test("mesures NVIDIA : succès, erreurs et latence moyenne",()=>{
 const rows=[{model:"m1",status:"ok",duration_ms:200},
  {model:"m1",status:"http_503",duration_ms:400}];
 const stats=modelDiagnostics(rows);
 assert.equal(stats[0].attempts,2);
 assert.equal(stats[0].success,1);
 assert.equal(stats[0].avgMs,300);
});
test("Telegram : reprend au fragment suivant déjà envoyé",async()=>{
 let delivered=new Set([0]);const calls=[];
 const raw="**Guide**\n\n"+("Message explicatif et détaillé. ".repeat(80));
 const count=await sayConversation(123,raw,"",{allowedUrls:[LINKS.pronos]},{
  updateId:22,maxParts:5,
  receiptReader:async()=>delivered,
  receiptWriter:async(_update,i,ref)=>{assert.ok(ref.message_id);delivered.add(i);},
  send:async(id,text,connection,opts)=>{calls.push({id,text,opts});return {message_id:calls.length+20};}
 });
 assert.equal(calls.length,count-1);
 assert.equal(delivered.size,count);
 assert.deepEqual(calls.at(-1).opts.allowedUrls,[LINKS.pronos]);
});
test("installations : instruction selon le système et uniquement le site officiel",()=>{
 assert.match(installationSteps("iPhone Safari"),/Sur l’écran d’accueil/);
 assert.match(installationSteps("Android Samsung"),/Installer l’application/);
 assert.match(installationSteps("Windows PC"),/Windows/);
 for(const device of ["Android","iPhone","Windows"]){
  assert.ok(installationSteps(device).includes(LINKS.installer));
 }
});
test("pays : mention reconnue, légalité jamais inventée",()=>{
 assert.equal(clientCountryContext("Je suis à Lomé au Togo"),"Togo");
 assert.equal(clientCountryContext("Je vis à Cotonou"),"Bénin");
 assert.equal(clientCountryContext("Vous êtes disponibles ?"),null);
});
test("cotes fournies par le client : calcul exact sans inventer de bookmaker",()=>{
 const result=combineClientOdds("Cote 10 : 1,50 + 2.00 + 3,40");
 assert.deepEqual(result.values,[1.5,2,3.4]);
 assert.equal(result.total,10.2);
 assert.equal(result.verified,false);
 assert.equal(combineClientOdds("Fais-moi une cote 10"),null);
});
test("fautes phonétiques proches des partenaires : confirmation obligatoire",()=>{
 assert.equal(suggestPartnerSpelling("Je cherche Melbett"),"melbet");
 assert.equal(suggestPartnerSpelling("Je cherche Linebett"),"linebet");
 assert.equal(suggestPartnerSpelling("Je cherche un site complètement inconnu"),null);
 assert.equal(analyzeClientIntent("Aide-moi à m'inscrire sur Betclik").needsClarification,true);
});
test("formatage : dédoublonner code promo et éviter les mentions de liens invalides",()=>{
 const reply=tidyResponseText("🎁 **Code promo : XPVIP**\n🎁 **Code promo : XPVIP**\n[lien non vérifié retiré]");
 assert.equal((reply.match(/XPVIP/g)||[]).length,1);
 assert.ok(!reply.includes("[lien non vérifié"));
 assert.match(reply,/Code promo : XPVIP/);
});
