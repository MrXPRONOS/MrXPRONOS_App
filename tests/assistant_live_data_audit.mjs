const site='https://mrxpronos.github.io/MrXPRONOS_App/';
for(const name of ['data.json','bonus.json','articles.json','conseils.json']){
 try{
  const response=await fetch(site+name,{signal:AbortSignal.timeout(20000)});
  const json=await response.json();
  const first=Array.isArray(json)?json[0]:Object.values(json).find(x=>Array.isArray(x));
  const matches=Array.isArray(json.matches)?json.matches:Array.isArray(json)?json:Array.isArray(first)?first:[];
  const preview=matches.slice(0,3).map(x=>x&&typeof x==='object'?Object.fromEntries(Object.entries(x).filter(([k])=>/date|team|match|category|event|home|away|bonus|name|title|active/i.test(k)).slice(0,9)):x);
  console.log('REAL_DATA',JSON.stringify({name,status:response.status,entries:matches.length,rootKeys:Object.keys(json).slice(0,25),preview}).slice(0,3600));
 }catch(e){console.log('REAL_DATA',JSON.stringify({name,error:String(e)}))}
}