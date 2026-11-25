import test from 'node:test';
import assert from 'node:assert/strict';
import {sanitizeFormationText,inspectFormationCover,formationHeading,
 matchFormationFilename,formationFilePart,telegramCaption}
 from '../formation-content-safety.mjs';
const cover='📊 Tout savoir sur la Data Science avec Python – Formation ultime avec Sébastien Daviot\n\n🎥 Vidéo | 🗣 Français | 🎓 Formateur : Sébastien Daviot | ⏱️ Durée : 52h\n\n🚀 Maîtrise Python pour analyser les données.';
test('recognize real unstructured educational cover with title and descriptive text',()=>{
 const a=inspectFormationCover(cover);
 assert.ok(a);
 assert.equal(a.category,'formation_digitale');
 assert.match(a.title,/Data Science/);
 assert.match(a.caption,/analyser les données/);
});
test('ignore casual messages, ad posts, link shares and unrelated photos',()=>{
 for(const s of ['Il faut liker et vous abonner !',
  '📢 Abonnez-vous sur @publique pour le prochain cours.',
  'https://t.me/channel\nLikez et partagez !',
  'Mes notes personnelles\nJe sauvegarde ça ici pour plus tard.']){
  assert.equal(inspectFormationCover(s),null,s);
 }
 assert.equal(inspectFormationCover(''),null);
 assert.equal(inspectFormationCover('Cybercriminalité'),null);
});
test('safe outgoing text preserves teaching descriptions but drops URLs, handles and promos',()=>{
 const raw='📚 Cours complet de Python\n✅ Apprendre à programmer en Python\n'+
  'Abonnez-vous sur @promobot\nSite : https://example.com/a?b=2\n'+
  'Lien : t.me/example\nContact : @someone\n'+
  '[voir le cours](https://example.com/malware)\nCours: python-2026';
 const result=sanitizeFormationText(raw);
 assert.match(result,/Apprendre à programmer en Python/);
 assert.match(result,/Cours: python-2026/);
 for(const x of ['https://','t.me/','@promobot','@someone','Abonnez-vous'])
  assert.equal(result.includes(x),false,result);
});
test('Telegram clickable hidden entity uses UTF16 offsets and is stripped',()=>{
 const t='Cours Python 😃 cliquez ici';
 const o=t.indexOf('cliquez ici');
 const clean=sanitizeFormationText(t,[{type:'text_link',offset:o,length:11,url:'https://example.com'}]);
 assert.equal(clean,'Cours Python 😃');
});
test('filenames match ONLY one proven course cover, ignoring post adjacency',()=>{
 const a=matchFormationFilename('Sébastien_Daviot_DATA_SCIENCE_avec_Python_en_2026_le_cours_ULTIME.rar',
  [{message_id:10,caption:cover}]);
 assert.equal(a.reason,'unique_filename_cover');
 assert.equal(a.cover.message_id,10);
 assert.equal(a.cover.category,'formation_digitale');
 assert.equal(matchFormationFilename('sauvegarde.zip',[{message_id:10,caption:cover}]).cover,null);
 const duplicated=[{message_id:10,caption:cover},{message_id:12,caption:cover}];
 assert.equal(matchFormationFilename('Data_Science_Python.rar',duplicated).reason,'ambiguous_matching_covers');
});
test('metadata filename parts recognized, ambiguous totals require explicit markers',()=>{
 assert.deepEqual(formationFilePart('Partie: 2/3\nTotal: 3','module.zip'),
  {number:2,total:3,explicit:true});
 assert.deepEqual(formationFilePart('','PowerBI_part2.rar'),
  {number:2,total:null,explicit:false});
 assert.deepEqual(formationFilePart('','PowerBI.pdf'),
  {number:1,total:1,explicit:false});
 assert.equal(formationFilePart('Partie: 3/2','module.zip'),null);
});
test('shortened captions cannot reintroduce advertising URLs',()=>{
 const full=cover+'\n'+('Description détaillée. '.repeat(120))+
 '\nAbonnez-vous @bad\nhttps://t.me/bad';
 const output=telegramCaption(full);
 assert.ok(output.length<=1024);
 assert.equal(output.includes('t.me/'),false);
 assert.equal(output.includes('@bad'),false);
});
test('actual business and finance covers route without manual Cours tags',()=>{
 const business='🎬 Antoine BM - Business 14 Jours : La méthode pour vivre de ses formations\n🎥 Vidéo | Durée 5h\nDécouvrez le programme de cette formation.';
 assert.equal(inspectFormationCover(business).category,'formation_business');
 const finance='📉 Tout savoir sur le trading et la bourse – Formation complète\n🎥 Vidéo de 10h\nApprenez à investir.';
 assert.equal(inspectFormationCover(finance).category,'formation_finance');
});
