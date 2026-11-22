import {expiryNoticeText} from '../expiry-notice-outbox.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {copyExpiryCaption,PRIVATE_COPY_LIFETIME_HOURS,PRIVATE_COPY_LIFETIME_MS,privateCopyExpirySqlModifier} from '../private-copy-notice.mjs';

test('all private video notices show a 12-hour deadline in UTC',()=>{
 const start=Date.parse('2026-11-22T04:59:00.000Z');
 const txt=copyExpiryCaption('Mon film',{now:start});
 assert.equal(PRIVATE_COPY_LIFETIME_HOURS,12);
 assert.equal(PRIVATE_COPY_LIFETIME_MS,43200000);
 assert.match(txt,/Mon film/);
 assert.match(txt,/12 heures après son envoi/);
 assert.match(txt,/22\/11\/2026 à 16:59 \(UTC\)/);
 assert.match(txt,/Messages enregistrés/);
 assert.doesNotMatch(txt,/24 heures|24 h/);
 assert.ok(txt.length<=1024);
});
test('the message stays bounded even with an excessively long title',()=>{
 const txt=copyExpiryCaption('X'.repeat(5000),{now:Date.parse('2026-11-22T13:59:00Z')});
 assert.ok(txt.length<=1024);
 assert.match(txt,/23\/11\/2026 à 01:59 \(UTC\)/);
});

test('late receipts preserve original 24-hour promises but use 12 hours for new copies',()=>{
 assert.equal(privateCopyExpirySqlModifier('2026-11-22 05:14:43'),'+24 hours');
 assert.equal(privateCopyExpirySqlModifier('2026-11-22 05:14:44'),'+12 hours');
 assert.equal(privateCopyExpirySqlModifier('2026-11-22T05:30:00Z'),'+12 hours');
 assert.throws(()=>privateCopyExpirySqlModifier('not-a-date'),/invalid_sent_at/);
});

test('separate single-film expiry message follows the actual D1 deletion deadline',()=>{
 const text=expiryNoticeText({
  mediaCount:1,firstExpiry:'2026-11-22 18:04:00',lastExpiry:'2026-11-22 18:04:00'
 });
 assert.match(text,/Cette vidéo sera supprimée automatiquement de ce chat 12 heures après son envoi/);
 assert.match(text,/Suppression prévue : 22\/11\/2026 à 18:04 \(UTC\)/);
 assert.match(text,/Messages enregistrés/);
 assert.doesNotMatch(text,/🎬/);
});
test('multi-video expiry message announces the first and last deletion separately',()=>{
 const text=expiryNoticeText({
  mediaCount:3,firstExpiry:'2026-11-22 18:04:00',lastExpiry:'2026-11-22 18:11:00'
 });
 assert.match(text,/Ces 3 vidéos seront supprimées automatiquement/);
 assert.match(text,/Première suppression prévue : 22\/11\/2026 à 18:04/);
 assert.match(text,/Dernière suppression prévue : 22\/11\/2026 à 18:11/);
});
