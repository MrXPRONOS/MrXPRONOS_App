const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const script = fs.readFileSync(path.resolve(__dirname, "../assets/js/main.js"), "utf8")
  .replace(/^import \{ safeCmsUrl, isSafeCmsUrl \} from "\.\/cms-url-guard\.mjs";\r?\n/m, "");
const today = new Date().toISOString().slice(0,10);
const kickoff = today + "T16:00:00Z";

function pick(id,category,overrides={}) {
  return {
    id:"bsd:"+id,source:"bsd",event_date:kickoff,date:today,
    status:"notstarted",recommendation_eligible:true,
    is_finished:false,combo_only:false,category,
    home_team:"Equipe "+id,away_team:"Adversaire",league:"Test",
    final_score:84,prediction:{selection_key:"OVER_15",confidence:84},
    ...overrides
  };
}
function fixture(matches,search="") {
  const url={hostname:"localhost",search,href:"http://localhost/pronos.html"+search};
  const cats=["pro","vip"];
  const tabs=cats.map(cat=>({
    dataset:{cat},classList:{toggle(){}},setAttribute(k,v){this[k]=v;},
    addEventListener(k,cb){this[k]=cb;},tabIndex:-1,
  }));
  const counts=Object.fromEntries(cats.map(cat=>["count-"+cat,{textContent:""}]));
  const panel={setAttribute(){},innerHTML:"",hidden:false};
  const doc={
    querySelector(){return null;},
    querySelectorAll(sel){return sel===".pronostic-category-tabs .tab-btn"?tabs:[];},
    getElementById(id){return counts[id]||null;},
    addEventListener(){},
  };
  const win={location:url,history:{replaceState(){}},addEventListener(){},
    mockPanel:panel,testMatches:matches,renderedIds:[]};
  const context=vm.createContext({document:doc,window:win,location:url,
    URL,URLSearchParams,console,setTimeout,clearTimeout,Date});
  vm.runInContext(script,context,{filename:"main.js"});
  vm.runInContext(
    'DOM.matches=window.mockPanel; allData={matches:window.testMatches}; currentCategory=readInitialCategory(); renderMatches=function(ms){window.renderedIds=ms.map(m=>m.id);}; filterAndDisplay();',
    context);
  return {
    tabs,counts,window:win,
    get selected(){return vm.runInContext("currentCategory",context);},
    refresh(rows){win.testMatches=rows;vm.runInContext("allData={matches:window.testMatches}; filterAndDisplay();",context);},
    click(cat){vm.runInContext("setupPronosticPageListeners()",context);
      tabs.find(t=>t.dataset.cat===cat).click();}
  };
}
test("Le site présente uniquement deux onglets Pro et VIP",()=>{
  const html=fs.readFileSync(path.resolve(__dirname,"../pronos.html"),"utf8");
  assert.deepEqual([...html.matchAll(/data-cat="([^"]+)"/g)].map(x=>x[1]),["pro","vip"]);
  assert.doesNotMatch(html,/Ultra Safe|Cotes 1,50\+|mx-market-range-section/);
});
test("Pro par défaut, seuls les vrais matchs Pro >=79 sont visibles",()=>{
  const b=fixture([pick(1,"simple"),pick(2,"pro"),pick(3,"pro",{prediction:{confidence:78.9}}),pick(4,"vip")]);
  assert.equal(b.selected,"pro");
  assert.equal(b.counts["count-pro"].textContent,"1");
  assert.equal(b.counts["count-vip"].textContent,"1");
  assert.deepEqual([...b.window.renderedIds],["bsd:2"]);
});
test("VIP est affiché par défaut lorsque Pro est vide",()=>{
  const b=fixture([pick(1,"simple"),pick(2,"vip")]);
  assert.equal(b.selected,"vip");
  assert.deepEqual([...b.window.renderedIds],["bsd:2"]);
});
test("Lien direct VIP respecte le choix de l'utilisateur",()=>{
  const b=fixture([pick(1,"pro"),pick(2,"vip")],"?cat=vip");
  assert.equal(b.selected,"vip");
  assert.deepEqual([...b.window.renderedIds],["bsd:2"]);
});
test("Anciens liens vers Ultra Safe et Safe reviennent aux onglets autorisés",()=>{
  const b=fixture([pick(1,"pro"),pick(2,"vip")],"?cat=safe");
  assert.equal(b.selected,"pro");
  assert.deepEqual([...b.window.renderedIds],["bsd:1"]);
});
test("Choisir VIP manuellement survit au rechargement des données",()=>{
  const b=fixture([pick(1,"pro"),pick(2,"vip")]);
  b.click("vip");
  b.refresh([pick(1,"pro"),pick(2,"vip"),pick(3,"vip")]);
  assert.equal(b.selected,"vip");
  assert.equal(b.tabs[1]["aria-selected"],"true");
  assert.deepEqual([...b.window.renderedIds],["bsd:2","bsd:3"]);
});
test("Simple, combinés, matchs d'une autre date et confiance trop basse sont exclus",()=>{
  const b=fixture([
    pick(1,"simple"),pick(2,"pro",{combo_only:true}),
    pick(3,"pro",{date:"2020-01-01"}),pick(4,"pro",{recommendation_eligible:false}),
    pick(5,"pro",{prediction:{confidence:78.999}}),pick(6,"pro",{prediction:{confidence:79}})
  ]);
  assert.equal(b.counts["count-pro"].textContent,"1");
  assert.deepEqual([...b.window.renderedIds],["bsd:6"]);
});
