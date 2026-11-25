import test from 'node:test';
import assert from 'node:assert/strict';
import {planFormationBacklog} from '../formation-backlog-production.mjs';
const source='-1001111111111';
const base=(id,kind,caption='',file='',category='formation_general')=>({
 chat_id:source,message_id:id,kind,caption,filename:file,
 file_unique_id:'unique-'+id,category,state:'needs_review',
 review_code:'training_category_unknown'
});
const fiche=base(50,'poster',
 '📊 Tout savoir sur Excel avec Copilot – Guide complet avec Philippe Riquelme\n'+
 '🎓 Auteur : Philippe Riquelme\n📚 Ebook en français avec exercices de niveau avancé.\n'+
 '🚀 Apprends à analyser les données dans Excel avec Copilot.');
const file=base(51,'course_file','',
 "Excel_avec_Copilot_L'IA_qui_fait_le_travail_à_votre_place.epub");
test('backfill picks complete course despite interleaved promotional text',()=>{
 const ad=base(52,'text','Il faut liker et s’abonner à @channel.');
 const r=planFormationBacklog([fiche,ad,file]);
 assert.equal(r.accepted.length,1);
 assert.equal(r.accepted[0].item.category,'formation_digitale');
 assert.deepEqual(r.accepted[0].item.parts.map(p=>p.message_id),[51]);
 assert.equal(r.accepted[0].proposals[0].caption.includes('@channel'),false);
});
test('file without matching cover never selected even if adjacent',()=>{
 const rows=[fiche,base(55,'course_file','',
  'facture-secrete-personnelle.pdf')];
 assert.equal(planFormationBacklog(rows).accepted.length,0);
});
test('incomplete multipart course stays in review',()=>{
 const rows=[base(70,'poster',
  '📊 Tout savoir sur Power BI – Formation complète\n🎥 Vidéo de cours\n'+
  'Apprends les outils Power BI et la data visualisation.'),
  base(71,'course_file','','Power_BI_formation_part1.rar'),
  base(72,'text','Likez et partagez avec vos amis!'),
  base(73,'course_file','','Power_BI_formation_part2.rar')];
 assert.equal(planFormationBacklog(rows).accepted.length,0);
});
test('complete multipart with total survives announcement interruption',()=>{
 const rows=[base(70,'poster',
  '📊 Tout savoir sur Power BI – Formation complète\n🎥 Vidéo de cours\n'+
  'Apprends les outils Power BI et la data visualisation.\nTotal: 2'),
  base(71,'course_file','','Power_BI_formation_part1.rar'),
  base(72,'text','Likez et partagez avec vos amis!'),
  base(73,'course_file','','Power_BI_formation_part2.rar')];
 const p=planFormationBacklog(rows);
 assert.equal(p.accepted.length,1);
 assert.deepEqual(p.accepted[0].item.parts.map(x=>x.message_id),[71,73]);
});
test('changed, published or explicitly conflicting files cannot be revived',()=>{
 assert.equal(planFormationBacklog([fiche,
  {...file,review_code:'source_media_changed'}]).accepted.length,0);
 assert.equal(planFormationBacklog([fiche,
  {...file,state:'published'}]).accepted.length,0);
 assert.equal(planFormationBacklog([fiche,
  {...file,review_code:'conflicting_course_covers'}]).accepted.length,0);
});
test('two posters claiming the same title are not auto paired',()=>{
 const duplicates=[fiche,{...fiche,message_id:58,file_unique_id:'unique-58'},file];
 assert.equal(planFormationBacklog(duplicates).accepted.length,0);
});
test('never selects more than two courses in one cycle',()=>{
 const b=base(65,'poster',
 '🎬 Antoine BM - Business 14 Jours : Formation complète\n'+
 '🎥 Vidéo en français\nDécouvrez le programme complet de cette formation.');
 const bf=base(66,'course_file','','Antoine BM - Business 14 Jours.rar');
 const more=base(71,'poster',
 '📉 Tout savoir sur le trading et la bourse – Formation complète\n'+
 '🎥 Vidéo en français\nApprenez les marchés boursiers en profondeur.');
 const mf=base(72,'course_file','','trading_et_bourse.pdf');
 const results=planFormationBacklog([fiche,file,b,bf,more,mf]);
 assert.ok(results.accepted.length<=2);
});
