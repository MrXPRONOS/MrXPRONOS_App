import test from 'node:test';
import assert from 'node:assert/strict';
import {selectVerifiedPilot} from '../formation-production-pilot.mjs';
const chat='-1001111111111';
const rows=[
 {chat_id:chat,message_id:93,category:'formation_digitale',kind:'poster',
  file_unique_id:'poster-original',
  caption:'📊 Tout savoir sur Excel avec Copilot – Guide complet avec Philippe Riquelme\n'+
   '📚 Livre / Ebook | Français | 🎓 Auteur : Philippe Riquelme\n'+
   '🚀 Découvre comment Microsoft Copilot s’intègre directement à Excel pour analyser tes données.',
  filename:'',state:'indexed'},
 {chat_id:chat,message_id:94,category:'formation_digitale',kind:'course_file',
  file_unique_id:'ebook-original',
  caption:'',filename:"Excel_avec_Copilot_L'IA_qui_fait_le_travail_à_votre_place.epub",
  state:'indexed'}
];
test('pilot selects only uniquely paired Excel Copilot fiche and EPUB',()=>{
 const x=selectVerifiedPilot(rows,chat);
 assert.equal(x.category,'formation_digitale');
 assert.equal(x.poster_message_id,93);
 assert.deepEqual(x.parts.map(p=>p.message_id),[94]);
 assert.match(x.description,/Copilot/);
});
test('cannot publish a second document with unknown completion',()=>{
 assert.throws(()=>selectVerifiedPilot([...rows,
  {...rows[1],message_id:95,file_unique_id:'another-file'}],chat));
});
test('cannot publish message from a different stock source',()=>{
 assert.throws(()=>selectVerifiedPilot([{...rows[0],chat_id:'-1002222222222'},rows[1]],chat));
});
test('cannot publish unlicensed or pending media',()=>{
 assert.throws(()=>selectVerifiedPilot([rows[0],{...rows[1],state:'needs_review'}],chat));
});
test('cannot publish a filename unrelated to course',()=>{
 assert.throws(()=>selectVerifiedPilot([rows[0],
  {...rows[1],filename:'personal-notes.epub'}],chat));
});
