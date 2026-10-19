import {moneyGlobalUsd,moneyPriceUsd,validateGlobalUsd,shortDateFr} from './crypto_poster_format.mjs';
import { chromium } from 'playwright';
import { readFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
const data=JSON.parse(await readFile('crypto/generated/test/market_design_data.json','utf8'));
const rows=data.rows;
if(rows.length!==5||rows.some(r=>!Array.isArray(r.sparkline)||r.sparkline.length<12))throw Error('Missing real chart data');
const cap=rows[0].market_cap_total,vol=rows[0].global_volume_24h,fear=rows[0].fear_greed;
validateGlobalUsd(cap,vol);
if(!(cap>0&&vol>0))throw Error('Missing global market totals');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=moneyPriceUsd;
const icon=(name,color='#b3c9e8')=>{
 const shapes={globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a16 16 0 0 1 0 18M12 3a16 16 0 0 0 0 18"/>',chart:'<path d="M3 3v18h18M7 16l4-4 3 3 6-8"/>',activity:'<path d="M3 12h4l3-7 4 14 3-7h4"/>'};
 return '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="'+color+'" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+shapes[name]+'</svg>';
};
function chart(points,up){const min=Math.min(...points),max=Math.max(...points),span=max-min||1;const coords=points.map((v,i)=>[(i/(points.length-1))*265,74-(v-min)/span*62+4]);const d=coords.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');const color=up?'#3df0a8':'#ff698d';return '<svg viewBox="0 0 265 85" preserveAspectRatio="none"><defs><linearGradient id="g'+(up?'u':'d')+'" x1="0" x2="0" y1="0" y2="1"><stop stop-color="'+color+'" stop-opacity=".32"/><stop offset="1" stop-color="'+color+'" stop-opacity="0"/></linearGradient></defs><path d="'+d+' L265 85 L0 85 Z" fill="url(#g'+(up?'u':'d')+')"/><path d="'+d+'" stroke="'+color+'" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'}
// Reuse the approved premium coin artwork from V1, never recreate logos with glyphs.
const logoFiles={BTC:'btc.png',ETH:'eth.png',SOL:'sol.png',BNB:'bnb.png',XRP:'xrp.png'};
const logoData={};
for(const [symbol,filename] of Object.entries(logoFiles)){
  const buffer=await readFile(join('crypto/assets/premium_market',filename));
  if(buffer.length<500)throw Error('Invalid approved coin logo: '+filename);
  logoData[symbol]='data:image/png;base64,'+buffer.toString('base64');
}
const cards=rows.map(r=>{
 const up=r.change>=0;
 const arrow=up?'▲':'▼';
 return '<article class="coin"><div class="symbol"><img src="'+logoData[r.symbol]+'" alt="'+esc(r.symbol)+'"/></div><div class="identity"><b>'+esc(r.name)+'</b><small>'+esc(r.symbol)+' / USD</small></div><div class="spark">'+chart(r.sparkline,r.sparkline[r.sparkline.length-1]>=r.sparkline[0])+'</div><div class="quote"><b>'+money(r.price)+'</b><span class="'+(up?'up':'down')+'">'+arrow+' '+(up?'+':'')+Number(r.change).toFixed(2)+'% 24H</span></div></article>';
}).join('');
let html=`<!doctype html><html><head><meta charset="utf-8"/><style>
*{box-sizing:border-box}body{margin:0;width:1080px;height:1350px;color:#fff;font-family:Arial,sans-serif;background:radial-gradient(ellipse at 85% -10%,#2c5793 0%,transparent 46%),radial-gradient(ellipse at 0% 65%,#112d5e 0%,transparent 48%),linear-gradient(135deg,#061024,#091b38 75%,#040b1c);overflow:hidden}.page{padding:65px 58px}.eyebrow{font-size:20px;letter-spacing:5px;color:#dfbc73;font-weight:700}.top{display:flex;justify-content:space-between;align-items:center}.logo{font-weight:900;font-size:27px;letter-spacing:1px;color:#f5ce86}.heading{margin:43px 0 10px;font-size:67px;line-height:1.02;letter-spacing:-2px;font-weight:900}.heading em{font-style:normal;color:#f4c678}.sub{color:#a7bfdc;font-size:21px;margin-bottom:38px}.coins{display:grid;gap:13px}.coin{height:142px;border:1px solid rgba(164,195,244,.35);border-radius:24px;display:flex;align-items:center;padding:20px 25px;background:linear-gradient(105deg,rgba(35,62,105,.87),rgba(8,24,53,.94));box-shadow:0 13px 24px #0004,inset 0 1px #ffffff18}.symbol{width:96px;height:96px;border-radius:50%;display:grid;place-items:center;flex-shrink:0;filter:drop-shadow(0 6px 12px #0009)}.symbol img{width:96px;height:96px;object-fit:contain;display:block}.identity{width:175px;padding-left:15px;display:grid;gap:7px}.identity b{font-size:26px}.identity small{color:#9db8db;font-size:16px}.spark{width:245px;height:85px;margin-left:8px;opacity:.95}.spark svg{width:100%;height:100%}.quote{margin-left:auto;text-align:right;display:grid;gap:10px}.quote b{font-size:25px}.quote span{font-size:20px;font-weight:800;letter-spacing:.2px}.up{color:#46e9a8}.down{color:#ff7b9a}.metrics{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:26px}.metric{height:126px;background:linear-gradient(145deg,#122b50,#09182e);border:1px solid #345c87;border-radius:20px;padding:18px}.label{display:flex;align-items:center;gap:8px;color:#aac5e4;font-size:14px;letter-spacing:.3px;font-weight:700}.value{font-size:30px;font-weight:900;margin-top:13px}.small{font-size:15px;color:#42e4a3}.foot{display:flex;justify-content:space-between;margin-top:24px;color:#88a7c9;font-size:14px}.goldline{width:105px;height:5px;background:#edbf6a;border-radius:10px;margin-top:22px}
</style></head><body><div class="page"><div class="top"><div class="eyebrow">MARKET INTELLIGENCE</div><div class="logo">MR XPRONOS <span style="color:#e8bd70">◆</span></div></div><div class="heading">COURS DU MARCHÉ<br/><em>CRYPTO.</em></div><div class="goldline"></div><div class="sub">Données réelles • 5 actifs majeurs • Courbes historiques 48h</div><section class="coins">${cards}</section><section class="metrics"><div class="metric"><div class="label">${icon('globe')} CAPITALISATION</div><div class="value">${moneyGlobalUsd(cap)}</div><div class="small">${Number(rows[0].market_cap_change_24h||0)>=0?'+':''}${Number(rows[0].market_cap_change_24h||0).toFixed(2)}% sur 24h</div></div><div class="metric"><div class="label">${icon('chart')} VOLUME GLOBAL 24H</div><div class="value">${moneyGlobalUsd(vol)}</div></div><div class="metric"><div class="label">${icon('activity')} FEAR & GREED</div><div class="value">${fear==null?'N/D':fear+'/100'}</div></div></section><div class="foot"><span>Source cours : ${esc(data.provider)} • Global : CoinLore</span><span>${esc(data.timestamp.slice(0,16).replace('T',' '))} UTC</span></div></div></body></html>`;
// Explicit watermark on offline-only fixture output. Never misrepresent QA as real.
if(data.provider==='QA_SIMULATION'){
 html=html.replace('</body>','<div style="position:fixed;z-index:100;bottom:0;left:0;right:0;background:#a82c48;padding:13px;text-align:center;font:900 21px Arial;color:white">SIMULATION QA — DONNÉES FICTIVES — NE PAS PUBLIER</div></body>');
}
const browser=await chromium.launch({headless:true});try{const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});await page.setContent(html);await mkdir('crypto/generated/test',{recursive:true});await page.screenshot({path:'crypto/generated/test/prices_v2.png'});console.log('V2_RENDERED real data, original V1 logos, 5 charts, global cap and global volume');}finally{await browser.close()}
