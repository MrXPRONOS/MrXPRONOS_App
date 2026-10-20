#!/usr/bin/env node
// Fidélité visuelle à la capture de référence : UI indonésienne, bleu/blanc, 1080px.
// Génère une maquette, pas une preuve de pari. --input JSON facultatif.
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const pairs=[
 ['Sabah Baku','Borussia Dortmund','20.10.2026 (23:45)','Total (1.5) Over','1.063'],
 ['Fenerbahçe','Slavia Prague','20.10.2026 (23:45)','Double Chance. 1X','1.204'],
 ['Liverpool','Villarreal','21.10.2026 (02:00)','1x2. M1','1.155'],
 ['Manchester City','AEK Athens','21.10.2026 (02:00)','1x2. M1','1.124'],
 ['Napoli','Bodø-Glimt','21.10.2026 (02:00)','Double Chance. 1X','1.215'],
 ['Porto','PSV Eindhoven','21.10.2026 (02:00)','Total (1) Over','1.02'],
 ['Paris Saint-Germain','Barcelona','21.10.2026 (02:00)','1X2 + Masing-Masing Tim Mencetak. M1 Dan Kedua Tim Mencetak Skor - Ya','2.98'],
 ['Roma','Slovan Bratislava','21.10.2026 (02:00)','1x2. M1','1.169'],
 ['VfB Stuttgart','Atlético Madrid','21.10.2026 (02:00)','Total (1.5) Over','1.084'],
 ['Lille OSC','Galatasaray','21.10.2026 (02:45)','Peluang Ganda + Kedua Tim Mencetak Skor. 1X Dan Kedua Tim Mencetak Skor = Ya','2.04'],
 ['Como','Manchester United','21.10.2026 (23:45)','Kedua Tim Mencetak Skor. Ya','1.51']
];
const sample={
 created_at:'20.10.2026 (11:17)',category:'Akumulator',ticket_id:'98159324917',
 combined_odds:'32.247',stake:'18000 Rp',potential_win:'580460.38 Rp',completed:0,status:'Diterima',
 legs:pairs.map(([home_team,away_team,event_date,selection,odds])=>({
  home_team,away_team,event_date,selection,odds,league:'Sepak bola. Liga Champions UEFA',status:'Diterima'
 }))
};
const args=process.argv.slice(2);
const getArg=(name,def)=>{const i=args.indexOf(name);return i>=0&&args[i+1]?args[i+1]:def};
const input=getArg('--input',process.env.ACCUMULATOR_INPUT||'');
const output=getArg('--output',process.env.ACCUMULATOR_OUTPUT||'telegram_out/accumulator_reference.png');
const data=input?JSON.parse(fs.readFileSync(input,'utf8')):sample;
if(!Array.isArray(data.legs)||!data.legs.length||data.legs.length>80)throw Error('legs doit contenir 1 à 80 matchs');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=x=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const localLogo=p=>{
 if(!p||/^https?:/.test(p))return null;
 const name=path.resolve(String(p).replace(/^\//,''));
 if(!fs.existsSync(name)||!fs.statSync(name).isFile())return null;
 const mime=name.endsWith('.webp')?'image/webp':name.endsWith('.svg')?'image/svg+xml':'image/png';
 return 'data:'+mime+';base64,'+fs.readFileSync(name).toString('base64');
};
const cached=new Map();
try{
 const json=JSON.parse(fs.readFileSync('data.json','utf8'));
 for(const m of (json.matches||[]))for(const [n,p] of [[m.home_team,m.home_logo||m.home_team_logo],[m.away_team,m.away_logo||m.away_team_logo]]){
   const logo=localLogo(p);if(logo&&n)cached.set(norm(n),logo);
 }
}catch{}
const aliases={'Sabah Baku':'Sabah FK','Slavia Prague':'Slavia Praha','Bodø-Glimt':'Bodo Glimt','Como':'Como 1907'};
async function getLogo(name,provided){
 const direct=localLogo(provided);if(direct)return direct;
 const known=cached.get(norm(name));if(known)return known;
 if(process.env.NO_REMOTE_LOGOS==='1')return null;
 try{
  const search=aliases[name]||name;
  const r=await fetch('https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t='+encodeURIComponent(search),{signal:AbortSignal.timeout(6000)});
  if(!r.ok)return null;
  const a=(await r.json()).teams||[];
  const t=a.find(x=>norm(x.strTeam)===norm(search))||a.find(x=>String(x.strSport||'').toLowerCase()==='soccer');
  const url=t?.strBadge||t?.strTeamBadge;
  if(!url||!/^https:\/\//.test(url))return null;
  const image=await fetch(url,{signal:AbortSignal.timeout(6000)});
  if(!image.ok)return null;
  const bytes=Buffer.from(await image.arrayBuffer());
  if(bytes.length>300000||bytes.length<100)return null;
  return 'data:'+(image.headers.get('content-type')||'image/png').split(';')[0]+';base64,'+bytes.toString('base64');
 }catch{return null;}
}
const overrides={};
for(const leg of data.legs){if(leg.home_logo)overrides[leg.home_team]=leg.home_logo;if(leg.away_logo)overrides[leg.away_team]=leg.away_logo;}
const teams=[...new Set(data.legs.flatMap(l=>[l.home_team,l.away_team]))];
const logos=new Map(await Promise.all(teams.map(async name=>[name,await getLogo(name,overrides[name])])));
const shirt='data:image/svg+xml;charset=utf-8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 70 76"><path d="M24 5h22l7 9 13 7-8 15-8-3v34H20V33l-8 3-8-15 13-7z" stroke="#d9ad00" stroke-width="2" fill="#ffda00"/><path d="M24 5q11 17 22 0" fill="#212121"/><path d="M21 65h29" stroke="#cf0000" stroke-width="7"/></svg>');
function imageOf(name){
 const value=name==='Borussia Dortmund'?shirt:logos.get(name);
 return value?'<img class="crest" src="'+esc(value)+'" alt="">':'<div class="crest fallback">'+esc(String(name||'?').slice(0,2).toUpperCase())+'</div>';
}
const ball='<svg class="ball" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#d9e5e9"/><path fill="#758f9e" d="M12 5 7 8l2 5h6l2-5zm-6 9-3-2 1 6 4 2 2-5zm12 0-4 1 2 5 4-2 1-6z"/></svg>';
function dateOf(val){
 if(!val)return '';
 if(/^\d\d\.\d\d\.\d{4}/.test(val))return val;
 const d=new Date(val);
 if(!Number.isFinite(d.getTime()))return String(val);
 const p=new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);
 return p.replace(', ',' (')+')';
}
function leg(l){
 const prediction=l.selection||l.prediction?.label||l.prediction?.type||l.prediction?.double_chance||'—';
 const odds=l.odds||l.prediction?.odds||'—';
 return '<section class="leg"><div class="league-head">'+ball+'<div><div class="league">'+esc(l.league||'Sepak bola. Liga Champions UEFA')+'</div><div class="date">'+esc(dateOf(l.event_date||l.date))+' <span class="utc">UTC</span></div></div></div>'
 +'<div class="teams"><span class="team home">'+esc(l.home_team)+'</span>'+imageOf(l.home_team)+'<b class="vs">VS</b>'+imageOf(l.away_team)+'<span class="team away">'+esc(l.away_team)+'</span></div>'
 +'<div class="market"><span>'+esc(prediction)+'</span><b>'+esc(odds)+'</b></div>'
 +'<div class="status"><span>Status:</span><span>'+esc(l.status||data.status||'—')+'</span></div></section>';
}
const n=data.legs.length;
const combined=data.combined_odds??data.legs.reduce((p,l)=>p*Number(l.odds||l.prediction?.odds||1),1).toFixed(3);
const CSS='*{box-sizing:border-box}html,body{margin:0;padding:0}body{width:262px;background:#edf1f5;color:#12384d;font-family:Arial,Roboto,Helvetica,sans-serif;-webkit-font-smoothing:antialiased}#app{width:262px;background:#eef2f6}.phone{height:26px;background:#fff;color:#6b7981;font-size:7px;padding:9px 9px 0;display:flex;justify-content:space-between}.nav{height:37px;background:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 11px;color:#668b9c;border-bottom:1px solid #d9e1e6}.back{font-size:22px;font-weight:300}.nav-title{font-size:10px;font-weight:700}.nav-right{font-size:17px;letter-spacing:10px;margin-right:-9px}.ticket{margin:4px 5px 0;background:#fff;border-radius:7px 7px 0 0;overflow:hidden;border:1px solid #e1e7ec;box-shadow:0 1px 3px #dbe4e9}.summary{padding:10px 9px 6px}.stamp{color:#91a4ae;font-size:6.4px;line-height:10px}.utc{display:inline-block;background:#6383dc;color:#fff;padding:1px 3px;border-radius:2px;font-size:6px;font-weight:800}.name{font-weight:800;font-size:10px;color:#163f56}.nr{font-weight:600;font-size:6.5px;margin-left:5px;color:#22485e}.overview{border-top:1px solid #edf0f2;margin-top:9px;padding-top:5px}.overview-top{display:flex;align-items:center;justify-content:space-between;font-size:7.4px;font-weight:700;line-height:13px;margin-bottom:3px}.overview-top .left{display:flex;gap:7px;align-items:center}.overview-top .tile{font-size:11px;color:#67889a}.overview-line{height:15px;display:flex;justify-content:space-between;align-items:center;font-size:7px}.overview-line .label{color:#7e9ba9}.overview-line strong{color:#12384d;font-size:8px}.overview-line .accept{color:#4389bd}.check{background:#3e9bc7;color:#fff;border-radius:50%;display:inline-flex;width:10px;height:10px;align-items:center;justify-content:center;margin-right:4px;font-size:8px}.leg{min-height:106px;border-top:1px solid #e4e9ed;background:#fff;padding:7px 9px 6px}.league-head{display:flex;align-items:flex-start;gap:6px;min-height:24px}.ball{width:11px;height:11px;margin-top:2px;flex:none}.league{font-size:7px;font-weight:700;color:#6c8797;line-height:11px}.date{font-size:6.3px;color:#8ba1ae}.teams{height:39px;display:grid;grid-template-columns:minmax(0,1fr) 27px 19px 27px minmax(0,1fr);column-gap:3px;align-items:center}.team{font-size:6.7px;line-height:1.18;color:#18394b;font-weight:700}.team.home{text-align:right}.team.away{text-align:left}.crest{height:25px;width:25px;object-fit:contain}.crest.fallback{border-radius:50%;border:1px solid #d7e2e8;background:#edf3f7;font-weight:700;color:#67889c;font-size:7px;display:grid;place-items:center}.vs{text-align:center;font-size:9px;color:#173e53}.market{min-height:15px;padding-top:2px;display:flex;align-items:flex-start;justify-content:space-between;gap:5px;font-weight:700;color:#183b4d;font-size:6.7px;line-height:1.13}.market span{max-width:196px}.market b{font-size:7.5px;white-space:nowrap}.status{display:flex;justify-content:space-between;color:#9cb0bb;font-size:6.6px;margin-top:5px}.status span:last-child{color:#6a9ab9;font-weight:600}.bottomgap{height:66px;background:#edf1f5}.duplicate{height:39px;padding:9px 10px;background:#fff}.duplicate-btn{background:#d9ebf4;border-radius:4px;text-align:center;font-weight:700;font-size:7px;color:#6e9ab7;padding:8px}.tabs{height:53px;background:#fff;border-top:1px solid #e7edf2;display:flex;justify-content:space-around;align-items:center;color:#79a0b4;font-size:6.5px}.tab{text-align:center}.tab i{font-style:normal;display:block;font-size:17px;margin-bottom:3px}.tab.active{color:#2790bf}.tab.center i{border-radius:50%;background:#2790bf;color:#fff;width:31px;height:31px;line-height:31px;font-size:19px;margin:auto auto 2px}';
const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=262,initial-scale=1"><style>'+CSS+'</style></head><body><div id="app">'
+'<div class="phone"><span>11:21 | 0,0KB/d ● ▪</span><span>▂ ▅ ▪ ◧</span></div><div class="nav"><span class="back">‹</span><span class="nav-title">Detail taruhan</span><span class="nav-right">♧ ⋮</span></div><div class="ticket"><div class="summary">'
+'<div class="stamp">'+esc(data.created_at||'')+' <span class="utc">UTC</span></div><div><span class="name">'+esc(data.category||'Akumulator')+'</span><span class="nr">№ '+esc(data.ticket_id||'—')+'</span></div><div class="overview"><div class="overview-top"><span class="left"><span class="tile">▦</span>Jumlah event: '+n+'</span><span>'+esc(data.completed??0)+' dari '+n+' diselesaikan</span></div>'
+'<div class="overview-line"><span class="label">Odd:</span><strong>'+esc(combined)+'</strong></div><div class="overview-line"><span class="label">Taruhan:</span><strong>'+esc(data.stake??'—')+'</strong></div><div class="overview-line"><span class="label">Potensi kemenangan:</span><strong>'+esc(data.potential_win??'—')+'</strong></div><div class="overview-line"><span class="label">Status:</span><strong class="accept"><span class="check">✓</span>'+esc(data.status||'—')+'</strong></div></div></div>'
+data.legs.map(leg).join('')+'</div><div class="bottomgap"></div><div class="duplicate"><div class="duplicate-btn">DUPLIKASIKAN SLIP TARUHAN</div></div><div class="tabs"><div class="tab"><i>♨</i>Populer</div><div class="tab"><i>★</i>Favorit</div><div class="tab center active"><i>▣</i>Slip</div><div class="tab"><i>◷</i>Riwayat</div><div class="tab"><i>☷</i>Menu</div></div></div></body></html>';
fs.mkdirSync(path.dirname(output),{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:262,height:700},deviceScaleFactor:1080/262});
 await page.setContent(html,{waitUntil:'load',timeout:30000});
 await page.evaluate(()=>document.fonts.ready);
 const element=page.locator('#app');
 await element.screenshot({path:output,type:'png',animations:'disabled'});
 const dims=await element.evaluate(e=>({w:e.clientWidth,h:e.scrollHeight}));
 console.log('ACCUMULATOR_RENDER_OK',JSON.stringify({matches:n,width:Math.round(dims.w*1080/262),height:Math.round(dims.h*1080/262),logos_resolved:[...logos.values()].filter(Boolean).length,output}));
} finally { await browser.close(); }
