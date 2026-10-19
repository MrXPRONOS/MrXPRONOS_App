/** Shared French display and unit rules for every premium crypto poster. */
export function finitePositive(value,name='financial amount'){
  const n=Number(value);
  if(typeof value==='boolean'||!Number.isFinite(n)||n<=0)throw Error('Invalid '+name);
  return n;
}
export function validateGlobalUsd(cap,volume){
  const c=finitePositive(cap,'market cap USD');
  const v=finitePositive(volume,'24h global volume USD');
  if(c<1e11||c>1e14||v<1e9||v>1e13||v>c*3)
    throw Error('Global USD figures outside plausible market order of magnitude; check provider units');
  return {cap:c,volume:v};
}
export function moneyGlobalUsd(value){
  const n=finitePositive(value,'global USD value');
  return (n/1e9).toLocaleString('fr-FR',{minimumFractionDigits:0,maximumFractionDigits:2})+' Md USD';
}
export function moneyPriceUsd(value){
  const n=finitePositive(value,'crypto USD price');
  if(n<1e-10) return n.toExponential(4).replace('.',',')+' USD';
  let dec=n>=100?2:n>=1?3:n>=0.01?6:n>=0.0001?8:n>=0.000001?10:12;
  const rounded=n.toLocaleString('fr-FR',{minimumFractionDigits:n>=1?2:0,maximumFractionDigits:dec});
  if(Number(rounded.replace(/\s|\u202f/g,'').replace(',','.'))===0)
    throw Error('A small token price was rounded to zero');
  return rounded+' USD';
}
export function shortDateFr(iso){
  const m=/^\d{4}-(\d{2})-(\d{2})/.exec(String(iso));
  if(!m)throw Error('Invalid daily date');
  return m[2]+'/'+m[1];
}
