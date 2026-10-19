import {moneyGlobalUsd,moneyPriceUsd,validateGlobalUsd,shortDateFr} from './crypto_poster_format.mjs';
/** #07 — Bilan des sept derniers jours, 1080 x 1350, Playwright. */
import {chromium} from 'playwright';
import {readFile,mkdir} from 'node:fs/promises';
const demo=process.argv.includes('--demo');
const file=demo?'crypto/generated/test/weekly_v2_demo.json':'crypto/generated/test/weekly_v2_data.json';
const output=demo?'crypto/generated/test/weekly_v2_demo.png':'crypto/generated/test/weekly_v2.png';
const d=JSON.parse(await readFile(file,'utf8'));
if(d.status!==(demo?'demo':'real_data')||d.is_demo!==demo)throw Error('Type of data mismatched');
if(d.provider!==(demo?'SIMULATION':d.provider)||(!demo&&!['CoinPaprika','CoinLore'].includes(d.provider)))throw Error('Bad provider');
const n=(v,digits=1)=>Number(v).toLocaleString('fr-FR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>(v>0?'+':v<0?'−':'')+n(Math.abs(v),2)+' %';
const changeColor=v=>v>=0?'#71EDBD':'#FF839E';
const dollar=moneyGlobalUsd;
validateGlobalUsd(d.market_cap_usd,d.volume_24h_usd);
for(const x of ['market_cap_usd','volume_24h_usd','btc_dominance_pct'])if(!Number.isFinite(d[x])||d[x]<=0)throw Error('Invalid metric '+x);
for(const a of ['btc','eth'])if(!d[a]||!Number.isFinite(d[a].change_7d))throw Error('Missing major');
for(const typ of ['winners','losers'])if(!Array.isArray(d[typ])||d[typ].length!==3||d[typ].some(x=>!Number.isFinite(x.change_7d)))throw Error('Invalid ranking');
if(!d.fear||!Number.isInteger(d.fear.score)||!Number.isInteger(d.fear.delta_7d))throw Error('Invalid fear');
const now=new Date(d.collected_at);
if(!Number.isFinite(now.valueOf()))throw Error('Invalid time');
const date=now.toLocaleDateString('fr-FR',{timeZone:'UTC',day:'2-digit',month:'long',year:'numeric'});
const coinArt={};
for(const [sym,file] of Object.entries({BTC:'btc.png',ETH:'eth.png'})){
 const bytes=await readFile('crypto/assets/premium_market/'+file);
 if(bytes.length<500)throw Error('Missing verified premium artwork '+sym);
 coinArt[sym]='data:image/png;base64,'+bytes.toString('base64');
}
const coin=(a,icon)=>'<div class="coin"><div class="coin-icon"><img alt="'+esc(a.symbol)+'" src="'+coinArt[a.symbol]+'"/></div><div class="coin-main"><div class="coin-symbol">'+esc(a.symbol)+'</div><div class="coin-price">'+n(a.price_usd,2)+' $</div></div><div class="coin-change" style="color:'+changeColor(a.change_7d)+'">'+pct(a.change_7d)+'</div></div>';
const ranking=(items)=>items.map((a,i)=>'<div class="rank"><span class="rank-num">0'+(i+1)+'</span><b>'+esc(a.symbol)+'</b><strong style="color:'+changeColor(a.change_7d)+'">'+pct(a.change_7d)+'</strong></div>').join('');
// Eight daily observations contain exactly seven successive 24-hour intervals.
const history=d.fear.history.slice(-8);
if(history.length!==8)throw Error('Not enough Fear history');
const bars=history.map((h,i)=>'<div class="bcell"><span>'+h.score+'</span><div class="bwrap"><i style="height:'+h.score+'%;background:'+(h.score>=55?'#76dda7':h.score>=45?'#f6c47c':'#fa8a95')+'"></i></div><small>'+esc(shortDateFr(h.date))+'</small></div>').join('');
const html='<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>'+
'*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden}body{font-family:Arial,Helvetica,sans-serif;color:#f9fbff;background:radial-gradient(ellipse at 105% -20%,#276396 0%,transparent 49%),radial-gradient(ellipse at -20% 100%,#254a7b 0%,transparent 49%),linear-gradient(155deg,#061226,#0a1d37 68%,#071024)}.page{position:relative;padding:42px 54px 28px}.top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #466c8a;padding-bottom:22px}.edition{color:#f3c786;font-size:17px;font-weight:900;letter-spacing:3px}.brand{font-size:27px;font-weight:900;letter-spacing:.6px}.brand em{font-style:normal;color:#edbd76}.title{font-size:72px;line-height:1.01;margin:25px 0 0;font-weight:900;letter-spacing:-2px;text-shadow:0 7px 14px #0008}.title span{color:#f5c783}.subtitle{margin-top:15px;color:#afc9df;font-size:21px}.hero{margin-top:25px;height:280px;border:1px solid #6a91b0;border-radius:31px;background:linear-gradient(125deg,#193b63,#0b1e38 75%);box-shadow:0 20px 37px #0006,inset 0 2px #ffffff1a;padding:24px 28px}.section-title{font-size:18px;letter-spacing:1.3px;color:#e7c992;font-weight:900}.coin{height:96px;display:flex;align-items:center;border-bottom:1px solid #4b6b87}.coin:last-child{border:0}.coin-icon{width:68px;height:68px;border-radius:50%;display:grid;place-items:center;font-size:37px;font-weight:900;color:#fff0c9;background:radial-gradient(circle at 30% 24%,#fff6c3,#e8a94e 45%,#805125 83%);box-shadow:0 8px 16px #000a,inset 0 3px #ffffff80;text-shadow:0 2px #795126}.coin-icon img{width:68px;height:68px;object-fit:contain}.coin-main{margin-left:21px}.coin-symbol{font-size:30px;font-weight:900}.coin-price{color:#bcd0e4;font-size:18px;margin-top:5px}.coin-change{margin-left:auto;font-size:29px;font-weight:900}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:15px}.metric{background:linear-gradient(140deg,#1b3a5c,#0b1d33);border:1px solid #396389;border-radius:22px;padding:22px 18px;height:143px}.metric label{display:block;color:#bdd0e4;font-size:15px;font-weight:900;letter-spacing:1px;min-height:36px}.metric b{display:block;font-size:28px;margin-top:14px;white-space:nowrap}.rankings{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:17px}.panel{height:233px;background:linear-gradient(148deg,#193a5f,#09182e);border:1px solid #3a5e84;border-radius:25px;padding:21px 22px;box-shadow:0 13px 25px #0005}.panel h2{font-size:22px;letter-spacing:.5px;margin:0 0 10px}.rank{height:49px;display:flex;gap:14px;align-items:center;border-bottom:1px solid #35516a}.rank:last-child{border:0}.rank-num{font-size:16px;color:#9db7d2}.rank b{font-size:21px}.rank strong{margin-left:auto;font-size:20px}.fear{margin-top:16px;height:189px;background:linear-gradient(145deg,#1a3858,#07172c);border:1px solid #3c6084;border-radius:24px;padding:19px 23px;display:flex;gap:22px}.fear-left{width:255px}.fear-title{font-size:18px;letter-spacing:1px;font-weight:900;color:#f5cc93}.fear-score{font-size:57px;font-weight:900;margin-top:10px;line-height:1}.fear-score small{font-size:22px;color:#c3d3e5}.fear-delta{font-size:17px;color:#b1ccdf;margin-top:10px}.fear-delta b{color:'+changeColor(d.fear.delta_7d)+'}.fear-right{flex:1;display:flex;align-items:end;justify-content:space-between;height:143px;gap:8px}.bcell{height:143px;display:flex;flex:1;flex-direction:column;align-items:center;font-weight:900;font-size:14px}.bwrap{height:99px;width:100%;display:flex;align-items:end;justify-content:center;margin-top:4px;background:#15335388;border-radius:7px}.bwrap i{width:75%;border-radius:5px 5px 0 0}.bcell small{font-size:13px;margin-top:7px;color:#aec8df}.footer{margin-top:19px;padding-top:17px;border-top:1px solid #395878;display:flex;justify-content:space-between;gap:14px;color:#b7c9de;font-size:15px}.note{margin-top:10px;text-align:center;color:#9db6d0;font-size:14px}.demo{position:absolute;z-index:10;top:0;left:0;right:0;text-align:center;background:#bb304e;color:#fff;padding:15px;font-size:20px;font-weight:900;letter-spacing:2px}' +
'</style></head><body><main class="page"><header class="top"><div class="edition">BILAN HEBDOMADAIRE #07</div><div class="brand">MR <em>XPRONOS</em> ◆</div></header>'+
'<h1 class="title">LA SEMAINE<br/><span>CRYPTO EN CHIFFRES</span></h1><div class="subtitle">Variations des cours sur 7 jours glissants • '+esc(date)+' UTC</div>'+
'<section class="hero"><div class="section-title">BITCOIN &amp; ETHEREUM • 7 JOURS</div>'+coin(d.btc,'₿')+coin(d.eth,'Ξ')+'</section>'+
'<section class="metrics"><div class="metric"><label>CAPITALISATION ACTUELLE</label><b>'+esc(dollar(d.market_cap_usd))+'</b></div><div class="metric"><label>DOMINANCE BTC ACTUELLE</label><b>'+n(d.btc_dominance_pct,1)+' %</b></div><div class="metric"><label>VOLUME SUR 24 H</label><b>'+esc(dollar(d.volume_24h_usd))+'</b></div></section>'+
'<section class="rankings"><div class="panel"><h2>↗ TOP 3 HAUSSES • 7 J</h2>'+ranking(d.winners)+'</div><div class="panel"><h2>↘ TOP 3 BAISSES • 7 J</h2>'+ranking(d.losers)+'</div></section>'+
'<section class="fear"><div class="fear-left"><div class="fear-title">SENTIMENT DU MARCHÉ</div><div class="fear-score">'+d.fear.score+'<small>/100</small></div><div class="fear-delta">Sur 7 jours : <b>'+(d.fear.delta_7d>0?'+':'')+d.fear.delta_7d+' pts</b></div></div><div class="fear-right">'+bars+'</div></section>'+
'<div class="footer"><span>Marché : '+esc(d.provider)+' • Sentiment : Alternative.me</span><span>Instantané : '+esc(date)+' UTC</span></div>'+
'<div class="note">Les tops concernent les 100 premières cryptos, hors stablecoins et BTC/ETH, avec volume ≥ 1 M$ / 24 h. Pas de conseil en investissement.</div>'+
(demo?'<div class="demo">SIMULATION — DONNÉES FICTIVES — NON PUBLIABLE</div>':'')+'</main></body></html>';
const browser=await chromium.launch({headless:true});
try{const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
await page.setContent(html,{waitUntil:'load'});
const b=await page.evaluate(()=>({scroll:document.documentElement.scrollHeight,note:document.querySelector('.note').getBoundingClientRect().bottom,footer:document.querySelector('.footer').getBoundingClientRect().bottom}));
if(b.scroll>1350||b.note>1350||b.footer>1350)throw Error('Poster overflow '+JSON.stringify(b));
await mkdir('crypto/generated/test',{recursive:true});await page.screenshot({path:output});
console.log('WEEKLY_07_RENDERED',demo?'DEMO':'REAL',d.provider,output);}finally{await browser.close()}
