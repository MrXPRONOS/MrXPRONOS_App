// Read-only supplier contract probe. Never posts odds or predictions.
const c=new AbortController();setTimeout(()=>c.abort(),20000).unref();
async function check(label,url){try{const resp=await fetch(url,{signal:c.signal,headers:{"Accept":"application/json","User-Agent":"MrXPRONOS-Live-Audit/1.0"}});const json=resp.ok?await resp.json().catch(()=>null):null;
const arr=json?.matches||json?.fixtures||json?.results||json?.events||[];
const small=(Array.isArray(arr)?arr:[]).slice(0,5).map(m=>({id:m.id||m.match_id,name:(typeof m.home==="string"?m.home:m.home?.name)+" - "+(typeof m.away==="string"?m.away:m.away?.name),status:m.status,slug:m.slug,minute:m.live_minute,keys:Object.keys(m).slice(0,20)}));
console.log("PROBE",JSON.stringify({label,status:resp.status,content_type:resp.headers.get("content-type"),count:Array.isArray(arr)?arr.length:null,rootKeys:Object.keys(json||{}).slice(0,22),small}).slice(0,9500));
return json}catch(e){console.log("PROBE",JSON.stringify({label,error:e?.name||"unknown"}));return null}}
const today=new Date().toISOString().slice(0,10);
const sport=await check("sportscore_live","https://sportscore.com/api/v1/fixtures/?sport=football&date="+today+"&status=live&limit=200");
const events=sport?.matches||sport?.fixtures||sport?.results||[];
const first=Array.isArray(events)?events.find(e=>e?.slug||e?.match_slug):null;
if(first){
 const slug=first.slug||first.match_slug;
 const j=await check("sportscore_detail","https://sportscore.com/api/v1/match/?sport=football&slug="+encodeURIComponent(slug));
 if(j) console.log("DETAIL_SHAPE",JSON.stringify({keys:Object.keys(j),matchKeys:Object.keys(j.match||j.data?.match||{}),statsSample:JSON.stringify(j.match?.statistics||j.match?.stats||j.data?.match?.statistics||j.statistics||j.stats||null).slice(0,1700)}));
}
await check("espn_recent","https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates="+today.replace(/-/g,"")+"&limit=500");
