// ESPN soccer score verification; never infer corners, cards or unsupported markets.
const LEAGUES=new Set(['eng.1','esp.1','ger.1','ita.1','fra.1','uefa.champions','uefa.europa','uefa.europa.conf','usa.1','por.1','ned.1','bra.1']);
export const MARKETS={HOME:'Victoire domicile',DRAW:'Match nul',AWAY:'Victoire extérieur',OVER_1_5:'Plus de 1,5 but',OVER_2_5:'Plus de 2,5 buts',UNDER_2_5:'Moins de 2,5 buts',BTTS_YES:'Deux équipes marquent',BTTS_NO:'Au moins une équipe sans but'};
export const safeLogo=raw=>{try{const u=new URL(raw);return u.protocol==='https:'&&u.hostname==='a.espncdn.com'?u.href:''}catch{return ''}};
export function validFixture(f){
 if(!f||!LEAGUES.has(f.league)||!/^[0-9]{5,16}$/.test(String(f.id))||!/^\d{4}-\d{2}-\d{2}$/.test(String(f.date)))return false;
 const date=Date.parse(f.date+'T12:00:00Z');return Number.isFinite(date)&&new Date(date).toISOString().slice(0,10)===f.date;
}
export function evaluateMarket(code,home,away){
 if(!Number.isInteger(home)||!Number.isInteger(away)||home<0||away<0||!MARKETS[code])return null;
 const outcomes={HOME:home>away,DRAW:home===away,AWAY:home<away,
 OVER_1_5:home+away>=2,OVER_2_5:home+away>=3,UNDER_2_5:home+away<=2,
 BTTS_YES:home>0&&away>0,BTTS_NO:home===0||away===0};return outcomes[code];
}
export async function getFixture(f,fetcher=fetch){
 if(!validFixture(f))throw Error('Référence ESPN invalide');
 const url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+f.league+'/scoreboard?dates='+f.date.replaceAll('-','');
 const res=await fetcher(url,{headers:{accept:'application/json'},signal:AbortSignal.timeout(9000)});
 if(!res.ok)throw Error('ESPN HTTP '+res.status);
 const data=await res.json(),ev=(data.events||[]).find(x=>String(x.id)===String(f.id));
 if(!ev)throw Error('Événement ESPN absent pour cette date');
 const competition=ev.competitions?.[0],arr=competition?.competitors||[];
 const home=arr.find(x=>x.homeAway==='home'),away=arr.find(x=>x.homeAway==='away');
 if(!home||!away)throw Error('Données équipes manquantes');
 const st=ev.status?.type||competition?.status?.type||{};
 const completed=st.completed===true&&String(st.name||'').toUpperCase().includes('FINAL');
 const score=completed?[Number(home.score),Number(away.score)]:null;
 if(score&&score.some(x=>!Number.isInteger(x)||x<0))throw Error('Score ESPN invalide');
 const display=x=>String(x.team?.displayName||x.team?.name||'').slice(0,110);
 const logo=x=>safeLogo(x.team?.logo||x.team?.logos?.[0]?.href||'');
 return {id:String(ev.id),league:f.league,date:f.date,competition:String(data.leagues?.[0]?.name||f.league).slice(0,110),
  home:display(home),away:display(away),homeLogo:logo(home),awayLogo:logo(away),
  completed,isLive:!completed&&(st.state==='in'||st.name==='STATUS_IN_PROGRESS'),
  score,source:'https://www.espn.com/soccer/match/_/gameId/'+encodeURIComponent(ev.id)};
}
export function settleCoupon(selections,matches){
 if(!Array.isArray(selections)||!selections.length)return {status:'review',reason:'Aucune sélection'};
 const items=[];let pending=false,losing=false;
 for(const s of selections){
  if(!validFixture(s.fixture)||!MARKETS[s.market_code])return {status:'review',reason:'Marché non calculable ou fixture manquante'};
  const key=[s.fixture.league,s.fixture.date,s.fixture.id].join('/');
  const game=matches.get(key);
  if(!game||!game.completed){pending=true;items.push({match_id:s.fixture.id,result:game?.isLive?'live':'pending'});continue}
  if(!game.score)return {status:'review',reason:'Score final manquant'};
  const won=evaluateMarket(s.market_code,game.score[0],game.score[1]);
  if(won===null)return {status:'review',reason:'Marché inconnu'};
  if(!won)losing=true;
  items.push({match_id:s.fixture.id,result:won?'won':'lost',score:game.score,source:game.source});
 }
 return {status:pending?'pending':losing?'lost':'won',items};
}
export async function settleFromESPN(env,fetcher=fetch,limit=5){
 const rows=(await env.DB.prepare("SELECT id,selections,result_status FROM coupons WHERE auto_settlement=1 AND active=1 AND result_status IN ('available','live') ORDER BY id ASC LIMIT ?").bind(Math.min(10,limit)).all()).results||[];
 const cache=new Map(),stats={checked:0,finished:0,needsReview:0,unavailable:0};
 for(const row of rows){
  let selections;try{selections=JSON.parse(row.selections)}catch{stats.needsReview++;continue}
  let error=null;const matches=new Map();
  for(const sel of selections){
   if(!validFixture(sel.fixture)||!MARKETS[sel.market_code]){error='Référence ou marché non pris en charge';break}
   const key=[sel.fixture.league,sel.fixture.date,sel.fixture.id].join('/');
   if(!cache.has(key)){
    try{cache.set(key,await getFixture(sel.fixture,fetcher))}catch(e){error=String(e).slice(0,150);cache.set(key,null)}
   }
   if(cache.get(key))matches.set(key,cache.get(key));
  }
  const report=error?{status:'review',reason:error}:settleCoupon(selections,matches);
  stats.checked++;
  if(report.status==='review'){stats.needsReview++;continue}
  if(report.status==='pending'){
   if(report.items?.some(i=>i.result==='live')&&row.result_status==='available'){
     await env.DB.prepare("UPDATE coupons SET result_status='live' WHERE id=? AND result_status='available'").bind(row.id).run();
   }
   continue;
  }
  const source=report.items?.find(i=>i.source)?.source||'';
  await env.DB.prepare("UPDATE coupons SET result_status=?,result_reviewed_at=?,result_source=?,settlement_report=?,settlement_checked_at=? WHERE id=? AND auto_settlement=1 AND result_status IN ('available','live')")
    .bind(report.status,new Date().toISOString(),source,JSON.stringify(report),new Date().toISOString(),row.id).run();
  stats.finished++;
 }
 return stats;
}
export function normalizeSelection(selection){
 if(!validFixture(selection?.fixture)||!MARKETS[selection.market_code])throw Error('Sélection ESPN non supportée');
 const odds=String(selection.odds||'').trim();
 if(!/^\d{1,3}(\.\d{1,4})?$/.test(odds))throw Error('Cote mal formatée');
 return {fixture:selection.fixture,market_code:selection.market_code,odds,market:MARKETS[selection.market_code],
   match:String(selection.match||'ESPN #'+selection.fixture.id).slice(0,120)};
}
