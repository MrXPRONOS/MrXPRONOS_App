import { calculateCoupon, parseCouponCommand } from './coupon_logic.ts';
function assert(condition: boolean, reason: string) { if (!condition) throw Error(reason); }
Deno.test('cote 4.00 acceptée',()=>assert(calculateCoupon([{match:'A',market:'B',odds:'4.00'}]).total==='4.00','4.00'));
Deno.test('cote 4.08 calculée',()=>assert(calculateCoupon([{match:'A',market:'B',odds:'1.70'},{match:'C',market:'D',odds:'2.40'}]).total==='4.08','4.08'));
Deno.test('3.99 refusée',()=>{let e=false;try{calculateCoupon([{match:'A',market:'B',odds:'3.99'}])}catch{e=true}assert(e,'3.99')});
Deno.test('3.9999 refusée même si arrondie',()=>{let e=false;try{calculateCoupon([{match:'A',market:'B',odds:'3.9999'}])}catch{e=true}assert(e,'3.9999')});
Deno.test('date passée refusée',()=>{let e=false;try{parseCouponCommand('PRO | 5 | 2020-01-01T18:00 | -1 | Coupon | A ; B ; 4')}catch{e=true}assert(e,'expiration')});
Deno.test('commande coupon valide',()=>{let p=parseCouponCommand('PRO | 50 | 2099-01-01T18:00 | -1 | Test | A ; B ; 1.70 | C ; D ; 2.40'); assert(p.total_odds==='4.08'&&p.xp_cost===50,'commande')});
