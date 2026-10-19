import assert from 'node:assert/strict';
import {moneyGlobalUsd,moneyPriceUsd,validateGlobalUsd,shortDateFr} from './crypto_poster_format.mjs';

assert.match(moneyGlobalUsd(2_718_295_617_920), /2.*718.*Md USD/);
assert.match(moneyGlobalUsd(84_134_511_488), /84,13 Md USD/);
assert.match(moneyPriceUsd(0.000004123456), /0,0000041235 USD/);
assert.match(moneyPriceUsd(0.000000049), /0,000000049 USD/);
assert.equal(shortDateFr('2026-10-18'), '18/10');
assert.equal(shortDateFr('2026-10-12'), '12/10');
assert.throws(()=>validateGlobalUsd(2.72e21,84e18),/outside plausible/);
assert.deepEqual(validateGlobalUsd(2.72e12,84e9),{cap:2.72e12,volume:84e9});
assert.throws(()=>moneyPriceUsd(0),/Invalid/);
console.log('QUALITY_10_JS_FORMAT_CHECKS_PASSED');
