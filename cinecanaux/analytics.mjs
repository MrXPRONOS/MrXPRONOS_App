// Privacy-first first-party analytics, no IP, message content or raw Telegram IDs stored.
const enc=new TextEncoder(),hex=a=>[...new Uint8Array(a)].map(x=>x.toString(16).padStart(2,'0')).join('');
const sha=async x=>hex(await crypto.subtle.digest('SHA-256',enc.encode(x)));
const reply=(x,status=200)=>Response.json(x,{status,headers:{'cache-control':'no-store'}});
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
async function visitor(env,kind,id){return sha('cine-radar-analytics:'+env.TELEGRAM_WEBHOOK_SECRET+':'+kind+':'+id)}
export async function recordBotTouch(env,update){
 const msg=update?.message;
 if(msg?.chat?.type!=='private'||!Number.isSafeInteger(msg.from?.id))return;
 const hash=await visitor(env,'bot',msg.from.id),start=/^\/start(?:@[A-Za-z0-9_]+)?(?:\s|$)/i.test(String(msg.text||''));
 await env.DB.prepare('INSERT INTO analytics_bot_users(visitor_hash,starts) VALUES(?,?) ON CONFLICT(visitor_hash) DO UPDATE SET last_seen_at=CURRENT_TIMESTAMP,starts=starts+excluded.starts').bind(hash,start?1:0).run();
 await env.DB.prepare("INSERT INTO analytics_bot_days(visitor_hash,day_utc,starts) VALUES(?,date('now'),?) ON CONFLICT(visitor_hash,day_utc) DO UPDATE SET starts=starts+excluded.starts").bind(hash,start?1:0).run();
}
const PROMOS=new Set(['actufoot_mrxp','ActuCrypto24H','mrxpronosfr']);
const valid=(e,t)=>e==='share'?t==='bot':e==='rating'?/^[1-5]$/.test(t):e==='promo_open'?PROMOS.has(t):e==='channel_open'?/^c:[1-9]\d{0,9}$/.test(t):e==='pin_open'?/^p:(?:films|series|animes):[1-9]\d{0,12}$/.test(t):false;
export async function analyticsEvent(env,request){
 if(request.method!=='POST')return reply({error:'Method'},405);
 const u=new URL(request.url),origin=request.headers.get('origin');
 if(origin&&origin!==u.origin)return reply({error:'Origin'},403);
 let p;try{const raw=await request.text();if(raw.length>440)throw Error();p=JSON.parse(raw)}catch{return reply({error:'Payload'},400)}
 const event=String(p?.event||''),id=String(p?.id||'');
 if(event==='visit'||event==='ping'){
  if(!UUID.test(id))return reply({error:'ID'},400);
  const hash=await visitor(env,'app',id);
  await env.DB.prepare('INSERT INTO analytics_app_visitors(visitor_hash) VALUES(?) ON CONFLICT(visitor_hash) DO UPDATE SET last_seen_at=CURRENT_TIMESTAMP').bind(hash).run();
  if(event==='visit')await env.DB.prepare("INSERT INTO analytics_app_days(visitor_hash,day_utc,visits) VALUES(?,date('now'),1) ON CONFLICT(visitor_hash,day_utc) DO UPDATE SET visits=visits+1").bind(hash).run();
  return reply({ok:true});
 }
 const target=String(p?.target||'');
 if(!valid(event,target))return reply({error:'Event'},400);
 if(event==='channel_open'){
  const exists=await env.DB.prepare("SELECT id FROM channels WHERE id=? AND status='approved'").bind(Number(target.slice(2))).first();
  if(!exists)return reply({error:'Channel'},404);
 }
 await env.DB.prepare("INSERT INTO analytics_events_daily(day_utc,event_name,target_key,hits) VALUES(date('now'),?,?,1) ON CONFLICT(day_utc,event_name,target_key) DO UPDATE SET hits=hits+1").bind(event,target).run();
 return reply({ok:true});
}
function period(url){
 const mode=url.searchParams.get('period')||'30d',now=new Date(),day=n=>new Date(Date.now()-n*86400000).toISOString().slice(0,10),today=day(0);
 let from=today,to=today;
 if(mode==='yesterday'){from=day(1);to=from}
 else if(mode==='7d')from=day(6);
 else if(mode==='30d')from=day(29);
 else if(mode==='week')from=day((now.getUTCDay()+6)%7);
 else if(mode==='month')from=today.slice(0,7)+'-01';
 else if(mode==='year')from=today.slice(0,4)+'-01-01';
 else if(mode==='last-year'){const y=Number(today.slice(0,4))-1;from=y+'-01-01';to=y+'-12-31'}
 else if(mode==='all')from='2020-01-01';
 else if(mode==='custom'){from=url.searchParams.get('from')||'';to=url.searchParams.get('to')||'';if(!/^\d{4}-\d\d-\d\d$/.test(from)||!/^\d{4}-\d\d-\d\d$/.test(to)||from>to||from<'2020-01-01'||to>today)throw Error('Période invalide')}
 else if(mode!=='today')throw Error('Période invalide');
 return {mode,from,to};
}
export async function adminAnalytics(env,request){
 let time;try{time=period(new URL(request.url))}catch(e){return reply({error:e.message},400)}
 const {from,to}=time;
 const countSql=[
  'SELECT (SELECT COUNT(*) FROM analytics_bot_users WHERE starts>0) bot_total,',
  "(SELECT COUNT(*) FROM analytics_bot_users WHERE last_seen_at>=datetime('now','-5 minutes')) bot_recent,",
  '(SELECT COUNT(*) FROM analytics_app_visitors) app_total,',
  "(SELECT COUNT(*) FROM analytics_app_visitors WHERE last_seen_at>=datetime('now','-5 minutes')) app_active,",
  '(SELECT COUNT(DISTINCT visitor_hash) FROM analytics_bot_days WHERE day_utc BETWEEN ? AND ?) bot_unique,',
  '(SELECT COALESCE(SUM(starts),0) FROM analytics_bot_days WHERE day_utc BETWEEN ? AND ?) bot_starts,',
  '(SELECT COUNT(DISTINCT visitor_hash) FROM analytics_app_days WHERE day_utc BETWEEN ? AND ?) app_unique,',
  '(SELECT COALESCE(SUM(visits),0) FROM analytics_app_days WHERE day_utc BETWEEN ? AND ?) app_visits'
 ].join(' ');
 const queries=[
  env.DB.prepare(countSql).bind(from,to,from,to,from,to,from,to).first(),
  env.DB.prepare('SELECT day_utc,COUNT(*) unique_visitors,SUM(visits) visits FROM analytics_app_days WHERE day_utc BETWEEN ? AND ? GROUP BY day_utc ORDER BY day_utc DESC LIMIT 3800').bind(from,to).all(),
  env.DB.prepare('SELECT day_utc,COUNT(*) unique_visitors,SUM(starts) starts FROM analytics_bot_days WHERE day_utc BETWEEN ? AND ? GROUP BY day_utc ORDER BY day_utc DESC LIMIT 3800').bind(from,to).all(),
  env.DB.prepare('SELECT event_name,target_key,SUM(hits) hits FROM analytics_events_daily WHERE day_utc BETWEEN ? AND ? GROUP BY event_name,target_key ORDER BY hits DESC LIMIT 240').bind(from,to).all(),
  env.DB.prepare("SELECT c.title,c.link,SUM(e.hits) hits FROM analytics_events_daily e JOIN channels c ON c.id=CAST(SUBSTR(e.target_key,3) AS INTEGER) WHERE e.event_name='channel_open' AND e.day_utc BETWEEN ? AND ? GROUP BY e.target_key ORDER BY hits DESC LIMIT 20").bind(from,to).all(),
  env.DB.prepare('SELECT c.title,c.link,t.opens FROM channel_telemetry t JOIN channels c ON c.id=t.channel_id ORDER BY t.opens DESC LIMIT 12').all(),
  env.DB.prepare('SELECT p.kind,p.title,p.message_id,p.click_count,c.username FROM cine_pinned_posts p JOIN radar_primary_channels c ON c.kind=p.kind ORDER BY p.click_count DESC LIMIT 16').all()
 ];
 const [metrics,app,bot,events,channels,historical,pins]=await Promise.all(queries);
 const evt=events.results||[];
 const count=e=>evt.filter(x=>x.event_name===e).reduce((a,x)=>a+Number(x.hits),0);
 return reply({range:time,generated_at:new Date().toISOString(),metrics:Object.fromEntries(Object.entries(metrics||{}).map(([k,v])=>[k,Number(v)||0])),
  daily:{app:app.results||[],bot:bot.results||[]},events:{channel_open:count('channel_open'),pin_open:count('pin_open'),promo_open:count('promo_open'),share:count('share'),rating:count('rating')},
  top_channels:channels.results||[],historical_channels:historical.results||[],top_pins:pins.results||[],
  promos:evt.filter(x=>x.event_name==='promo_open'),ratings:evt.filter(x=>x.event_name==='rating'),
  note:'Depuis activation du suivi. Démarrages du bot ≠ abonnements confirmés ; clics Telegram ≠ adhésions. Statistiques anonymisées et sans fingerprint.'});
}
