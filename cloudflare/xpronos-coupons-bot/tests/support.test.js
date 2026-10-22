import test from 'node:test';
import assert from 'node:assert/strict';
import {supportGuide,ticketSummary} from '../src/support.js';
test('support Free Pronos explique commandes, sans données sensibles',()=>{const text=supportGuide();assert.match(text,/FREE PRONOS/);assert.match(text,/\/support/);assert.match(text,/\/mytickets/)});
test('les tickets affichés échappent les balises HTML',()=>{const text=ticketSummary([{id:12,status:'open',message:'<script>alert(1)</script>',admin_reply:null}]);assert.ok(!text.includes('<script>'));assert.match(text,/&lt;script&gt;/)});
