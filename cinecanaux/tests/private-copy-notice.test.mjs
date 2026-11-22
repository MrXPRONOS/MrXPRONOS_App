import test from 'node:test';
import assert from 'node:assert/strict';
import {copyExpiryCaption,PRIVATE_COPY_LIFETIME_HOURS,PRIVATE_COPY_LIFETIME_MS} from '../private-copy-notice.mjs';

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
