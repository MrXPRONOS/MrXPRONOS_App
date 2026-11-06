"use strict";
const $ = id => document.getElementById(id);
let selectedId = null;
let cachedFixtures = [];
let currentCompetition = "";
const num = (v, digits=1) => new Intl.NumberFormat("fr-FR",{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(v);
const pct = v => `${num(v*100,2)} %`;
const safe = s => String(s ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
const when = iso => new Date(iso).toLocaleString("fr-FR",{dateStyle:"medium",timeStyle:"short"});
function notice(message,type="info"){$("notice").innerHTML=`<div class="alert ${type}">${safe(message)}</div>`;window.scrollTo({top:0,behavior:"smooth"});}
async function api(path,{method="GET",body=null,multipart=false}={}){
  let opts={method,headers:{}};
  const token=($('adminToken')?.value||'').trim();
  if(token)opts.headers['Authorization']=`Bearer ${token}`;
  if(body!==null){opts.body=multipart?body:JSON.stringify(body);if(!multipart)opts.headers["Content-Type"]="application/json";}
  let res=await fetch(path,opts), json;
  try{json=await res.json();}catch{throw new Error(`Réponse serveur invalide : HTTP ${res.status}`);}
  if(!res.ok){let d=json.detail??json;throw new Error(typeof d==="string"?d:JSON.stringify(d));}
  return json;
}
async function busy(id,task){const el=$(id),old=el.textContent;el.disabled=true;el.textContent="Calcul en cours...";try{await task();}catch(err){notice(err.message||String(err),"error");}finally{el.disabled=false;el.textContent=old;if(id==="predictBtn")el.disabled=!selectedId;}}
async function reload(){
  let [health,leagues]=await Promise.all([api("/api/health"),api("/api/competitions")]);
  $("status").textContent=(health.public_mode?'🔒 Serveur sécurisé · ':'')+(health.api_key_configured?'API configurée':'Mode CSV ou démo');
  let old=$("competition").value;
  $("competition").innerHTML=`<option value="">Choisir une compétition</option>`+leagues.map(l=>`<option value="${safe(l.competition)}">${safe(l.competition)} (${l.finished} terminés / ${l.scheduled} prévus)</option>`).join("");
  if(leagues.some(l=>l.competition===old))$("competition").value=old;
  else if(leagues.length)$("competition").value=leagues[0].competition;
  await loadCompetition();
}
async function loadCompetition(){
  currentCompetition=$("competition").value;
  selectedId=null;$("predictBtn").disabled=true;$("selectedMatch").textContent="Aucun match sélectionné.";
  if(!currentCompetition){$("fixtures").textContent="Aucune compétition importée.";$("xiStatus").textContent="Choisir une compétition.";return;}
  await refreshXi();
  const [fixtures,teams]=await Promise.all([
    api("/api/matches?competition="+encodeURIComponent(currentCompetition)),
    api("/api/teams?competition="+encodeURIComponent(currentCompetition))]);
  cachedFixtures=fixtures;
  const optionHtml=`<option value="">Choisir une équipe</option>`+teams.map(t=>`<option value="${safe(t.team_id)}">${safe(t.team_name)} (${t.played})</option>`).join("");
  $("homeTeam").innerHTML=optionHtml;$("awayTeam").innerHTML=optionHtml;
  $("fixtureCount").textContent=`${fixtures.length} match(s)`;
  if(!fixtures.length){$("fixtures").innerHTML="<p class='help'>Aucune rencontre future. Tu peux en créer une à droite.</p>";return;}
  $("fixtures").innerHTML=fixtures.map(m=>`<button class="fixture" data-match="${safe(m.id)}"><span><strong>${safe(m.home_name)} – ${safe(m.away_name)}</strong><small>${safe(when(m.kickoff))}</small></span><span class="chip ${m.source==='demo'?'demo':''}">${m.source==='demo'?'FICTIF':'À venir'}</span></button>`).join("");
  $("fixtures").querySelectorAll("[data-match]").forEach(el=>el.addEventListener("click",()=>selectMatch(el.dataset.match)));
}
function selectMatch(id){
  const match=cachedFixtures.find(m=>m.id===id);if(!match)return;
  selectedId=id;$("predictBtn").disabled=false;
  $("selectedMatch").innerHTML=`Match sélectionné : <strong>${safe(match.home_name)} – ${safe(match.away_name)}</strong> · ${safe(when(match.kickoff))}${match.source==='demo'?' · <strong>DÉMONSTRATION FICTIVE</strong>':''}${match.neutral_venue?' · terrain neutre':''}`;
  document.querySelectorAll(".fixture").forEach(el=>el.classList.toggle("active",el.dataset.match===id));
}
function opts(forBacktest=false){return {
  xi:($('xiMode').value==='manual' || forBacktest)?Number($("xi").value):null,
  min_games:Number($("minGames").value),min_team:Number($("minTeam").value),
  regularization:Number($("reg").value)};
}
async function refreshXi(){
  if(!currentCompetition)return;
  const r=await api('/api/xi/calibration?competition='+encodeURIComponent(currentCompetition));
  $('xiStatus').textContent=r.available
    ?`ξ optimisé : ${num(r.calibration.selected_xi,4)} · ${r.calibration.n_scored} matchs de validation · ${r.calibration.n_folds} blocs · données : ${r.calibration.data_source.join(', ')}`
    :'Aucune valeur ξ optimisée. En mode automatique, le coefficient historique 0,0065 sera utilisé avec un avertissement.';
}

function renderResult(d){
  const best=d.top_scores[0];
  const bars=d.top_scores.map((s,i)=>`<div class="probrow"><span class="score">${safe(s.score)}</span><div class="track"><div style="width:${Math.min(100,s.probability*100/Math.max(.001,d.top_scores[0].probability))}%"></div></div><span class="prob">${pct(s.probability)}</span></div>`).join("");
  $("result").innerHTML=`${d.mode.startsWith('DEMO')?'<div class="alert warning">Attention : clubs, résultats et prédiction entièrement fictifs. Ne pas utiliser pour miser.</div>':''}
  <div class="results-hero"><div><div class="team">${safe(d.home_team)}</div><div class="sub">Domicile</div></div><div><div class="score">${safe(best.score)}</div><div class="sub">Score le plus probable · ${pct(best.probability)}</div></div><div><div class="team">${safe(d.away_team)}</div><div class="sub">Extérieur</div></div></div>
  <div class="stats"><div class="stat"><div class="label">Buts attendus domicile</div><div class="number">${num(d.expected_home_goals,3)}</div></div><div class="stat"><div class="label">Buts attendus extérieur</div><div class="number">${num(d.expected_away_goals,3)}</div></div><div class="stat"><div class="label">Correction ρ</div><div class="number">${num(d.rho,4)}</div></div></div>
  <h4>Top 5 des scores</h4>${bars}<h4>Probabilités 1 N 2</h4><div class="stats"><div class="stat"><div class="label">Victoire domicile</div><div class="number">${pct(d.one_x_two.home)}</div></div><div class="stat"><div class="label">Match nul</div><div class="number">${pct(d.one_x_two.draw)}</div></div><div class="stat"><div class="label">Victoire extérieur</div><div class="number">${pct(d.one_x_two.away)}</div></div></div>
  ${d.data_quality?.stale_results?'<div class="alert warning">Résultats historiques non actualisés depuis plus de 21 jours : vérifier la fraîcheur de la source avant tout usage réel.</div>':''}
  <div class="fine">Dernier résultat du championnat : ${safe(d.data_quality?.last_finished_game||'inconnu')} · provenance : ${safe(Object.entries(d.data_quality?.result_provenances||{}).map(([name,count])=>name+'='+count).join(', '))}.</div>
  <div class="fine">Terrain : ${d.neutral_venue?'neutre (avantage domicile désactivé)':'domicile'}</div>
  <div class="fine">Paramètre ξ : ${num(d.xi_per_half_week,4)} / demi-semaine · Origine : ${safe(d.xi_source)}${d.xi_calibration?` · Validé sur ${d.xi_calibration.validation_matches} matchs · Historique mis à jour depuis la calibration : ${d.xi_calibration.stale_data?'oui':'non'}`:''}.</div>
  ${d.xi_source==='historical_default_not_optimized'?'<div class="alert warning">ξ=0,0065 est une valeur historique non optimisée pour cette compétition.</div>':''}
  <div class="fine">Analyse : ${safe(when(d.generated_at))} · ${d.training.matches} matchs historiques · ${d.training.teams} équipes · historique allant du ${safe(d.training.first_game.slice(0,10))} au ${safe(d.training.last_game.slice(0,10))}. Probabilité en dehors de la grille calculée : ${pct(d.probability_uncovered)}. Aucune garantie de score.</div>`;
  $("resultSection").hidden=false;$("resultSection").scrollIntoView({behavior:"smooth",block:"start"});
}
function renderBacktest(r){
  const details=r.detailed.slice(0,200).map(d=>`<tr><td>${safe(d.match)}</td><td>${safe(d.actual)}</td><td>${safe(d.best)}</td><td>${d.top1_hit?'✓':'–'}</td><td>${num(d.dc_log_loss,3)}</td></tr>`).join("");
  $("backtest").innerHTML=`<div class="stats"><div class="stat"><div class="label">Tests valides</div><div class="number">${r.n_evaluated}</div></div><div class="stat"><div class="label">Score exact Top 1</div><div class="number">${pct(r.top1_hit_rate)}</div></div><div class="stat"><div class="label">Score exact Top 3</div><div class="number">${pct(r.top3_hit_rate)}</div></div></div><div class="fine">Log loss Dixon-Coles : ${num(r.mean_dc_log_loss,3)} · Poisson entraîné indépendamment : ${num(r.mean_poisson_independent_log_loss,3)} · Brier 1N2 : ${num(r.mean_one_x_two_brier,3)} · ${r.n_folds} mois/blocs. Prévisions vérifiées sur des matchs passés non vus lors de leur entraînement. ${r.n_skipped} tests écartés.</div><div class="tablewrap"><table><thead><tr><th>Match</th><th>Réel</th><th>Prévu</th><th>Correct</th><th>Log loss</th></tr></thead><tbody>${details}</tbody></table></div>`;
}
async function loadHistory(){
  let rows=await api("/api/predictions");
  const outcome = x => {
    if(x.correct!==null)return (x.correct?'✓':'✕')+' · '+safe(x.result_provenance||'provenance inconnue');
    if(x.prediction.source==='manual' && new Date(x.prediction.kickoff)<=new Date()){
      return `<div class="manual-score"><input class="final-home" type="number" min="0" max="99" placeholder="D" aria-label="Buts domicile"/><span>–</span><input class="final-away" type="number" min="0" max="99" placeholder="E" aria-label="Buts extérieur"/><button class="btn-ghost" data-final-id="${safe(x.prediction.match_id)}">Saisir</button></div>`;
    }
    return '—';
  };
  $("history").innerHTML=rows.length?`<div class="tablewrap"><table><thead><tr><th>Date analyse</th><th>Match</th><th>Prédit</th><th>Prob.</th><th>Réel</th><th>Vérification</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${safe(when(x.created_at))}</td><td>${safe(x.prediction.home_team)} – ${safe(x.prediction.away_team)}</td><td>${safe(x.prediction.top_scores[0].score)}</td><td>${pct(x.prediction.top_scores[0].probability)}</td><td>${safe(x.actual_score??'En attente')}</td><td>${outcome(x)}</td></tr>`).join("")}</tbody></table></div>`:"<p class='help'>Aucune prédiction enregistrée.</p>";
  $("history").querySelectorAll("[data-final-id]").forEach(button=>button.addEventListener("click",async()=>{
    const row=button.closest('tr');
    const h=row.querySelector('.final-home').value;
    const a=row.querySelector('.final-away').value;
    if(h===''||a===''||!Number.isInteger(Number(h))||!Number.isInteger(Number(a))){notice('Indiquer les deux scores entiers.','error');return;}
    try{
      await api('/api/fixtures/manual/result',{method:'POST',body:{match_id:button.dataset.finalId,home_goals:Number(h),away_goals:Number(a)}});
      await loadHistory();notice('Score manuel enregistré. Ce résultat est déclaré, pas vérifié par une API.');
    }catch(err){notice(err.message,'error');}
  }));
}

document.addEventListener("DOMContentLoaded",()=>{
  $("xiMode").addEventListener("change",()=>{$("xi").disabled=$("xiMode").value!=="manual";});
  $("ofSyncBtn").addEventListener("click",()=>busy("ofSyncBtn",async()=>{
    const seasons=$("ofSeasons").value.split(",").map(x=>x.trim()).filter(Boolean);
    const r=await api('/api/sync-openfootball',{method:'POST',body:{seasons}});
    if(!r.all_successful)notice('Import OpenFootball partiel : '+JSON.stringify(r.seasons),'warning');
    else notice('Résultats réels importés : '+r.imported_or_updated+' lignes.','info');
    await reload();$("competition").value=r.competition;await loadCompetition();
  }));
  $("calibrateBtn").addEventListener("click",()=>busy("calibrateBtn",async()=>{
    if(!currentCompetition)throw Error('Sélectionner une compétition réelle.');
    const r=await api('/api/xi/calibrate',{method:'POST',body:{
      competition:currentCompetition,eval_start:$("xiStart").value,eval_end:$("xiEnd").value,
      block_months:Number($("xiBlock").value),min_games:400,min_team:5,
      min_scored:100,min_folds:3,regularization:0.15}});
    $("xiReport").textContent=`Valeur optimale ξ=${num(r.selected_xi,4)} · ${r.n_scored} scores réels sur ${r.n_folds} blocs · Log loss optimisée ${num(r.selected_mean_log_loss,4)} contre ${num(r.historical_mean_log_loss,4)} pour ξ=0,0065.`;
    await refreshXi();notice('Optimisation réelle terminée et enregistrée dans SQLite.');
  }));
  $("kickoff").value=new Date(Date.now()+86400000).toLocaleString("sv-SE").slice(0,16).replace(" ","T");
  $("competition").addEventListener("change",()=>busy("refreshBtn",loadCompetition));
  $("refreshBtn").addEventListener("click",()=>busy("refreshBtn",reload));
  $("syncBtn").addEventListener("click",()=>busy("syncBtn",async()=>{let seasons=$("apiSeasons").value.split(",").map(x=>Number(x.trim()));if(!seasons.length||seasons.some(x=>!Number.isInteger(x)))throw new Error("Saisons invalides.");let result=await api("/api/sync",{method:"POST",body:{code:$("apiCode").value.trim().toUpperCase(),seasons}});notice(result.all_successful?`Import API terminé : ${result.rows_imported_or_updated} matchs.`:`Import partiel : ${JSON.stringify(result.seasons)}`,result.all_successful?"info":"warning");await reload();$("competition").value=result.competition;await loadCompetition();}));
  $("importBtn").addEventListener("click",()=>busy("importBtn",async()=>{if(!$("csvFile").files.length)throw new Error("Sélectionne un CSV.");let form=new FormData();form.append("file",$("csvFile").files[0]);let code=encodeURIComponent($("csvLeague").value.trim());let d=await api(`/api/import-csv?default_competition=${code}`,{method:"POST",body:form,multipart:true});notice(`${d.imported_or_updated} matchs CSV importés.`,"info");await reload();$("competition").value=d.competitions[0];await loadCompetition();}));
  $("demoBtn").addEventListener("click",()=>busy("demoBtn",async()=>{let d=await api("/api/demo",{method:"POST"});await reload();$("competition").value=d.competition;await loadCompetition();selectMatch(d.example_match_id);notice("Démonstration chargée : tous les matchs sont fictifs.","warning");}));
  $("manualBtn").addEventListener("click",()=>busy("manualBtn",async()=>{if(!currentCompetition)throw new Error("Sélectionne un championnat.");let str=$("kickoff").value;let dt=new Date(str);if(!str||isNaN(dt))throw new Error("Date invalide.");let data={competition:currentCompetition,home_id:$("homeTeam").value,away_id:$("awayTeam").value,kickoff:dt.toISOString(),neutral_venue:$("neutralVenue").checked};let added=await api("/api/fixtures/manual",{method:"POST",body:data});await loadCompetition();selectMatch(added.id);notice("Rencontre future créée, tu peux lancer son analyse.");}));
  $("predictBtn").addEventListener("click",()=>busy("predictBtn",async()=>{if(!selectedId)throw new Error("Sélectionne un match.");let result=await api("/api/predict",{method:"POST",body:{match_id:selectedId,...opts()}});renderResult(result);await loadHistory();}));
  $("backtestBtn").addEventListener("click",()=>busy("backtestBtn",async()=>{if(!currentCompetition)throw new Error("Sélectionne une compétition.");let res=await api("/api/backtest",{method:"POST",body:{competition:currentCompetition,n_samples:Number($("samples").value),...opts()}});renderBacktest(res);}));
  $("historyBtn").addEventListener("click",()=>busy("historyBtn",loadHistory));
  $('adminToken').addEventListener('change',()=>reload().then(loadHistory).catch(e=>notice(e.message,'error')));
  reload().then(loadHistory).catch(e=>notice(e.message,"error"));
});
