import test from 'node:test';
import assert from 'node:assert/strict';
import {
 intentFor, analyzeClientIntent, partnerFromMessage, verifiedReplyReview,
 guideIsContinuation, guideStateFromReply, guidedResponse, guideStepCompleted,
 keepOneGuideStep, officialSocialUrls, responseLinks, safetyResponse,
 formatAdminHistory, privacyCommand, LINKS
} from '../index.js';

// Scénarios anonymisés tirés de l'historique de test Telegram des 16–17 novembre.
// Aucun numéro de téléphone, identifiant, secret ou texte personnel sensible.
const cases=[
 ['Merci !','thanks'],
 ['Je veux les coupons du jour','pronos'],
 ['Comment rejoindre votre canal Telegram ?','canaux'],
 ['Montre-moi les résultats précédents','resultats'],
 ['Comment installer le site','site_nav'],
 ['Je veux un score exact','scores'],
 ['Je veux un cote 10','odds'],
 ['Je veux m’inscrire sur line bet','signup'],
 ['Aide moi pour m’inscrire sur linebet','signup'],
 ['Envoi moi le lien des réseaux sociaux','social']
];

test('historical client intents remain distinct',()=>{
 for(const [input,expected] of cases)
  assert.equal(intentFor(input),expected,input);
});
test('a thank-you never gets an irrelevant question',()=>{
 assert.equal(verifiedReplyReview('Je ne peux pas confirmer cette information.', 'Merci !'),'Avec plaisir 😊');
});
test('Line Bet and Mel Bet resolve to their exact bookmakers',()=>{
 assert.equal(partnerFromMessage('Je veux m’inscrire sur line bet'),'linebet');
 assert.equal(partnerFromMessage('mel bet'),'melbet');
});
test('unconfirmed brand Bedclicker cannot trigger a verified partner link',()=>{
 const context=analyzeClientIntent('Je veux créer un compte sur Bedclicker.');
 assert.equal(context.needsClarification,true);
 assert.match(safetyResponse({...context,dataRights:false}),/^$/);
 assert.deepEqual(responseLinks('signup','Je veux créer un compte sur Bedclicker'),[]);
});
test('one-step guide remains at the current step on acknowledgement',()=>{
 const prior={mode:'guided',goal:'Installation',step_number:2,step_text:'**Étape 2** Ouvre les réglages'};
 const reply=guidedResponse('**Étape 2**\n\nOuvre le menu','D’accord',[],prior);
 assert.equal(guideStepCompleted('D’accord'),false);
 assert.equal(guideStateFromReply('D’accord',reply,prior).step_number,2);
});
test('explicit confirmation advances by precisely one step',()=>{
 const prior={mode:'guided',goal:'Installation',step_number:2};
 const reply=guidedResponse('Étape 1 : Ouvre la suite.','fait',[],prior);
 assert.match(reply,/Étape 3/);
 assert.equal(guideStateFromReply('fait',reply,prior).step_number,3);
});
test('guide blocks do not leak the second step even when bold',()=>{
 const text='**Étape 1**\n\nOuvre le site.\n\n**Étape 2**\n\nSaisis ton code.';
 assert.equal(keepOneGuideStep(text),'**Étape 1**\n\nOuvre le site.');
});
test('asking for clarification must retain the active guide',()=>{
 assert.equal(guideIsContinuation('Je n’ai pas compris',{mode:'guided'}),true);
 assert.equal(guideIsContinuation('Je suis bloqué',{mode:'guided'}),true);
});
test('all known networks are supplied for plural request',()=>{
 assert.equal(officialSocialUrls('Envoi moi le lien des réseaux sociaux').length,6);
});
test('PWA explanation does not lose its installer destination',()=>{
 assert.equal(responseLinks('site_nav','Comment installer le site')[0],LINKS.installer);
});
test('a client private OTP is masked in administrator conversation history',()=>{
 const text=formatAdminHistory([{role:'user',content:'Code OTP est 123456'}]);
 assert.ok(!text.includes('123456'));
 assert.match(text,/MASQUÉ/);
});
test('privacy actions are specific and cannot target arbitrary chats',()=>{
 assert.equal(privacyCommand('/delete_my_data'),'request_delete');
 assert.equal(privacyCommand('efface le chat de quelqu’un'),null);
});
