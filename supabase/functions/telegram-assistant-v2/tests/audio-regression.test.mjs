import test from "node:test";
import assert from "node:assert/strict";
import {
 looksLikeTelegramOggOpus,pcmMonoWav16,convertTelegramOggToWav,
 transcribeTelegramAudio,transcriptLooksCorrupted
} from "../index.js";

function sampleOgg(){
 const bytes=new Uint8Array(100);
 bytes.set([79,103,103,83],0); // OggS
 for(let i=0;i<8;i++)bytes[28+i]="OpusHead".charCodeAt(i);
 return {bytes,mime:"audio/ogg"};
}
function pcm(seconds=2){
 const rate=48000;
 const samples=new Float32Array(Math.round(seconds*rate));
 for(let i=0;i<samples.length;i++)samples[i]=.2*Math.sin(i/12);
 return {channelData:[samples],sampleRate:rate};
}
test("voix Telegram : reconnaître Ogg Opus sans l'envoyer brut à Omni",()=>{
 assert.equal(looksLikeTelegramOggOpus(sampleOgg().bytes),true);
 assert.equal(looksLikeTelegramOggOpus(new Uint8Array([1,2,3,4])),false);
});
test("transcodage : construire un WAV PCM mono 16 kHz avec en-tête valide",()=>{
 const wave=pcmMonoWav16(pcm(1).channelData,48000);
 const head=String.fromCharCode(...wave.subarray(0,4));
 const dv=new DataView(wave.buffer);
 assert.equal(head,"RIFF");
 assert.equal(String.fromCharCode(...wave.subarray(8,12)),"WAVE");
 assert.equal(dv.getUint32(24,true),16000);
 assert.equal(dv.getUint16(22,true),1);
 assert.equal(dv.getUint16(34,true),16);
 assert.equal(wave.length,32044);
});
test("transcodage : découper un vocal 10 secondes sous la limite NVIDIA",async()=>{
 const decoded=pcm(10);
 const result=await convertTelegramOggToWav(sampleOgg(),{decode:async()=>decoded});
 assert.equal(result.reason,null);
 assert.equal(result.chunks.length,3);
 assert.ok(result.chunks.every(x=>x.mime==="audio/wav"&&x.bytes.length<175000));
 assert.equal(result.durationSeconds,10);
});
test("transcodage : refuser proprement plus de 6 segments",async()=>{
 const result=await convertTelegramOggToWav(sampleOgg(),{decode:async()=>pcm(34)});
 assert.equal(result.reason,"audio_too_long_for_inline");
 assert.equal(result.chunks.length,0);
});
test("transcription : Nemotron Omni reçoit uniquement WAV base64 depuis Telegram",async()=>{
 const requests=[];
 const result=await transcribeTelegramAudio(sampleOgg(),{
   asrUrl:"",apiKey:"fake",
   decodeOgg:async()=>pcm(2),
   http:async(_url,opts)=>{
     const body=JSON.parse(opts.body);
     const content=body.messages[0].content;
     requests.push(content[0].audio_url.url);
     return {ok:true,json:async()=>({choices:[{message:{content:"Je veux rejoindre le canal Telegram."}}]})};
   }
 });
 assert.equal(requests.length,1);
 assert.match(requests[0],/^data:audio\/wav;base64,/);
 assert.ok(!requests[0].startsWith("data:audio/ogg"));
 assert.equal(result.source,"omni_converted_wav");
 assert.equal(result.quality,"clear");
 assert.match(result.transcript,/canal Telegram/);
});
test("transcription : segmentation 10 secondes exige confirmation du client",async()=>{
 const result=await transcribeTelegramAudio(sampleOgg(),{
   asrUrl:"",apiKey:"fake",decodeOgg:async()=>pcm(10),
   http:async()=>({ok:true,json:async()=>({choices:[{message:{content:"Je cherche les pronostics du jour."}}]})})
 });
 assert.equal(result.quality,"uncertain");
 assert.ok(result.reasons.includes("segmented_audio"));
});
test("transcription : priorité au vrai moteur ASR Ogg natif",async()=>{
 const seen=[];
 const result=await transcribeTelegramAudio(sampleOgg(),{
   asrUrl:"https://asr.example.org/v1/audio/transcriptions",
   apiKey:"fake",asrKey:"secret",decodeOgg:async()=>{throw Error("should not decode")},
   http:async(url,opts)=>{
      seen.push({url,headers:opts.headers});
      return {ok:true,json:async()=>({text:"Je veux créer un compte sur Betclic."})};
   }
 });
 assert.equal(seen.length,1);
 assert.ok(seen[0].url.endsWith("/v1/audio/transcriptions"));
 assert.equal(result.source,"dedicated_asr");
 assert.match(result.transcript,/Betclic/);
});
test("transcription : si le décodeur Ogg est indisponible, ne pas halluciner",async()=>{
 let calls=0;
 const result=await transcribeTelegramAudio(sampleOgg(),{
   asrUrl:"",apiKey:"fake",decodeOgg:async()=>{throw Error("decoder unavailable")},
   http:async()=>{calls++;throw Error("should not send raw Ogg")}
 });
 assert.equal(result.transcript,null);
 assert.equal(result.reason,"ogg_decode_failed");
 assert.equal(calls,0);
});
test("transcription : rejeter les transcriptions incohérentes observées",()=>{
 assert.equal(transcriptLooksCorrupted("Esquire monsieur est prononcé a o s e Esquire monsieur est prononcé"),true);
 assert.equal(transcriptLooksCorrupted("Je voudrais savoir comment installer le site"),false);
});
test("transcription : sortie absurde d'Omni est rejetée, jamais donnée à la conversation",async()=>{
 const result=await transcribeTelegramAudio(sampleOgg(),{
  asrUrl:"",apiKey:"fake",decodeOgg:async()=>pcm(1),
  http:async()=>({ok:true,json:async()=>({choices:[{message:{content:"Esquire monsieur est prononcé plan rencontre"} }]})})
 });
 assert.equal(result.transcript,null);
 assert.equal(result.reason,"audio_segment_not_transcribed");
});
