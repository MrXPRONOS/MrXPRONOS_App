import test from 'node:test';
import assert from 'node:assert/strict';
import {calculateCoupon,parseCouponCommand} from '../src/logic.js';

const bet=(odds)=>({match:'Équipe A - Équipe B',market:'1X',odds});
test('4.08 est valide',()=>assert.equal(calculateCoupon([bet('1.70'),bet('2.40')]).total,'4.08'));
test('4.00 exact est accepté',()=>assert.equal(calculateCoupon([bet('2.00'),bet('2.00')]).total,'4.00'));
test('3.99 refusé',()=>assert.throws(()=>calculateCoupon([bet('3.99')]),/inférieure/));
test('3.999 arrondi à 4.00 est refusé',()=>assert.throws(()=>calculateCoupon([bet('2.15'),bet('1.86')]),/inférieure/));
test('cotes invalides refusées',()=>assert.throws(()=>calculateCoupon([bet('a')]),/invalide/));
test('bornes de cote respectées',()=>assert.throws(()=>calculateCoupon([bet('1.00'),bet('4.01')]),/limites/));
test('parsing administration valide',()=>{
 const c=parseCouponCommand('VIP | 30 | 2099-01-01T00:00 | -1 | Test | A - B ; 1X ; 2.00 | C - D ; 2X ; 2.10');
 assert.equal(c.total_odds,'4.20');assert.equal(c.stock,-1);assert.equal(c.xp_cost,30);
 assert.equal(JSON.parse(c.selections).length,2);
});
test('coût négatif refusé',()=>assert.throws(()=>parseCouponCommand('VIP | -1 | 2099-01-01T00:00 | -1 | Test | A - B ; 1X ; 4.20'),/Prix XP/));
test('date expirée refusée',()=>assert.throws(()=>parseCouponCommand('VIP | 30 | 2020-01-01T00:00 | -1 | Test | A - B ; 1X ; 4.20'),/Date UTC/));
