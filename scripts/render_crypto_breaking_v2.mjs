/** Actu Crypto #08 — affiche éditoriale BTC/ETH 1080x1350, 100% automatique. */
import {chromium} from 'playwright';
import {readFile, mkdir} from 'node:fs/promises';

const demo=process.argv.includes('--demo');
const input=demo?'crypto/generated/test/breaking_v2_demo.json':'crypto/generated/test/breaking_v2_data.json';
const output=demo?'crypto/generated/test/breaking_v2_demo.png':'crypto/generated/test/breaking_v2.png';
const d=JSON.parse(await readFile(input,'utf8'));
if(d.publication!==8||d.status!==(demo?'demo':'real_data')||d.is_demo!==demo)
    throw Error('Demo/real data guard rejected payload');
const a=d.main,b=d.confirmation;
if(!a||!b||a.source===b.source||!['bitcoin','ethereum'].includes(d.topic))
    throw Error('Two independent confirmations required');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=s=>new Date(s).toLocaleString('fr-FR',{timeZone:'UTC',day:'2-digit',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'});
const main=esc(a.title), source=esc(a.source), confirm=esc(b.source);
const coin=d.topic==='bitcoin'?'BITCOIN':'ETHEREUM';
const glyph=d.topic==='bitcoin'?'₿':'Ξ';
const headlineSize=a.title.length>144?49:a.title.length>109?56:a.title.length>72?64:75;
const phase=demo?'DÉMONSTRATION FICTIVE':'INFORMATION RECoupÉE'.toUpperCase();
const html='<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>'+
'*{box-sizing:border-box}html,body{width:1080px;height:1350px;margin:0;overflow:hidden}body{background:#051123;color:#fff;font-family:Arial,Helvetica,sans-serif}'+
'.poster{height:1350px;position:relative;overflow:hidden;background:radial-gradient(ellipse 750px 630px at 93% 7%,#23456b99,transparent 76%),radial-gradient(ellipse 760px 790px at -24% 87%,#18446e66,transparent 73%),linear-gradient(140deg,#071424,#0a1b35 55%,#050d1d)}'+
'.ambient{position:absolute;top:220px;left:-220px;width:600px;height:600px;border:1px solid #d7a35b20;border-radius:50%;box-shadow:0 0 0 68px #d7a35b06,0 0 0 136px #d7a35b06,0 0 0 204px #d7a35b05}.grains{position:absolute;inset:0;opacity:.16;background-image:radial-gradient(#d7ecff 1px,transparent 1px);background-size:33px 33px;mask-image:linear-gradient(135deg,transparent,#0008,transparent)}'+
'.main{position:relative;z-index:2;padding:56px 65px 37px}.top{display:flex;align-items:center;justify-content:space-between;padding-bottom:27px;border-bottom:1px solid #809bb051}.brand{font-weight:900;font-size:31px;letter-spacing:1px}.brand span{color:#eac18b}.serial{color:#b6c8dd;font-size:17px;letter-spacing:2px;font-weight:800}.eyebrow{margin-top:34px;display:flex;align-items:center;gap:15px;font-size:20px;font-weight:900;letter-spacing:4px;color:#ffdc9c}.dot{width:13px;height:13px;border-radius:50%;background:#ffbd71;box-shadow:0 0 21px #ffd07d}.coinlabel{margin-top:25px;color:#b3ccdf;font-size:27px;font-weight:800;letter-spacing:6px}.bigtitle{font-size:88px;line-height:1.01;letter-spacing:-3px;font-weight:900;margin:10px 0 0;text-shadow:0 11px 24px #0009}.bigtitle span{color:#ffcf8c}.underline{height:5px;width:230px;border-radius:5px;background:linear-gradient(90deg,#f1c88b,transparent);margin-top:25px}.description{margin-top:24px;color:#bdd0e4;font-size:21px;letter-spacing:.3px;line-height:1.5}'+
'.feature{margin-top:35px;height:392px;border:1px solid #6889a56c;border-radius:32px;background:linear-gradient(136deg,#1b395bde,#08182edb 67%);box-shadow:0 25px 45px #0008,inset 0 2px #ffffff19;position:relative;overflow:hidden;padding:36px 42px}.feature-head{display:flex;justify-content:space-between;align-items:center;position:relative;z-index:3}.feature-label{font-size:17px;letter-spacing:2px;font-weight:900;color:#f4c995}.confirmed{font-size:15px;letter-spacing:1px;color:#9df5ca;font-weight:900;border:1px solid #6a9a8c;padding:12px 17px;border-radius:99px}.coin3d{position:absolute;right:-72px;top:72px;width:313px;height:313px;border-radius:50%;transform:rotate(-18deg);background:radial-gradient(circle at 31% 25%,#fff3ba 0%,#eec781 20%,#a87230 56%,#5d3f24 84%);border:17px solid #f7d08b;box-shadow:inset 0 0 0 9px #b9813b,inset 0 0 0 13px #fce0ab,0 20px 46px #000c,0 0 80px #d49d4660;display:grid;place-items:center;color:#74431e;font-size:188px;font-weight:900;text-shadow:2px 3px 1px #ffe7b8;opacity:.83}.story{position:relative;z-index:4;width:720px;font-size:'+headlineSize+'px;line-height:1.11;letter-spacing:-1.5px;font-weight:900;margin-top:35px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:4;overflow:hidden;text-shadow:0 7px 20px #000b}.original{position:relative;z-index:4;font-size:16px;color:#e1bb88;letter-spacing:2px;font-weight:900;margin-top:16px}'+
'.confirm-panel{margin-top:29px;display:grid;grid-template-columns:1fr 1fr;gap:19px}.sourcecard{height:152px;padding:25px 25px;background:#0d2743;border:1px solid #56738b;border-radius:24px;box-shadow:inset 0 1px #ffffff12}.source-label{color:#9bbbd0;letter-spacing:2px;font-size:15px;font-weight:900}.source-name{font-size:32px;font-weight:900;margin-top:15px}.time{font-size:16px;color:#b9cde0;margin-top:9px}.bottom{margin-top:30px;border-top:1px solid #7594a05a;padding-top:24px}.bottom-top{color:#efc893;font-size:22px;font-weight:900;letter-spacing:1px}.bottom p{font-size:17px;color:#b5c9dc;line-height:1.48;margin:14px 0}.footer{display:flex;justify-content:space-between;color:#8faac3;font-size:16px;margin-top:15px}.watermark{position:absolute;z-index:9;inset:0;background:#40051c99;display:flex;align-items:center;justify-content:center;transform:rotate(-17deg);font-size:49px;font-weight:900;text-align:center;letter-spacing:4px;text-shadow:0 4px 8px #000;pointer-events:none}'+
'</style></head><body><div class="poster"><div class="ambient"></div><div class="grains"></div><main class="main">'+
'<header class="top"><div class="brand">MR <span>XPRONOS</span> ◈</div><div class="serial">ACTU CRYPTO · #08</div></header>'+
'<div class="eyebrow"><i class="dot"></i> BREAKING NEWS</div><div class="coinlabel">'+coin+'</div>'+
'<h1 class="bigtitle">L’ACTU QUI<br><span>COMPTE.</span></h1><div class="underline"></div>'+
'<div class="description">Une information majeure sur '+coin.toLowerCase()+'<br>confirmée par deux médias indépendants.</div>'+
'<section class="feature"><div class="feature-head"><div class="feature-label">À LA UNE · TITRE ORIGINAL</div><div class="confirmed">✓ RECoupÉ</div></div><div class="coin3d">'+glyph+'</div><div class="story">'+main+'</div><div class="original">TITRE SOURCE (ANGLAIS)</div></section>'+
'<section class="confirm-panel"><div class="sourcecard"><div class="source-label">SOURCE PRINCIPALE</div><div class="source-name">'+source+'</div><div class="time">'+esc(dt(a.published_at))+' UTC</div></div>'+
'<div class="sourcecard"><div class="source-label">DEUXIÈME CONFIRMATION</div><div class="source-name">'+confirm+'</div><div class="time">'+esc(dt(b.published_at))+' UTC</div></div></section>'+
'<div class="bottom"><div class="bottom-top">INFORMATION VÉRIFIÉE · '+esc(dt(d.collected_at))+' UTC</div>'+
'<p>Sources citées dans la légende Telegram. Vérifiez les articles complets pour connaître le contexte et les éventuelles mises à jour.</p></div>'+
'<footer class="footer"><span>MR XPRONOS · ACTU CRYPTO</span><span>Information, pas conseil financier</span></footer>'+
'</main>'+(demo?'<div class="watermark">SIMULATION<br>INFORMATION FICTIVE<br>NON PUBLIABLE</div>':'')+'</div></body></html>';
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
 await page.setContent(html,{waitUntil:'load'});
 const diag=await page.evaluate(()=>{
   const find=s=>{const r=document.querySelector(s).getBoundingClientRect();return {bottom:r.bottom,right:r.right,height:r.height}};
   const story=document.querySelector('.story');
   return {story:find('.story'),feature:find('.feature'),footer:find('.footer'),textClipped:story.scrollHeight>story.clientHeight+2,
     bottom:document.querySelector('.bottom').getBoundingClientRect().bottom};
 });
 if(diag.textClipped||diag.footer.bottom>1342||diag.feature.bottom>1100)
     throw Error('Poster content overflow: '+JSON.stringify(diag));
 await mkdir('crypto/generated/test',{recursive:true});
 await page.screenshot({path:output});
 console.log('BREAKING_08_RENDERED',demo?'DEMO':'REAL',d.topic,output);
}finally{await browser.close()}
