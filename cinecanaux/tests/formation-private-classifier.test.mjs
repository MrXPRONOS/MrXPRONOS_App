import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyFormationPost,courseId,FORMATION_CATEGORIES}
 from '../formation-private-classifier.mjs';
test('exactly five destination categories share one intake',()=>{
 assert.deepEqual(FORMATION_CATEGORIES,[
  'formation_general','formation_business','formation_finance',
  'formation_digitale','formation_mindset']);
});
test('explicit French category routes even a neutral course title',()=>{
 for(const [name,expected] of [
  ['Business','formation_business'],['Finance','formation_finance'],
  ['Digitale','formation_digitale'],['Mindset','formation_mindset'],
  ['Générale','formation_general']]){
  assert.equal(classifyFormationPost(
   'Cours: cours-test-2026\nCatégorie: '+name+'\nAuteur: Formateur').category,expected);
 }
});
test('explicit category cannot be overridden by other unrelated keywords',()=>{
 const result=classifyFormationPost('Cours: trading-debutants\nCatégorie: Business');
 assert.equal(result.category,'formation_business');
 assert.equal(result.reason,'explicit');
});
test('title-only automatic categorization requires one domain',()=>{
 assert.equal(classifyFormationPost('Cours: investissement-bourse-2026').category,
  'formation_finance');
 assert.equal(classifyFormationPost('Cours: python-debutants').category,
  'formation_digitale');
 assert.equal(classifyFormationPost('Cours: leadership-pratique').category,
  'formation_mindset');
});
test('ambiguous titles are quarantined and never guessed to general',()=>{
 for(const caption of ['Cours: trading-marketing-2026',
                      'Cours: formation-avancee-2026','Cours: trading\nCatégorie: ???',
                      'Cours: leadership\nCatégorie: Business\nCatégorie: Finance']){
  const result=classifyFormationPost(caption);
  assert.equal(result.category,null,caption);
 }
});
test('files with neutral titles inherit a single confirmed course cover',()=>{
 const poster={category:'formation_business',
  caption:'Cours: entreprise-2026\nCatégorie: Business\nAuteur: Auteur autorisé'};
 const result=classifyFormationPost(
  'Cours: entreprise-2026\nTotal: 2\nPartie: 1/2','doc-part01.zip',[poster]);
 assert.equal(result.category,'formation_business');
 assert.equal(result.reason,'matching_course_cover');
});
test('two conflicting course covers block all subsequent documents',()=>{
 const covers=[
  {category:'formation_business',caption:'Cours: cours-2026\nCatégorie: Business'},
  {category:'formation_finance',caption:'Cours: cours-2026\nCatégorie: Finance'}
 ];
 assert.equal(classifyFormationPost('Cours: cours-2026\nPartie: 1/1','module.zip',covers).category,null);
});
test('course ID parser must be exact and bounded',()=>{
 assert.equal(courseId('Cours: abc-2026\nAuteur: Test'),'abc-2026');
 assert.equal(courseId('Cours: Invalid Name!'),null);
 assert.equal(courseId('Pas un Cours: abc-2026'),null);
});
