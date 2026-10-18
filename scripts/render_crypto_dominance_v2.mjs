/** Mr XPRONOS — Publication 06, dominance du Bitcoin, 1080×1350. */
import {chromium} from 'playwright';
import {readFile, mkdir} from 'node:fs/promises';

const demo = process.argv.includes('--demo');
const input = demo ? 'crypto/generated/test/dominance_v2_demo.json' : 'crypto/generated/test/dominance_v2_data.json';
const output = demo ? 'crypto/generated/test/dominance_v2_demo.png' : 'crypto/generated/test/dominance_v2.png';
const d = JSON.parse(await readFile(input, 'utf8'));
if(d.status !== (demo ? 'demo' : 'real_data') || d.is_demo !== demo) throw Error('Mode de données incorrect');
if(demo ? d.provider !== 'SIMULATION' : !['CoinPaprika','CoinLore'].includes(d.provider)) throw Error('Source invalide');
const fields = ['market_cap_usd','volume_24h_usd','btc_dominance_pct','other_dominance_pct','market_cap_change_24h_pct','cryptocurrencies_number'];
if(fields.some(k => typeof d[k] !== 'number' || !Number.isFinite(d[k]))) throw Error('Donnée non numérique');
if(d.market_cap_usd < 1e6 || d.volume_24h_usd <= 0 || d.btc_dominance_pct <= 0 ||
   d.btc_dominance_pct >= 100 || Math.abs(d.btc_dominance_pct+d.other_dominance_pct-100)>0.001) throw Error('Valeurs financières incohérentes');
const num=(v, digits=1)=>v.toLocaleString('fr-FR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
const big=(v)=>v>=1e12?num(v/1e12,2)+' billions $':num(v/1e9,1)+' Md $';
const stamp=new Date(d.source_updated_at || d.collected_at);
if(Number.isNaN(stamp.getTime())) throw Error('Date invalide');
const when=stamp.toLocaleString('fr-FR',{timeZone:'UTC',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});
const stampLabel=d.source_updated_at?'MESURÉ LE':'CONSULTÉ LE';
const esc=s=>String(s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const btc=d.btc_dominance_pct;
const change=d.market_cap_change_24h_pct;
const sign=change>0?'+':change<0?'−':'';
const formattedChange=sign+num(Math.abs(change),2)+' %';
const deltaColor=change>=0?'#6FE5AC':'#FF8BA4';
const circum=2*Math.PI*164;
const dash=circum*btc/100;
const svg='<svg class="donut" viewBox="0 0 440 440" role="img" aria-label="Dominance du Bitcoin : '+num(btc,2)+' pour cent">'+
'<defs><linearGradient id="btcGold" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#FFF0B6"/><stop offset=".5" stop-color="#F1BE70"/><stop offset="1" stop-color="#D88C4B"/></linearGradient><filter id="ringDrop"><feGaussianBlur stdDeviation="4"/></filter></defs>'+
'<circle cx="220" cy="220" r="164" fill="none" stroke="#234468" stroke-width="49"/>'+
'<circle cx="220" cy="220" r="164" fill="none" stroke="#E2A35E" stroke-opacity=".38" stroke-width="65" stroke-dasharray="'+dash+' '+circum+'" transform="rotate(-90 220 220)" filter="url(#ringDrop)"/>'+
'<circle cx="220" cy="220" r="164" fill="none" stroke="url(#btcGold)" stroke-width="48" stroke-dasharray="'+dash+' '+circum+'" transform="rotate(-90 220 220)"/>'+
'<circle cx="220" cy="220" r="130" fill="#0A1D36" stroke="#B0CAE020" stroke-width="2"/>'+
'<text x="220" y="183" text-anchor="middle" font-size="28" font-weight="900" fill="#F4C779">₿ BITCOIN</text>'+
'<text x="220" y="255" text-anchor="middle" font-size="73" font-weight="900" fill="#FFF9EB">'+num(btc,1)+'%</text>'+
'<text x="220" y="297" text-anchor="middle" font-size="20" font-weight="700" letter-spacing="3" fill="#ABCCE4">DOMINANCE</text></svg>';

const html = `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{width:1080px;height:1350px;margin:0;overflow:hidden}
body{color:#f7faff;font-family:Arial,Helvetica,sans-serif;background:radial-gradient(ellipse at 110% 0%,#275c87 0%,transparent 42%),radial-gradient(ellipse at -15% 91%,#1a4574 0%,transparent 48%),linear-gradient(155deg,#081426,#0b2140 57%,#050e20)}
.page{width:100%;height:100%;padding:47px 55px 38px;position:relative}
.page:before{content:'';pointer-events:none;position:absolute;inset:0;opacity:.12;background-image:linear-gradient(#6a92ae25 1px,transparent 1px),linear-gradient(90deg,#6a92ae25 1px,transparent 1px);background-size:44px 44px}
.top{position:relative;display:flex;align-items:center;justify-content:space-between;height:51px;border-bottom:1px solid #42617d}
.section{font-weight:900;color:#eac185;font-size:18px;letter-spacing:4px}
.logo{font-size:28px;letter-spacing:1px;font-weight:900;color:#fff;filter:drop-shadow(0 4px 7px #0008)}.logo span{color:#f0c47e}
.title{position:relative;margin:29px 0 0;font-size:69px;line-height:1.05;font-weight:900;letter-spacing:-2.5px;text-shadow:0 7px 14px #000a}
.title em{font-style:normal;color:#f2c37e;text-shadow:0 4px #5b4325,0 9px 14px #000b}
.subtitle{position:relative;font-size:22px;color:#b4d0e9;margin-top:17px}
.hero{position:relative;margin-top:30px;height:505px;border-radius:37px;overflow:hidden;border:1px solid #6287ab;background:linear-gradient(136deg,#23486ce8,#0b1d37ed 58%,#0f3054f5);box-shadow:0 27px 44px #0008,inset 0 2px #ffffff30}
.hero:before{content:'';position:absolute;left:30px;top:105px;width:460px;height:340px;border-radius:50%;background:#d3a56716;filter:blur(50px)}
.hero-label{position:absolute;left:33px;top:28px;letter-spacing:2px;color:#bfd4e6;font-size:19px;font-weight:900}
.donut{position:absolute;left:19px;top:59px;width:445px;height:425px;filter:drop-shadow(0 13px 11px #0008)}
.panel{position:absolute;left:484px;top:112px;right:30px}
.panel-title{font-size:16px;font-weight:800;letter-spacing:1.5px;color:#b5cde4}
.panel-lead{margin-top:12px;font-size:36px;line-height:1.14;font-weight:900}
.panel-lead span{color:#f3c780}
.rule{height:1px;background:#486a8b;margin:24px 0}
.legend{display:flex;align-items:center;gap:15px;color:#e5eefb;font-size:22px;margin-top:18px;font-weight:700}
.dot{width:14px;height:14px;flex:none;border-radius:50%;box-shadow:0 0 15px #F4CB8855}
.percent{margin-left:auto;font-size:23px;font-weight:900}
.source-line{position:absolute;bottom:20px;right:31px;font-size:15px;color:#b2c9e0}
.metrics{position:relative;display:grid;grid-template-columns:1fr 1fr;gap:17px;margin-top:22px}
.metric{height:174px;padding:24px 27px;border-radius:24px;background:linear-gradient(145deg,#193d62dc,#0b1d38);border:1px solid #3c678d;box-shadow:0 12px 22px #0005,inset 0 1px #ffffff1b}
.metric-label{font-size:17px;letter-spacing:1.2px;color:#b7cce3;font-weight:900}
.metric-value{margin-top:19px;font-size:41px;white-space:nowrap;font-weight:900;color:#f7faff;letter-spacing:-1px}
.metric-note{color:#adc4db;font-size:15px;margin-top:9px}
.footer{position:relative;margin-top:24px;border-top:1px solid #4c7397;padding-top:17px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;color:#b8cde3;font-size:16px}
.footer b{color:#f5d398}.caution{position:relative;text-align:center;font-size:14px;color:#9cb7d3;margin-top:18px}
.demo{position:absolute;top:0;left:0;right:0;z-index:10;background:#ba3854;color:white;text-align:center;padding:15px;font-weight:900;font-size:19px;letter-spacing:2px}
</style></head><body><main class="page">
<div class="top"><span class="section">ANALYSE DU MARCHÉ CRYPTO</span><div class="logo">MR <span>XPRONOS</span> ◆</div></div>
<h1 class="title">LE POIDS DU <em>BITCOIN</em><br/>SUR LE MARCHÉ CRYPTO</h1>
<div class="subtitle">Dominance BTC &amp; capitalisation globale • Rapport #06</div>
<section class="hero"><div class="hero-label">RÉPARTITION DE LA CAPITALISATION MONDIALE</div>${svg}
<div class="panel"><div class="panel-title">LE BITCOIN REPRÉSENTE</div><div class="panel-lead"><span>${num(btc,1)} %</span> DE LA<br/>VALEUR DU<br/>MARCHÉ</div><div class="rule"></div>
<div class="legend"><i class="dot" style="background:#f2c27d"></i> Bitcoin <b class="percent">${num(btc,1)} %</b></div>
<div class="legend"><i class="dot" style="background:#406a92"></i> Autres cryptos <b class="percent">${num(d.other_dominance_pct,1)} %</b></div></div>
<div class="source-line">${stampLabel} ${esc(when)} UTC</div></section>
<section class="metrics">
<div class="metric"><div class="metric-label">CAPITALISATION GLOBALE</div><div class="metric-value">${esc(big(d.market_cap_usd))}</div><div class="metric-note">Valeur totale estimée du marché</div></div>
<div class="metric"><div class="metric-label">VARIATION SUR 24 H</div><div class="metric-value" style="color:${deltaColor}">${formattedChange}</div><div class="metric-note">Variation de la capitalisation globale</div></div>
<div class="metric"><div class="metric-label">VOLUME TOTAL SUR 24 H</div><div class="metric-value">${esc(big(d.volume_24h_usd))}</div><div class="metric-note">Échanges estimés en dollars US</div></div>
<div class="metric"><div class="metric-label">CRYPTOMONNAIES SUIVIES</div><div class="metric-value">${num(d.cryptocurrencies_number,0)}</div><div class="metric-note">Couverture de ${esc(d.provider)}</div></div></section>
<div class="footer"><span>Source : <b>${esc(d.provider)}</b></span><span>DOMINANCE BTC • RAPPORT QUOTIDIEN</span></div>
<div class="caution">Données indicatives selon la couverture du fournisseur • Pas un conseil en investissement.</div>
${demo?'<div class="demo">SIMULATION — DONNÉES FICTIVES • NON PUBLIABLE</div>':''}
</main></body></html>`;

const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
 await page.setContent(html,{waitUntil:'load'});
 const bounds=await page.evaluate(()=>({scroll:document.documentElement.scrollHeight,
    caution:document.querySelector('.caution').getBoundingClientRect().bottom,
    metrics:document.querySelector('.metrics').getBoundingClientRect().bottom}));
 if(bounds.scroll>1350 || bounds.caution>1350 || bounds.metrics>1350) throw Error('Débordement affiche : '+JSON.stringify(bounds));
 await mkdir('crypto/generated/test',{recursive:true});
 await page.screenshot({path:output});
 console.log('DOMINANCE_V2_RENDERED',demo?'DEMO':'REAL',d.provider,output);
} finally { await browser.close(); }
