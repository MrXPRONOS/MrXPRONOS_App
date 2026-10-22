// Free Pronos — anonymized request timing: no IDs, message text, IPs, hashes or tokens.
const ALLOWED_ROUTES=new Set(['/me','/coupons','/tasks','/history','/results','/mytickets','/admin/overview','/admin/tickets','/admin/performance','/support','/claim','/redeem','/channel-claim','/alerts','/callback','/message']);
export function routeLabel(path){
 const label=String(path||'').startsWith('/api/')?String(path).slice(4):String(path||'');
 return ALLOWED_ROUTES.has('/'+label.replace(/^\//,''))?'/'+label.replace(/^\//,''):'/other';
}
export function coloLabel(c){
 return typeof c==='string'&&/^[A-Z]{3}$/.test(c)?c:'UNK';
}
export function metricValue(value){
 return Number.isFinite(value)?Math.max(0,Math.min(120000,Math.round(value))):0;
}
export function newBotMetrics(now=performance.now()){
 return {start:now,telegram_ms:0,ack_ms:null,reply_ms:null,calls:0};
}
export function recordTelegram(metrics,method,elapsed,at=performance.now()){
 if(!metrics)return;
 metrics.calls=Math.min(30,metrics.calls+1);
 metrics.telegram_ms+=metricValue(elapsed);
 if(method==='answerCallbackQuery'&&metrics.ack_ms===null)metrics.ack_ms=metricValue(at-metrics.start);
 if(['sendMessage','editMessageText','editMessageReplyMarkup','sendPhoto'].includes(method)&&metrics.reply_ms===null)
   metrics.reply_ms=metricValue(at-metrics.start);
}
export async function storeSample(env,payload){
 if(!env?.DB)return false;
 const route=routeLabel(payload.route);
 const kind=['bot_callback','bot_message','miniapp'].includes(payload.kind)?payload.kind:'miniapp';
 const metrics=payload.metrics||{};
 await env.DB.prepare(
  'INSERT INTO perf_samples(kind,route,colo,response_ms,telegram_ms,callback_ack_ms,first_reply_ms,telegram_calls,status) VALUES(?,?,?,?,?,?,?,?,?)'
 ).bind(kind,route,coloLabel(payload.colo),metricValue(payload.response_ms),
  metricValue(metrics.telegram_ms||0),
  metrics.ack_ms==null?null:metricValue(metrics.ack_ms),
  metrics.reply_ms==null?null:metricValue(metrics.reply_ms),
  Math.min(30,Math.max(0,Number(metrics.calls)||0)),
  payload.status==='error'?'error':'ok'
 ).run();
 return true;
}
export function scheduleSample(ctx,env,payload){
 if(!ctx||typeof ctx.waitUntil!=='function')return;
 // The benchmark runner must not fabricate regional end-user traffic.
 if(payload.isBenchmark)return;
 const p=storeSample(env,payload).catch(error=>console.warn('Free Pronos perf sample failed:',String(error).slice(0,95)));
 ctx.waitUntil(p); // Never block user response on metrics writes.
}
const percentile=(numbers,f)=>{
 if(!numbers.length)return null;
 const a=numbers.slice().sort((x,y)=>x-y);
 return a[Math.max(0,Math.min(a.length-1,Math.ceil(f*a.length)-1))];
};
export function summarizeSamples(rows){
 const groups=new Map();
 for(const r of rows){
   const key=[r.kind,r.route,coloLabel(r.colo)].join(':');
   if(!groups.has(key))groups.set(key,{kind:r.kind,route:r.route,colo:coloLabel(r.colo),raw:[]});
   groups.get(key).raw.push(r);
 }
 return [...groups.values()].map(({kind,route,colo,raw})=>{
   const times=raw.map(x=>Number(x.response_ms)).filter(Number.isFinite);
   const first=raw.filter(x=>x.first_reply_ms!=null).map(x=>Number(x.first_reply_ms));
   const ack=raw.filter(x=>x.callback_ack_ms!=null).map(x=>Number(x.callback_ack_ms));
   return {kind,route,colo,samples:times.length,p50_ms:percentile(times,.5),p95_ms:percentile(times,.95),
     first_reply_p50_ms:percentile(first,.5),first_reply_p95_ms:percentile(first,.95),
     ack_p50_ms:percentile(ack,.5),telegram_ms_p50:percentile(raw.map(x=>Number(x.telegram_ms||0)),.5)};
 }).sort((a,b)=>b.samples-a.samples||a.route.localeCompare(b.route));
}
export async function performanceReport(env){
 const [sampleRows,probe]=await Promise.all([
  env.DB.prepare("SELECT kind,route,colo,response_ms,telegram_ms,callback_ack_ms,first_reply_ms FROM perf_samples WHERE observed_at>=strftime('%Y-%m-%dT%H:%M:%fZ','now','-7 days') ORDER BY id DESC LIMIT 3000").all(),
  (async()=>{const t=performance.now();await env.DB.prepare('SELECT 1 AS ready').first();return metricValue(performance.now()-t)})()
 ]);
 const rows=sampleRows.results||[];
 return {window:'7d',samples:rows.length,truncated:rows.length===3000,
  groups:summarizeSamples(rows),
  d1_probe_ms:probe,
  note:'Worker reçoit la requête -> réponse API. Le premier message et l’acquittement sont confirmés par Telegram API, pas l’affichage sur le téléphone. Colo Cloudflare = point de présence, pas position précise.'};
}
