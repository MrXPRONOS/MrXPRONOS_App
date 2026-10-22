// Lightweight live latency benchmark. Read-only; sequential requests.
const BASE=process.env.CINE_RADAR_URL||"https://cinecanaux-bot.cinecanaux-xpronos.workers.dev";
const RUNS=Math.max(4,Math.min(20,Number(process.env.BENCH_SAMPLES)||10));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function percentile(a,p){const v=a.slice().sort((x,y)=>x-y);return v[Math.min(v.length-1,Math.max(0,Math.ceil((p/100)*v.length)-1))];}
async function sample(path){
 const begin=performance.now();
 const controller=new AbortController(),kill=setTimeout(()=>controller.abort(),9000);
 try{
  const response=await fetch(BASE+path,{headers:{"accept":"application/json, text/html;q=0.9"},cache:"no-store",signal:controller.signal});
  await response.arrayBuffer();
  return {ms:Math.round((performance.now()-begin)*10)/10,status:response.status};
 }finally{clearTimeout(kill);}
}
async function main(){
 const listing=await fetch(BASE+"/api/catalog",{cache:"no-store"}).then(r=>r.json());
 const first=Number(listing.channels?.[0]?.id);
 if(!Number.isSafeInteger(first)||first<=0)throw new Error("No public channel available for read-only preview benchmark");
 const paths=["/health","/app","/api/catalog","/api/catalog?type=films","/api/catalog?type=series","/api/catalog?type=animes","/api/channel-preview?id="+first];
 const report={version:process.env.BENCH_VERSION||"before",run_at:new Date().toISOString(),samples:RUNS,location:"GitHub Actions runner (not end-user phone)",rows:[]};
 for(const path of paths){
  const observations=[];
  for(let j=0;j<RUNS;j++){
   const result=await sample(path);
   if(result.status!==200)throw new Error(path+" HTTP "+result.status);
   observations.push(result.ms);
   await pause(50);
  }
  const row={path,p50_ms:percentile(observations,50),p90_ms:percentile(observations,90),max_ms:Math.max(...observations),min_ms:Math.min(...observations)};
  report.rows.push(row);
  console.log("LATENCY "+JSON.stringify(row));
 }
 console.log("REPORT "+JSON.stringify(report));
}
await main();
