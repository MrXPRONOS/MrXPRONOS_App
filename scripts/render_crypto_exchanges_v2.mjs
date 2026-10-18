/** Mr XPRONOS #09 — premium exchange-news poster; real/demo separation. */
import {chromium} from 'playwright';
import {readFile,mkdir} from 'node:fs/promises';

const demo=process.argv.includes('--demo');
const file=demo?'crypto/generated/test/exchanges_v2_demo.json':'crypto/generated/test/exchanges_v2_data.json';
const output=demo?'crypto/generated/test/exchanges_v2_demo.png':'crypto/generated/test/exchanges_v2.png';
const d=JSON.parse(await readFile(file,'utf8'));
const providers=['CoinDesk','Cointelegraph','The Block','Decrypt','Blockworks','BeInCrypto','Bitcoin Magazine','NewsBTC','Coinbase Status','Kraken Status'];
const exchanges=['BINANCE','COINBASE','OKX','KRAKEN','BYBIT','BITGET','KUCOIN','GEMINI'];
const cats=['SÉCURITÉ','ACCÈS & SERVICES','FRAIS & TRADING','RÉGLEMENTATION','INNOVATION'];
if(d.publication!==9||d.is_demo!==demo||d.status!==(demo?'demo':'real_data'))
  throw Error('Refusing wrong publication or real/demo status');
if(!d.main||!providers.includes(d.main.source)||!exchanges.includes(d.exchange)||
   !cats.includes(d.category)||d.exchange!==d.main.exchange||d.main.category!==d.category)
  throw Error('Bad exchange news metadata');
if(d.confirmation&&!providers.includes(d.confirmation.source))throw Error('Unrecognized confirmation source');
if(d.main.severe&&!d.confirmation)throw Error('Sensitive headline needs corroboration');
if(d.verification!==(d.main.official?'official_notice':(d.confirmation?'cross_reported':'attributed_report')))
  throw Error('Bad provenance label');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stamp=v=>new Date(v).toLocaleString('fr-FR',{timeZone:'UTC',day:'2-digit',month:'long',hour:'2-digit',minute:'2-digit',year:'numeric'});
if(!Number.isFinite(Date.parse(d.collected_at))||!Number.isFinite(Date.parse(d.main.published_at)))throw Error('Unusable dates');
const title=esc(d.main.title);
const category=esc(d.category);
const exchange=esc(d.exchange);
const source=esc(d.main.source);
const second=esc(d.confirmation?.source||'—');
const when=esc(stamp(d.main.published_at));
const published=esc(stamp(d.collected_at));
const headlineSize=d.main.title.length>153?42:d.main.title.length>117?47:d.main.title.length>86?53:60;
const status=d.main.official?'SOURCE OFFICIELLE':d.confirmation?'DEUX MÉDIAS':'SOURCE ATTRIBUÉE';
const evidence=d.main.official?'INCIDENT SIGNALÉ PAR LA PLATEFORME':d.confirmation?'DEUX SOURCES RECROISÉES':'ARTICLE ATTRIBUÉ À SON MÉDIA';
const svg='<svg viewBox="0 0 450 450" class="network" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'+
'<defs><radialGradient id="orb" cx="30%" cy="25%"><stop offset="0%" stop-color="#ffe3b3"/><stop offset="39%" stop-color="#daa96e"/><stop offset="75%" stop-color="#8b653c"/><stop offset="100%" stop-color="#2b3a4b"/></radialGradient><linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f3d7a3"/><stop offset="1" stop-color="#b27c4d"/></linearGradient></defs>'+
'<circle cx="225" cy="225" r="196" stroke="#d5a868" stroke-opacity=".17" fill="none" stroke-width="2"/>'+
'<circle cx="225" cy="225" r="161" stroke="#d5a868" stroke-opacity=".24" fill="none" stroke-width="3"/>'+
'<circle cx="225" cy="225" r="139" fill="url(#orb)" stroke="#f5d9a6" stroke-width="6"/>'+
'<circle cx="225" cy="225" r="114" fill="#0e2b47" stroke="#f7ddae" stroke-width="5"/>'+
'<g fill="none" stroke="url(#edge)" stroke-width="19" stroke-linecap="round" stroke-linejoin="round">'+
'<path d="M149 201h148l-42-39M297 250H148l43 39"/></g>'+
'<circle cx="225" cy="225" r="102" fill="none" stroke="#d6b680" stroke-opacity=".3" stroke-width="2"/>'+
'<circle cx="64" cy="153" r="8" fill="#f8dca1"/><circle cx="387" cy="317" r="8" fill="#f8dca1"/>'+
'</svg>';
const html=`<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{width:1080px;height:1350px;margin:0;overflow:hidden}
body{font-family:Arial,Helvetica,sans-serif;color:#f8fbff;background:#061226}
.poster{position:relative;height:1350px;width:1080px;overflow:hidden;background:
 radial-gradient(ellipse 800px 580px at 103% -11%,#315681b5,transparent 69%),
 radial-gradient(ellipse 800px 610px at -28% 104%,#20508483,transparent 72%),
 linear-gradient(145deg,#061225,#091e39 57%,#040d1e)}
.poster:before{content:"";position:absolute;inset:0;background-image:linear-gradient(#6b8cac13 1px,transparent 1px),linear-gradient(90deg,#6b8cac13 1px,transparent 1px);background-size:48px 48px;opacity:.45}
.page{position:relative;padding:49px 56px 35px;z-index:1}
.top{display:flex;align-items:center;justify-content:space-between;height:51px;border-bottom:1px solid #4c6b86;padding-bottom:19px}
.eyebrow{font-size:18px;font-weight:900;letter-spacing:3px;color:#edc58a}
.brand{font-size:29px;font-weight:900;letter-spacing:.4px;color:#fff;text-shadow:0 5px 11px #0008}.brand span{color:#f0c482}
.heading{margin:33px 0 0;font-size:77px;font-weight:900;line-height:1.01;letter-spacing:-2.7px;text-shadow:0 7px 16px #000a}
.heading em{font-style:normal;color:#f5c783}
.goldline{margin-top:20px;height:5px;width:139px;border-radius:3px;background:linear-gradient(90deg,#ecc284,#fff4bf);box-shadow:0 0 18px #f3c47375}
.sub{margin-top:15px;font-size:20px;color:#b9cde1;line-height:1.35}
.hero{margin-top:25px;height:503px;border-radius:34px;position:relative;overflow:hidden;
 background:linear-gradient(127deg,#1e4168eb,#0a1b35f6 73%);
 border:1px solid #7394b0;box-shadow:0 28px 44px #0008,inset 0 2px #ffffff22}
.hero:before{content:"";position:absolute;right:-180px;top:-90px;width:620px;height:540px;background:radial-gradient(circle,#eabb7340,transparent 68%)}
.hero-header{padding:29px 34px 0;display:flex;justify-content:space-between;align-items:center;position:relative;z-index:4}
.tag{font-size:16px;letter-spacing:1.4px;color:#efcd96;font-weight:900}
.pill{color:#d6f8e9;border:1px solid #6f9d93;background:#1b54494d;padding:11px 16px;border-radius:24px;font-size:15px;font-weight:900}
.network{width:390px;height:390px;position:absolute;right:-75px;top:95px;transform:rotate(-13deg);
 filter:drop-shadow(0 17px 17px #000a) drop-shadow(0 0 34px #dbad6b45);opacity:.97}
.exchange{font-size:67px;font-weight:900;letter-spacing:-1.2px;margin:23px 34px 0;position:relative;z-index:3;text-shadow:0 7px 15px #000c}
.exchange[data-long="true"]{font-size:56px}
.rule{margin:8px 34px 0;width:210px;height:4px;background:linear-gradient(90deg,#e5c18a,transparent);position:relative;z-index:4}
.headline{position:relative;z-index:5;width:680px;margin:20px 0 0 34px;font-size:${headlineSize}px;
 letter-spacing:-1.4px;line-height:1.115;font-weight:900;text-shadow:0 5px 16px #000d;overflow-wrap:break-word}
.origin{position:absolute;left:36px;bottom:26px;font-size:15px;font-weight:900;letter-spacing:1.3px;color:#e9c28b}
.evidence{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}
.card{height:161px;padding:23px 24px;border:1px solid #456f93;border-radius:25px;
 background:linear-gradient(143deg,#183c60,#0a1b35 85%);box-shadow:0 13px 24px #0005}
.cardlabel{font-size:15px;color:#c4d4e6;font-weight:900;letter-spacing:1.2px}
.cardname{font-size:31px;font-weight:900;color:#fff;margin-top:13px}
.cardtime{font-size:16px;color:#aebfd3;margin-top:11px}
.info{margin-top:19px;border:1px solid #476e8e;background:#102948d9;border-radius:23px;padding:20px 23px;
 display:flex;align-items:center;justify-content:space-between;gap:18px;min-height:92px}
.infotitle{font-size:20px;font-weight:900;color:#f3ce91}
.infodesc{font-size:16px;color:#bcd0e3;margin-top:9px}
.marker{padding:12px 18px;border-radius:16px;background:#314d69;color:#efcf9b;
 text-align:center;font-size:16px;white-space:nowrap;font-weight:900}
.footer{display:flex;justify-content:space-between;align-items:start;margin-top:22px;
 padding-top:17px;border-top:1px solid #476f8d;font-size:15px;color:#b0c5df;gap:15px}
.footnote{font-size:14px;color:#8aa9c8;margin-top:10px;text-align:center}
.demo{position:absolute;inset:auto 0 0 0;z-index:10;height:48px;background:#ab2c47;color:#fff;
 display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;letter-spacing:1.5px}
</style></head><body><div class="poster"><main class="page">
<header class="top"><span class="eyebrow">PLATEFORMES CRYPTO • #09</span><span class="brand">MR <span>XPRONOS</span> ◆</span></header>
<h1 class="heading">L'ACTU DES<br/><em>EXCHANGES.</em></h1>
<div class="goldline"></div>
<div class="sub">Binance · Coinbase · OKX · Kraken · autres plateformes</div>
<section class="hero">
<div class="hero-header"><span class="tag">${category} · INFO PLATEFORME</span><span class="pill">${status}</span></div>
${svg}
<div class="exchange" data-long="${d.exchange.length>7}">${exchange}</div>
<div class="rule"></div><div class="headline">${title}</div>
<div class="origin">TITRE ORIGINAL DE LA SOURCE · ANGLAIS</div>
</section>
<div class="evidence">
<div class="card"><div class="cardlabel">SOURCE À L'ORIGINE</div><div class="cardname">${source}</div><div class="cardtime">${when} UTC</div></div>
<div class="card"><div class="cardlabel">${d.confirmation?'DEUXIÈME MÉDIA':d.main.official?'STATUT DE L’INCIDENT':'STATUT DE LA SOURCE'}</div><div class="cardname">${d.confirmation?second:d.main.official?'OFFICIEL':'1 SOURCE'}</div>
<div class="cardtime">${d.confirmation?'Recoupement de titres':d.main.official?'Vérifier le statut actuel':'À consulter dans son contexte'}</div></div>
</div>
<div class="info"><div><div class="infotitle">${evidence}</div><div class="infodesc">Lien de la source primaire ou du média dans la légende Telegram.</div></div>
<div class="marker">EXCHANGE<br/>WATCH</div></div>
<footer class="footer"><span>Sources : ${source}${d.confirmation?' + '+second:''}</span><span>Collecte : ${published} UTC</span></footer>
<div class="footnote">Information sourcée, pas une recommandation de trading. Vérifiez la disponibilité selon votre pays.</div>
</main>${demo?'<div class="demo">SIMULATION • ACTUALITÉ FICTIVE • NON PUBLIABLE</div>':''}</div></body></html>`;
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
 await page.setContent(html,{waitUntil:'load'});
 await page.evaluate(async()=>{
   await document.fonts.ready;
   const story=document.querySelector('.headline'),hero=document.querySelector('.hero');
   let size=parseFloat(getComputedStyle(story).fontSize);
   while(story.getBoundingClientRect().bottom > hero.getBoundingClientRect().bottom-64 && size>30){
     size-=1;story.style.fontSize=size+'px';
   }
 });
 const b=await page.evaluate(()=>{
  let bounds=x=>{const r=document.querySelector(x).getBoundingClientRect();return {top:r.top,bottom:r.bottom}};
  return {scroll:document.documentElement.scrollHeight,hero:bounds('.hero'),title:bounds('.headline'),foot:bounds('.footnote'),info:bounds('.info')}
 });
 if(b.scroll>1350||b.foot.bottom>1320||b.title.bottom>b.hero.bottom-55||b.info.bottom>1245)
  throw Error('Poster overflow '+JSON.stringify(b));
 await mkdir('crypto/generated/test',{recursive:true});
 await page.screenshot({path:output});
 console.log('EXCHANGE_09_RENDERED',demo?'DEMO':'REAL',d.exchange,d.verification,output);
}finally{await browser.close()}
