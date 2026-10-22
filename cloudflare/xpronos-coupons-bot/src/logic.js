// Calcul strict des cotes, partagé entre le Worker et les tests Node.
// Les cotes sont décimales; seuil vérifié AVANT l'arrondi d'affichage.
export function calculateCoupon(items) {
  if (!Array.isArray(items) || items.length < 1 || items.length > 10) throw Error('Entre 1 et 10 sélections.');
  let numerator=1n, denominator=1n;
  const selections=items.map(s=>{
    const match=String(s.match||'').trim(), market=String(s.market||'').trim(), odds=String(s.odds||'').trim();
    if(!match||!market||match.length>120||market.length>120||!/^\d{1,3}(\.\d{1,4})?$/.test(odds)) throw Error('Sélection invalide. Format : Match ; Marché ; Cote (ex. 1.75).');
    const [whole,fraction='']=odds.split('.');
    const scaled=BigInt(whole)*10000n+BigInt(fraction.padEnd(4,'0'));
    if(scaled<=10000n||scaled>1000000n)throw Error('Cote individuelle hors limites (1.0001 à 100).');
    numerator*=scaled;denominator*=10000n;
    return {match,market,odds};
  });
  if(numerator<4n*denominator)throw Error('Cote totale inférieure à 4.00. Coupon refusé.');
  const cents=(numerator*100n+denominator/2n)/denominator;
  return {total:String(cents/100n)+'.'+String(cents%100n).padStart(2,'0'),selections};
}
export function parseCouponCommand(raw,now=Date.now()){
  const parts=raw.trim().split('|').map(s=>s.trim());
  if(parts.length<6)throw Error('Format : /addcoupon PRO | 50 | 2026-12-01T18:00 | -1 | Titre | Match ; Marché ; 1.70 | ...');
  const [category,cost,expiry,stock,title,...bets]=parts;
  const tier=category.toUpperCase();
  if(!['SIMPLE','PRO','VIP'].includes(tier))throw Error('Catégorie SIMPLE, PRO ou VIP obligatoire.');
  if(!/^\d{1,6}$/.test(cost)||Number(cost)>100000)throw Error('Prix XP invalide.');
  if(!/^-?\d{1,6}$/.test(stock)||Number(stock)<-1||Number(stock)>100000)throw Error('Stock invalide (-1 = illimité).');
  if(!title||title.length>120)throw Error('Titre invalide.');
  const ts=/(?:Z|[+-]\d{2}:\d{2})$/.test(expiry)?expiry:expiry+'Z';
  const date=new Date(ts);
  if(!Number.isFinite(date.getTime())||date.getTime()<=now)throw Error('Date UTC future invalide.');
  const selections=bets.map(s=>{
    const p=s.split(';').map(x=>x.trim());
    if(p.length!==3)throw Error('Format sélection : Match ; Marché ; Cote.');
    return {match:p[0],market:p[1],odds:p[2]};
  });
  const result=calculateCoupon(selections);
  return {tier,title,selections:JSON.stringify(result.selections),total_odds:result.total,xp_cost:Number(cost),expires_at:date.toISOString(),stock:Number(stock)};
}
