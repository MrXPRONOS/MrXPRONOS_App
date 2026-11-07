// Shared admin snapshot labeling: separate successful data reads from real-time presence.
export function adminSnapshotLabel(source,now=new Date(),{intervalSeconds=null,windowText=""}={}){
 const date=now instanceof Date?now:new Date(now);
 const time=Number.isFinite(date.getTime())?date.toLocaleTimeString("fr-FR",{timeZone:"UTC"}):"heure inconnue";
 return "Instantané "+String(source||"")+" · "+time+" UTC"+
   (Number(intervalSeconds)>0?" · rafraîchissement "+intervalSeconds+" s":" · à la demande")+
   (windowText?" · "+windowText:"");
}
export function freshnessClass(lastUpdate,maxAgeMinutes,now=Date.now()){
 const millis=Date.parse(String(lastUpdate||""));
 if(!Number.isFinite(millis))return "unknown";
 const age=(now-millis)/60000;
 if(age<0)return "unknown";
 return age>maxAgeMinutes?"late":"good";
}
