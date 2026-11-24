import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validArchive,archiveIdentityAllowed} from './actufoot-v2-backup-worker.mjs';
const path='assets/data/private/actufoot_v2/archive/matches/2026-01.aes.json';
const hash='a'.repeat(64);
const blob=JSON.stringify({format:'mrxp.actufoot.v2.aes256gcm',archive_context:path,collection:'matches',key_version:2,ciphertext_b64:'abc',nonce_b64:'abc'});
test('validate V3 archive context',()=>assert.equal(validArchive(path,hash,blob),true));
test('reject cross-context, audit, invalid periods and key downgrade',()=>{
 for(const p of [path.replace('matches','audit'),path.replace('01','13'),path.replace('01','02')])assert.equal(validArchive(p,hash,blob),false);
 assert.equal(validArchive(path,hash,blob.replace('"key_version":2','"key_version":1')),false);
});

test('archive OIDC auto limited to main workflow event or protected manual environment',()=>{
  assert.equal(archiveIdentityAllowed({event_name:'schedule'},'archive'),true);
  assert.equal(archiveIdentityAllowed({event_name:'push'},'archive'),true);
  assert.equal(archiveIdentityAllowed({event_name:'workflow_dispatch'},'archive'),false);
  assert.equal(archiveIdentityAllowed({event_name:'schedule',environment:'other'},'archive'),false);
  assert.equal(archiveIdentityAllowed({event_name:'workflow_dispatch',environment:'actu-foot-v2-maintenance'},'archive'),true);
});
