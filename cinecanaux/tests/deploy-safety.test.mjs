import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const deploy=readFileSync(new URL('../../.github/workflows/cine-radar-production-deploy.yml',import.meta.url),'utf8');
const ci=readFileSync(new URL('../../.github/workflows/cine-radar-v2-ci.yml',import.meta.url),'utf8');

test('production deploy never runs on an untested direct push',()=>{
 assert.doesNotMatch(deploy,/^  push:\s*$/m);
 assert.match(deploy,/workflow_run:\s*\n\s*workflows:.*Minimal directory CI/);
 assert.match(deploy,/github\.event\.workflow_run\.conclusion == 'success'/);
 assert.match(deploy,/github\.event\.workflow_run\.event == 'push'/);
 assert.match(deploy,/github\.event\.workflow_run\.head_branch == 'main'/);
 assert.match(deploy,/ref: \$\{\{ github\.event\.workflow_run\.head_sha \}\}/);
 assert.match(deploy,/persist-credentials: false/);
});
test('CI actually runs when deployment policy changes',()=>{
 const triggers=ci.split('  pull_request:')[0]||'';
 assert.match(triggers,/cine-radar-production-deploy\.yml/);
 assert.match(ci,/Guard CI-before-deploy invariants/);
 assert.match(ci,/node --test cinecanaux\/tests\/deploy-safety\.test\.mjs/);
});
