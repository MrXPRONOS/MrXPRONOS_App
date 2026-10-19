/** #11 — African crypto regulation news, TEST ONLY, not a legal status determination. */
import {chromium} from 'playwright';
import {readFile,mkdir} from 'node:fs/promises';

const qa=process.argv.includes('--demo');
const dataPath=qa?'crypto/generated/test/regulation_11_demo.json':'crypto/generated/test/regulation_11_data.json';
const output=qa?'crypto/generated/test/regulation_11_demo.png':'crypto/generated/test/regulation_11.png';
const d=JSON.parse(await readFile(dataPath,'utf8'));
const sources=['CoinDesk','Cointelegraph','The Block','Decrypt','Blockworks','BeInCrypto','Bitcoin Magazine','NewsBTC','SIMULATION QA'];
if(d.publication!==11||d.is_demo!==qa||d.status!==(qa?'demo':'attributed_press')||
 d.legal_status_confirmed!==false||(!qa&&(d.source_count!==1||d.main?.high_impact!==false)))
 throw Error('Unsafe data or unverified Africa legal status');
const a=d.main;
if(!a||!sources.includes(a.source)||!a.title||!a.region||!a.topic||
  !Number.isFinite(Date.parse(a.published_at)))throw Error('Unverified regulatory source data');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=s=>new Date(s).toLocaleString('fr-FR',{timeZone:'UTC',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
const ts=esc(dt(d.collected_at)),date=esc(dt(a.published_at));
const isOfficial=false;
const headline=d.synopsis_fr;
if(typeof headline!=='string'||headline.length<15||headline.length>185)
 throw Error('Unverifiable Africa news synopsis');
const globeSvg=[
'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 440">',
'<defs><linearGradient id="land" x1="0" y1="0" x2="1" y2="1">',
'<stop stop-color="#ffe0a4"/><stop offset=".58" stop-color="#dfaa67"/>',
'<stop offset="1" stop-color="#88623c"/></linearGradient></defs>',
'<circle cx="199" cy="200" r="185" fill="none" stroke="#edc689" stroke-opacity=".22" stroke-width="2"/>',
'<path d="M154 22 L202 18 247 36 290 52 318 80 343 115 353 153 340 185 356 215 333 247 301 256 289 295 271 331 246 363 224 408 198 425 185 394 162 366 146 330 128 297 106 267 76 251 55 225 51 192 38 158 60 126 83 105 103 65 132 38Z"',
' fill="url(#land)" stroke="#fff0c4" stroke-width="5"/>',
'<path d="M325 335 Q344 367 324 401 L300 427 Q287 434 295 406 L308 361Z" fill="url(#land)" stroke="#fff0c4" stroke-width="3"/>',
'<circle cx="175" cy="186" r="38" fill="none" stroke="#f8ce8e" stroke-width="3" opacity=".7"/>',
'<circle cx="175" cy="186" r="12" fill="#082441" stroke="#fff1bf" stroke-width="5"/>',
'</svg>'
].join('');
const css=[
'*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden}',
'body{background:#051123;color:#f9fbff;font-family:Arial,Helvetica,sans-serif}',
'.poster{position:relative;width:1080px;height:1350px;overflow:hidden;padding:48px 56px 28px;',
'background:radial-gradient(ellipse 830px 570px at 106% -6%,#2e588399,transparent 70%),',
'radial-gradient(ellipse 760px 700px at -18% 98%,#1f457574,transparent 68%),',
'linear-gradient(146deg,#061326,#0a1e39 62%,#061021)}',
'.poster:before{position:absolute;inset:0;content:"";opacity:.15;pointer-events:none;',
'background:repeating-linear-gradient(0deg,transparent 0px,transparent 42px,#7798bc 43px,transparent 44px)}',
'.content{position:relative;z-index:2}',
'.top{display:flex;justify-content:space-between;align-items:center;padding-bottom:23px;border-bottom:1px solid #4b6a87}',
'.series{font-size:18px;color:#ebc68e;letter-spacing:3px;font-weight:900}',
'.brand{font-size:29px;font-weight:900}.brand span{color:#f2c483}',
'.heading{font-size:65px;line-height:1.02;letter-spacing:-2px;margin:30px 0 0;font-weight:900;text-shadow:0 8px 15px #0009}',
'.heading em{font-style:normal;color:#f3c781}',
'.goldline{width:145px;height:5px;border-radius:5px;background:linear-gradient(90deg,#f0c27e,#fff0b9);margin:20px 0 13px}',
'.sub{font-size:20px;color:#b7ccdf;margin:0}',
'.hero{height:527px;margin-top:26px;background:linear-gradient(145deg,#1a3d63ed,#091d37ef);',
'position:relative;border:1px solid #6e90b0;border-radius:34px;overflow:hidden;',
'box-shadow:0 25px 42px #0008,inset 0 2px #ffffff1f}',
'.hero:before{position:absolute;right:-100px;top:15px;width:440px;height:460px;content:"";',
'background:radial-gradient(circle,#c6a16b3f,transparent 69%)}',
'.herohead{position:relative;z-index:3;display:flex;justify-content:space-between;',
'align-items:center;padding:30px 32px 0}',
'.area{font-size:18px;color:#efce94;font-weight:900;letter-spacing:1.5px}',
'.pending{border:1px solid #bb9e6d;border-radius:30px;padding:10px 14px;',
'color:#f7dbad;background:#6b553453;font-size:14px;font-weight:900}',
'.globe{position:absolute;right:-72px;top:120px;width:369px;height:369px;',
'opacity:.96;filter:drop-shadow(0 14px 17px #000a) drop-shadow(0 0 25px #b38b4b64)}',
'.kind{position:relative;z-index:4;margin:31px 32px 0;font-size:43px;font-weight:900;',
'letter-spacing:-1px;text-shadow:0 7px 13px #000a}',
'.rule{position:relative;z-index:4;margin:14px 32px;width:180px;height:4px;',
'background:linear-gradient(90deg,#e6c186,transparent)}',
'.story{position:relative;z-index:5;margin:22px 0 0 32px;width:663px;',
'font-size:55px;line-height:1.12;letter-spacing:-1.2px;font-weight:900;',
'overflow-wrap:break-word;text-shadow:0 5px 17px #000e}',
'.original{position:absolute;bottom:25px;left:32px;color:#dfbb88;font-size:15px;',
'font-weight:900;letter-spacing:1.5px}',
'.tiles{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}',
'.tile{height:150px;background:linear-gradient(140deg,#193c60,#0a1b33);',
'border:1px solid #476f90;border-radius:24px;padding:22px 24px;box-shadow:0 11px 20px #0004}',
'.tilelabel{font-size:15px;color:#b5cadf;font-weight:900;letter-spacing:1.1px}',
'.tilevalue{font-size:25px;color:#f5d09a;font-weight:900;margin-top:14px;line-height:1.16}',
'.tiledetail{font-size:15px;color:#a6bed6;margin-top:10px}',
'.review{margin-top:19px;padding:21px 24px;background:#142d4bcf;border:1px solid #4b7294;',
'border-radius:23px;display:flex;gap:19px;align-items:center;height:111px}',
'.reviewicon{font-size:37px;width:58px;height:58px;border-radius:17px;background:#c6a06930;',
'display:grid;place-items:center;color:#f5d09a;flex:none}',
'.reviewtitle{font-size:21px;color:#f7d39e;font-weight:900}',
'.reviewdesc{font-size:16px;color:#c0d0e0;line-height:1.3;margin-top:7px}',
'.footer{margin-top:23px;padding-top:17px;border-top:1px solid #456d8d;',
'display:flex;justify-content:space-between;gap:12px;font-size:15px;color:#b8cce1}',
'.note{text-align:center;font-size:14px;color:#a0b9d2;margin-top:11px}',
'.demo{position:absolute;z-index:10;left:0;right:0;bottom:0;height:51px;',
'background:#a82d48;color:white;display:grid;place-items:center;font-size:19px;font-weight:900;letter-spacing:1.4px}'
].join('');
const h=[
'<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>',css,'</style></head><body>',
'<main class="poster"><div class="content">',
'<header class="top"><div class="series">AFRIQUE & CRYPTO · #11</div>',
'<div class="brand">MR <span>XPRONOS</span> ◆</div></header>',
'<h1 class="heading">RÉGLEMENTATION<br><em>CRYPTO EN AFRIQUE.</em></h1>',
'<div class="goldline"></div><p class="sub">Veille africaine · UEMOA · CEMAC · CEDEAO</p>',
'<section class="hero"><div class="herohead"><span class="area">',esc(a.region),
'</span><span class="pending">ARTICLE ATTRIBUÉ</span></div>',
'<div class="globe">',globeSvg,'</div>',
'<div class="kind">ACTU CRYPTO<br>AFRICAINE</div><div class="rule"></div>',
'<div class="story">',esc(headline),'</div>',
'<div class="original">TITRE ORIGINAL ET LIEN DU MÉDIA EN LÉGENDE TELEGRAM</div></section>',
'<section class="tiles"><div class="tile"><div class="tilelabel">THÈME DE L’ARTICLE</div>',
'<div class="tilevalue">',esc(a.topic),'</div>',
'<div class="tiledetail">Statut légal non confirmé</div></div>',
'<div class="tile"><div class="tilelabel">',isOfficial?'SOURCE INSTITUTIONNELLE':'MÉDIA SOURCE',
'</div><div class="tilevalue">',esc(a.source),'</div>',
'<div class="tiledetail">',date,' UTC</div></div></section>',
'<div class="review"><div class="reviewicon">⚖</div><div>',
'<div class="reviewtitle">ARTICLE JOURNALISTIQUE ATTRIBUÉ</div>',
'<div class="reviewdesc">Titre et source RSS identifiés. Le statut juridique doit être vérifié dans les documents officiels.</div>',
'</div></div><div class="footer"><span>Source : ',esc(a.source),'</span>',
'<span>Collecte : ',ts,' UTC</span></div>',
'<div class="note">Information médiatique attribuée · Aucun statut légal certifié.</div>',
'</div>',qa?'<div class="demo">SIMULATION QA · ACTUALITÉ FICTIVE · NE PAS PUBLIER</div>':'',
'</main></body></html>'
].join('');
const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
 await page.setContent(h,{waitUntil:'load'});
 await page.evaluate(async()=>{
   await document.fonts.ready;
   const t=document.querySelector('.story'), hero=document.querySelector('.hero');
   let font=parseFloat(getComputedStyle(t).fontSize);
   while(t.getBoundingClientRect().bottom>hero.getBoundingClientRect().bottom-61&&font>30){
     font-=1;t.style.fontSize=font+'px';
   }
 });
 const bounds=await page.evaluate(()=>{
   const b=q=>document.querySelector(q).getBoundingClientRect();
   return {scroll:document.documentElement.scrollHeight,note:b('.note').bottom,
     story:b('.story').bottom,hero:b('.hero').bottom}
 });
 if(bounds.scroll>1350||bounds.note>1322||bounds.story>bounds.hero-59)
   throw Error('Poster overflow '+JSON.stringify(bounds));
 await mkdir('crypto/generated/test',{recursive:true});
 await page.screenshot({path:output});
 console.log('REG11_PREMIUM_TEST_RENDERED',qa?'QA_NOT_PUBLISHABLE':'REAL_TEST_ONLY',a.source,output);
}finally{await browser.close()}
