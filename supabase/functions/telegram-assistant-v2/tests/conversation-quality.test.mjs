import test from 'node:test';
import assert from 'node:assert/strict';
import {
 LINKS, socialMediaRequest, officialSocialUrls, officialSocialMessage,
 verifiedReplyReview, contextualDestinations, intentFor,
 guidedMode, guideIsContinuation, answerRelevanceGuard,
 rankNvidiaModels, NVIDIA_MODELS, buildTelegramMessage, qualityMetrics, redactSensitiveText,
 privacyCommand, deletionConfirmationValid
} from '../index.js';

test('all social networks on explicit request',()=>{
 const q='Envoi moi le lien des réseaux sociaux';
 assert.equal(intentFor(q),'social');
 assert.equal(officialSocialUrls(q).length,6);
 assert.equal(contextualDestinations(q).length,6);
 const answer=verifiedReplyReview('Voici Telegram uniquement.',q);
 for(const name of ['WhatsApp','Facebook','Instagram','YouTube','Threads','Telegram'])
  assert.ok(answer.includes(name),name);
});
test('a single social request keeps its scope',()=>{
 assert.deepEqual(officialSocialUrls('Donne le lien Instagram'),[LINKS.instagram]);
 assert.equal(officialSocialUrls('Donne le lien du site').length,0);
});
test('unverified TikTok cannot be invented',()=>{
 assert.match(officialSocialMessage('Donne lien TikTok'),/non encore vérifié/);
 assert.deepEqual(officialSocialUrls('Donne lien TikTok'),[]);
});
test('more than three links are preserved as safe anchors',()=>{
 const urls=officialSocialUrls('réseaux sociaux');
 const m=buildTelegramMessage(officialSocialMessage('réseaux sociaux'),{allowedUrls:urls});
 assert.equal(m.reply_markup.inline_keyboard.length,3);
 assert.match(m.text,/<a href=/);
});
test('thanks and acknowledgment are contextual',()=>{
 assert.equal(verifiedReplyReview('Information indisponible','Merci !'),'Avec plaisir 😊');
 assert.equal(verifiedReplyReview('Quel bookmaker ?','Daccord'),'Parfait 👍');
});
test('false statement about PWA is corrected',()=>{
 assert.match(answerRelevanceGuard('Il n’y a pas d’application à installer.','Comment installer le site'),/installer.html/);
});
test('misspelled guided request is recognized',()=>{
 assert.equal(guidedMode('aide moi de pas a as'),true);
});
test('choice of bookmaker preserves an active guide',()=>{
 assert.equal(guideIsContinuation('melbet',{mode:'guided',bookmaker:'linebet'}),true);
 assert.equal(guideIsContinuation('line bet',{mode:'guided',bookmaker:'linebet'}),true);
 assert.equal(guideIsContinuation('un autre sujet',{mode:'guided',bookmaker:'linebet'}),false);
});
test('dynamic model ranking prioritizes proven successes',()=>{
 const first=NVIDIA_MODELS[0],second=NVIDIA_MODELS[1];
 const observations=[...Array(4)].map(()=>({model:first,status:'timeout',duration_ms:4800}))
   .concat([...Array(4)].map(()=>({model:second,status:'ok',duration_ms:1500})));
 const sorted=rankNvidiaModels(observations);
 assert.equal(sorted[0],second);
 assert.equal(sorted.length,NVIDIA_MODELS.length);
 assert.equal(new Set(sorted).size,NVIDIA_MODELS.length);
 assert.equal(sorted.at(-1),first);
});
test('ranking without observations is stable',()=>{
 assert.deepEqual(rankNvidiaModels([]),NVIDIA_MODELS);
});

test('private quality dashboard counts no message contents',()=>{
 const metrics=qualityMetrics({
  events:[{source:'chat',status:'ok'},{source:'chat',status:'timeout'},{source:'speech',status:'ok'}],
  messages:[{role:'user',content:'private'},{role:'assistant',content:'private'}],
  updates:[{}]
 });
 assert.equal(metrics.users,1);
 assert.equal(metrics.answers,1);
 assert.equal(metrics.nvidiaSuccess,1);
 assert.equal(metrics.nvidiaTimeouts,1);
 assert.equal(metrics.voiceAttempts,1);
 assert.equal(JSON.stringify(metrics).includes('private'),false);
});

test('OTP and API secrets must be redacted before AI context',()=>{
 const masked=redactSensitiveText('code OTP est 123456 et clé nvapi-abcdefghijklmnopq123456');
 assert.ok(!masked.includes('123456'));
 assert.ok(!masked.includes('abcdefghijklmnopq123456'));
 assert.match(masked,/MASQUÉ/);
});

test('privacy deletion requires an exact user command and fresh confirmation',()=>{
 assert.equal(privacyCommand('/delete_my_data'),'request_delete');
 assert.equal(privacyCommand('/confirm_delete_my_data'),'confirm_delete');
 assert.equal(privacyCommand('efface les données de mon voisin'),null);
 assert.equal(deletionConfirmationValid({mode:'awaiting_deletion',updated_at:new Date(100000).toISOString()},100000),true);
 assert.equal(deletionConfirmationValid({mode:'awaiting_deletion',updated_at:new Date(100000).toISOString()},500000),false);
 assert.equal(deletionConfirmationValid({mode:'guided',updated_at:new Date(100000).toISOString()},100000),false);
});
