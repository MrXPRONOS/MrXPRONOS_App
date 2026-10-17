/** Mr XPRONOS — Fear & Greed #05: premium editorial dashboard, 1080×1350. */
import {chromium} from 'playwright';
import {readFile,mkdir} from 'node:fs/promises';
const demo=process.argv.includes('--demo');
const input=demo?'crypto/generated/test/fear_v2_demo.json':'crypto/generated/test/fear_v2_data.json';
const output=demo?'crypto/generated/test/fear_v2_demo.png':'crypto/generated/test/fear_v2.png';
const data=JSON.parse(await readFile(input,'utf8'));
if(data.status!==(demo?'demo':'real_data') || Boolean(data.is_demo)!==demo)
 throw Error('Fear score not validated as '+(demo?'demo':'real')+' data');
if(data.provider!==(demo?'SIMULATION':'Alternative.me'))throw Error('Unverified source');
if(!Number.isInteger(data.score)||data.score<0||data.score>100)throw Error('Invalid score');
if(!Array.isArray(data.history)||data.history.length!==7 ||
 data.history.some(h=>!/^\d{4}-\d{2}-\d{2}$/.test(h.date)||!Number.isInteger(h.value)||h.value<0||h.value>100))
 throw Error('Missing actual seven-day history');
if(data.history[6].value!==data.score || data.delta_1d!==data.score-data.history[5].value ||
 data.delta_6d!==data.score-data.history[0].value)throw Error('Mismatched historical market data');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels=[['PEUR EXTRÊME',0,24],['PEUR',25,44],['NEUTRE',45,54],['AVIDITÉ',55,74],['AVIDITÉ EXTRÊME',75,100]];
const segmentColors=['#ee5574','#ff995c','#f3ce72','#89dc99','#37d9b0'];
const moodIndex=labels.findIndex(([,min,max])=>data.score>=min&&data.score<=max);
if(moodIndex<0 || data.classification!==labels[moodIndex][0])throw Error('Wrong classification');
const accent=segmentColors[moodIndex];
const geometry=(degree,radius=232)=>{const rad=degree*Math.PI/180;return [450+radius*Math.cos(rad),294-radius*Math.sin(rad)];};
function arc(a,b,color){const start=geometry(a),end=geometry(b);return `<path d="M ${start[0].toFixed(3)} ${start[1].toFixed(3)} A 232 232 0 0 1 ${end[0].toFixed(3)} ${end[1].toFixed(3)}" fill="none" stroke="${color}" stroke-width="43" stroke-linecap="round" filter="url(#ringGlow)"/>`}
const marks=[0,25,45,55,75,100];
const segments=marks.slice(0,-1).map((m,i)=>arc(180-m*1.8-2.8,180-marks[i+1]*1.8+2.8,segmentColors[i])).join('');
const needleEnd=geometry(180-data.score*1.8,187);
const needle=`<line x1="450" y1="294" x2="${needleEnd[0].toFixed(2)}" y2="${needleEnd[1].toFixed(2)}" stroke="#000d24" stroke-width="19" stroke-linecap="round" filter="url(#needleShadow)"/><line x1="450" y1="294" x2="${needleEnd[0].toFixed(2)}" y2="${needleEnd[1].toFixed(2)}" stroke="url(#needle)" stroke-width="9" stroke-linecap="round"/><circle cx="450" cy="294" r="22" fill="#061125" stroke="#dfedff" stroke-width="5"/><circle cx="450" cy="294" r="8" fill="#eac989"/>`;
const svg=`<svg class="gauge" viewBox="0 0 900 480" role="img" aria-label="Fear and Greed : ${data.score} sur 100"><defs>
 <filter id="ringGlow" x="-25%" y="-40%" width="150%" height="190%"><feGaussianBlur in="SourceAlpha" stdDeviation="2.7" result="blur"/><feOffset dy="4" result="offset"/><feMerge><feMergeNode in="offset"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="needleShadow" x="-30%" y="-40%" width="160%" height="180%"><feGaussianBlur stdDeviation="4"/></filter>
 <linearGradient id="needle"><stop stop-color="#b6c6e6"/><stop offset=".4" stop-color="#fff6c7"/><stop offset="1" stop-color="#f3cf86"/></linearGradient>
 </defs>
 <path d="M 218 294 A 232 232 0 0 1 682 294" stroke="#07152f" stroke-width="55" fill="none"/>
 ${segments}
 <circle cx="450" cy="294" r="173" fill="#081a37" stroke="#ffffff14" stroke-width="2"/>
 ${needle}
 <text x="450" y="386" text-anchor="middle" fill="#f9fbff" font-size="91" font-weight="900" style="paint-order:stroke;stroke:#0b1c39;stroke-width:3px">${data.score}<tspan font-size="27" fill="#a9c0df">/100</tspan></text>
 <text x="450" y="431" text-anchor="middle" fill="${accent}" font-size="27" font-weight="900" letter-spacing="2">${esc(data.classification)}</text>
 </svg>`;
const direction=n=>n>0?'+':n===0?'':'−';
const change=(n)=>direction(n)+Math.abs(n)+' pts';
const history=data.history.map((point,i)=>{
 const color=segmentColors[labels.findIndex(([,min,max])=>point.value>=min&&point.value<=max)];
 const date=esc(point.date.slice(8,10)+'/'+point.date.slice(5,7));
 const height=16+point.value*0.79;
 return `<div class="day"><div class="point">${point.value}</div><div class="bar-box"><div class="bar" style="height:${height.toFixed(2)}px;background:linear-gradient(180deg,${color},${color}55);box-shadow:0 0 18px ${color}33"></div></div><div class="date">${date}</div></div>`;
}).join('');
const observedDate=esc(String(data.observed_at).slice(8,10)+'/'+String(data.observed_at).slice(5,7)+'/'+String(data.observed_at).slice(0,4));
const statusStamp=demo?'SIMULATION — DONNÉES FICTIVES':'INDICE OFFICIEL • DONNÉES RÉELLES';
const html=`<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{width:1080px;height:1350px;overflow:hidden;margin:0}body{font-family:Arial,Helvetica,sans-serif;color:#f9fbff;background:radial-gradient(ellipse at 90% -12%,#2e568b 0%,transparent 48%),radial-gradient(ellipse at -10% 82%,#142f5c 0%,transparent 54%),linear-gradient(135deg,#051024,#091c39 75%,#040b1c)}.page{padding:45px 56px 0}.top{display:flex;align-items:center;justify-content:space-between}.eyebrow{font-weight:900;letter-spacing:4px;color:#e9c786;font-size:19px}.brand{font-size:28px;color:#f2cf8a;font-weight:900;text-shadow:0 4px 6px #000b}.heading{font-weight:900;font-size:72px;line-height:1.04;letter-spacing:-2px;text-shadow:0 9px 16px #000a;margin:32px 0 0}.heading em{font-style:normal;color:#f1c77e;text-shadow:0 4px #76532d,0 10px 12px #0009}.goldline{margin-top:15px;width:125px;height:5px;border-radius:6px;background:linear-gradient(90deg,#ddac62,#fff0ae);box-shadow:0 0 20px #e2ba6566}.subtitle{font-size:20px;color:#b5c9e1;margin-top:14px}.hero{height:575px;margin-top:19px;position:relative;background:linear-gradient(140deg,#1a3a65ed 0%,#0b1d3beb 60%,#0d2245ef);border:1px solid #5683b1;border-radius:34px;box-shadow:0 24px 46px #0008,inset 0 2px #ffffff35;overflow:hidden}.hero:before{content:'';position:absolute;inset:0;background:radial-gradient(circle at 50% 44%,${accent}18,transparent 52%);pointer-events:none}.hero-top{display:flex;justify-content:space-between;align-items:center;padding:24px 30px 0}.overline{font-size:18px;letter-spacing:2px;color:#abc5e2;font-weight:900}.time{font-size:17px;color:#d5e5f4}.gauge{position:absolute;top:47px;left:48px;width:885px;height:468px;filter:drop-shadow(0 12px 16px #0009)}.scale{position:absolute;bottom:18px;left:30px;right:30px;display:flex;align-items:center;gap:11px}.scaleitem{flex:1;text-align:center;font-size:13px;color:#a8c0dd;font-weight:800;letter-spacing:.3px}.scaleitem b{display:block;margin:0 auto 9px;height:7px;border-radius:3px}.scaleitem.active{color:#fff}.scaleitem.active b{box-shadow:0 0 18px ${accent}}.tile-row{margin-top:15px;display:grid;grid-template-columns:repeat(3,1fr);gap:13px}.tile{height:111px;background:linear-gradient(136deg,#193961,#091b33);border:1px solid #355c85;border-radius:21px;box-shadow:0 13px 24px #0004,inset 0 1px #ffffff19;padding:18px 20px}.tile .label{color:#a8c1e1;font-size:16px;letter-spacing:1px;font-weight:800}.tile strong{display:block;font-size:30px;margin-top:17px;font-weight:900}.trend{margin-top:13px;border-radius:26px;background:linear-gradient(130deg,#122d52bb,#07182fdd);border:1px solid #365e8b;height:205px;padding:15px 30px 10px}.trend-header{display:flex;justify-content:space-between;align-items:center}.trend-head{font-size:19px;font-weight:900;letter-spacing:1.5px}.trend-sub{font-size:16px;color:#9bbada}.days{height:144px;margin-top:8px;display:grid;grid-template-columns:repeat(7,1fr);gap:22px;align-items:end}.day{height:144px;display:flex;align-items:center;flex-direction:column;justify-content:flex-end}.point{font-size:16px;font-weight:900;margin-bottom:7px}.bar-box{height:99px;display:flex;align-items:end}.bar{width:50px;max-height:99px;border-radius:11px 11px 4px 4px;border:1px solid #ffffff37}.date{color:#a8c2de;font-size:14px;margin-top:7px}.footer{display:flex;justify-content:space-between;gap:25px;margin-top:18px;color:#a6c2df;font-size:15px}.note{text-align:center;margin-top:8px;font-size:14px;color:#86a7ce}.demo{position:absolute;inset:0 auto auto 0;width:100%;z-index:9;background:#ad2e40;color:white;text-align:center;font-weight:900;letter-spacing:1.5px;padding:16px;font-size:19px;box-shadow:0 8px 13px #0008}
</style></head><body><div class="page"><div class="top"><div class="eyebrow">ANALYSE DE MARCHÉ</div><div class="brand">MR XPRONOS ◆</div></div><div class="heading">INDICE FEAR &amp; GREED<br/><em>CRYPTO</em></div><div class="goldline"></div><div class="subtitle">Le baromètre du sentiment du marché • Indice sur 100</div><section class="hero"><div class="hero-top"><div class="overline">SENTIMENT DU MARCHÉ</div><div class="time">MESURE DU ${observedDate} (UTC)</div></div>${svg}<div class="scale">${labels.map((l,i)=>`<div class="scaleitem ${moodIndex===i?'active':''}"><b style="background:${segmentColors[i]}"></b>${esc(l[0])}</div>`).join('')}</div></section><section class="tile-row"><div class="tile"><div class="label">INDICE PRÉCÉDENT (J-1)</div><strong>${data.yesterday_score}<span style="color:#b7cde2;font-size:20px">/100</span></strong></div><div class="tile"><div class="label">ÉVOLUTION SUR 1 JOUR</div><strong style="color:${data.delta_1d>=0?'#56e9bd':'#ff7c9b'}">${change(data.delta_1d)}</strong></div><div class="tile"><div class="label">ÉVOLUTION SUR 6 JOURS</div><strong style="color:${data.delta_6d>=0?'#56e9bd':'#ff7c9b'}">${change(data.delta_6d)}</strong></div></section><section class="trend"><div class="trend-header"><div class="trend-head">ÉVOLUTION SUR 7 JOURS</div><div class="trend-sub">Mesures quotidiennes • 0 à 100</div></div><div class="days">${history}</div></section><div class="footer"><span>Source : ${esc(data.provider)} · Crypto Fear &amp; Greed Index</span><span>${statusStamp}</span></div><div class="note">Indicateur de sentiment uniquement : ni prévision ni conseil d’achat ou de vente.</div></div>${demo?'<div class="demo">SIMULATION • DONNÉES FICTIVES — CANAL TEST UNIQUEMENT</div>':''}</body></html>`;
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
 await page.setContent(html,{waitUntil:'load'});
 const b=await page.evaluate(()=>({h:document.documentElement.scrollHeight,note:document.querySelector('.note').getBoundingClientRect().bottom,chart:document.querySelector('.trend').getBoundingClientRect().bottom}));
 if(b.h>1350||b.note>1350||b.chart>1350)throw Error('Overflow in poster: '+JSON.stringify(b));
 await mkdir('crypto/generated/test',{recursive:true});
 await page.screenshot({path:output});
 console.log('FEAR_V2_RENDERED',demo?'DEMO_NOT_PUBLISHED':'REAL',data.score,data.classification,output);
}finally{await browser.close()}