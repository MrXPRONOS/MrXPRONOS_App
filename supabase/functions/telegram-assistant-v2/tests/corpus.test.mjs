import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {intentFor,analyzeClientIntent,contextualDestinations} from "../index.js";

const csv=readFileSync(new URL("./fixtures/1000_messages_clients.csv",import.meta.url),"utf8");
function parseCSVRow(line){
  const values=[];let i=0;
  while(i<line.length){
    if(line[i]!=='"')throw Error("Champ CSV non entre guillemets");
    i++;let value="";
    while(i<line.length){
      if(line[i]==='"'&&line[i+1]==='"'){value+='"';i+=2;continue;}
      if(line[i]==='"'){i++;break;}
      value+=line[i++];
    }
    values.push(value);
    if(line[i]===',')i++;
  }
  return values;
}
const all=csv.trimEnd().split(/\r?\n/).map(parseCSVRow);
const header=all.shift();
const index=Object.fromEntries(header.map((name,i)=>[name,i]));
const canonical=(value)=>value.normalize("NFD").replace(/[\u0300-\u036f]/g,"")
  .toLowerCase().replace(/[^\p{L}\p{N}]+/gu," ").trim();
test("exactement 1000 messages clients distincts avec identifiants uniques",()=>{
  assert.deepEqual(header,["id","intention","style","message_client","comportement_attendu"]);
  assert.equal(all.length,1000);
  assert.equal(new Set(all.map(v=>v[index.id])).size,1000);
  assert.equal(new Set(all.map(v=>canonical(v[index.message_client]))).size,1000);
  assert.ok(all.every(row=>row.length===5 && row.every(Boolean)));
});
test("50 intentions et 5 styles, soit 20 exemples par intention",()=>{
  const intents=new Map(),styles=new Map();
  for(const row of all){
    intents.set(row[index.intention],(intents.get(row[index.intention])||0)+1);
    styles.set(row[index.style],(styles.get(row[index.style])||0)+1);
  }
  assert.equal(intents.size,50);
  assert.equal(styles.size,5);
  assert.ok([...intents.values()].every(n=>n===20));
  assert.ok([...styles.values()].every(n=>n===200));
});
test("vérifie l'existence des fautes, SMS, vocaux et cas sensibles",()=>{
  for(const name of ["sms_abreviation","vocal_transcrit","orthographe_approximative","message_contextualise"]){
    assert.ok(all.some(x=>x[index.style]===name));
  }
  for(const intent of ["installer","canal","coupon_aujourdhui","inscription","vocal_confus","photo","mineur","perte_argent","securite"]){
    assert.ok(all.some(x=>x[index.intention]===intent),intent);
  }
});
test("les 1000 formulations passent dans le moteur de règles sans erreur",()=>{
  for(const row of all){
    const question=row[index.message_client];
    const intent=intentFor(question);
    const details=analyzeClientIntent(question);
    const destinations=contextualDestinations(question);
    assert.equal(typeof intent,"string");
    assert.equal(typeof details,"object");
    assert.ok(Array.isArray(destinations));
    assert.ok(destinations.length<=5);
  }
});
test("les questions mineur ne peuvent pas déclencher un lien bookmaker",()=>{
  for(const row of all.filter(r=>r[index.intention]==="mineur")){
    const question=row[index.message_client];
    const details=analyzeClientIntent(question);
    if(!details.minor)continue;
    const links=contextualDestinations(question);
    assert.ok(!links.some(url=>/reffpa|lb-aff|refpa3665|1wrbgb|bwredir|betpari-click/.test(url)));
  }
});
