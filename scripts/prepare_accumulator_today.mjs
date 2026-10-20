#!/usr/bin/env node
/**
 * Prépare un combiné de DIAGNOSTIC depuis data.json, sans inventer de pari.
 * Tous les matchs du jour sont inclus, sans préférence Simple/Pro/VIP.
 * Le test reste distinct de la future sélection éditoriale de production.
 */
import fs from 'node:fs';
import path from 'node:path';

const mode=process.env.ACCUMULATOR_MODE==='production'?'production':'test';
const now=new Date();
const day = process.env.ACCUMULATOR_TEST_DATE || now.toISOString().slice(0,10);
const MAX_PROD=Math.min(14,Math.max(4,Number(process.env.ACCUMULATOR_MAX_MATCHES||12)));
const MIN_PROD=4;
if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error('Date UTC invalide (YYYY-MM-DD)');
const sourcePath=process.env.ACCUMULATOR_SOURCE||'data.json';
const dest=process.env.ACCUMULATOR_INPUT||'telegram_out/accumulator_today.json';
const reportPath=process.env.ACCUMULATOR_DATA_REPORT||'telegram_out/accumulator_data_report.json';
const raw=JSON.parse(fs.readFileSync(sourcePath,'utf-8'));
const items=Array.isArray(raw.matches)?raw.matches:[];
const allToday=items.filter(m=>String(m?.event_date||m?.date||'').slice(0,10)===day);
let selected=allToday;
let videoIds=new Set();
if(mode==='production'){
 const ledgerPath=process.env.ACCUMULATOR_VIDEO_MANIFEST||'telegram_out/video_used_matches.json';
 if(!fs.existsSync(ledgerPath))throw Error('Registre des matchs vidéos requis, aucun combiné sans vidéo vérifiée');
 const ledger=JSON.parse(fs.readFileSync(ledgerPath,'utf8'));
 if(ledger.date!==day||ledger.kind!=='shorts_video_coupon'||!Array.isArray(ledger.published_video_ids))
   throw Error('Registre vidéo incorrect ou daté');
 videoIds=new Set(ledger.published_video_ids);
 if(videoIds.size===0){console.log('ACCUMULATOR_SKIP_NO_PUBLISHED_VIDEO',day);process.exit(3)}

 if(raw.source!=='bsd'||raw.model_version!=='bsd-v2-isolated')throw Error('Flux BSD V2 non vérifié');
 const generated=new Date(raw.generated_at||'');
 if(!Number.isFinite(generated.getTime())||generated>now||now-generated>24*3600000)throw Error('Flux BSD V2 récent requis (moins de 24 heures)');
 const valid=allToday.filter(m=>{
  if(videoIds.has(String(m.id||m.source_event_id||'')))return false;
  const p=m.prediction||{},odd=Number(p.odds),kick=Date.parse(m.event_date||'');
  return Number.isFinite(kick)&&kick>now.getTime()+30*60000
    && !m.is_finished && !['finished','cancelled','postponed','live'].includes(String(m.status||'').toLowerCase())
    && p.recommendation_eligible!==false && Boolean(p.selection_key)
    && Number.isFinite(odd)&&odd>1.01&&odd<100 && m.home_team&&m.away_team
    && ['vip','pro','simple'].includes(String(m.category||'').toLowerCase());
 });
 const weight={vip:3,pro:2,simple:1};
 valid.sort((a,b)=>
   (weight[String(b.category).toLowerCase()]-weight[String(a.category).toLowerCase()])*100
   +(b.prediction.odds_source==='mrxpronos_model'?-20:0)
   -(a.prediction.odds_source==='mrxpronos_model'?-20:0)
   +(Number(b.prediction.confidence||0)-Number(a.prediction.confidence||0))
   ||String(a.event_date).localeCompare(String(b.event_date)));
 selected=valid.slice(0,MAX_PROD);
}

if(mode==='production'&&selected.length<MIN_PROD){
 console.log('ACCUMULATOR_PRODUCTION_NO_DUE_MATCHES',JSON.stringify({day,available:allToday.length,used_in_video:videoIds.size,remaining_eligible:selected.length,minimum_required:MIN_PROD}));
 process.exit(3);
}
if (!selected.length) throw new Error('Aucun match pour '+day+' dans '+sourcePath+' (échec fermé, aucune donnée fictive)');
const ids=new Set();
const errors=[];
const mapped=selected.map((m,index)=>{
  const id=String(m.id??m.source_event_id??'').trim();
  const home=String(m.home_team||'').trim(),away=String(m.away_team||'').trim();
  const pred=m.prediction||{};
  const odds=Number(pred.odds);
  const event_date=String(m.event_date||'');
  const category=String(m.category||'').toLowerCase();
  if(!id||ids.has(id))errors.push(index+': identifiant manquant ou doublon');
  ids.add(id);
  if(!home||!away||home===away) errors.push(index+': noms d’équipes manquants ou identiques');
  if(!event_date.startsWith(day)) errors.push(index+': date incohérente');
  if(!Number.isFinite(Date.parse(event_date))) errors.push(index+': horaire invalide');
  if(!String(m.league||m.league_name||'').trim()) errors.push(index+': championnat absent');
  if(!Number.isFinite(odds)||odds<=1) errors.push(index+': cote absente ou invalide');
  if(!(pred.selection_key||pred.type||pred.label)) errors.push(index+': pronostic absent');
  const state='Accepté'; // Sélection retenue par Mr XPRONOS, NON un ticket enregistré chez un bookmaker
  return {
    id,home_team:home,away_team:away,
    event_date,
    league:m.league||m.league_name,
    home_logo:m.home_logo||m.home_team_logo||'',
    away_logo:m.away_logo||m.away_team_logo||'',
    category,
    prediction:{
      selection_key:pred.selection_key||'',
      label:pred.label||pred.type||'Pronostic',
      odds:odds,
      odds_source:pred.odds_source||''
    },
    odds:odds,
    status:state
  };
});
if(errors.length)throw new Error('Données du jour invalides : '+errors.join('; '));
mapped.sort((a,b)=>a.event_date.localeCompare(b.event_date)||a.home_team.localeCompare(b.home_team));
const estimatedCount=mapped.filter(m=>m.prediction.odds_source==='mrxpronos_model').length;
const combinedOdds=mapped.reduce((acc,m)=>acc*m.odds,1);
const displayedOdds=combinedOdds.toFixed(3);
const stake=50000;
const potentialGain=Math.round(Number(displayedOdds)*stake);
const money=n=>Math.round(n).toLocaleString('fr-FR')+' F CFA';
const doc={
 date:day,
 created_at:raw.generated_at||new Date().toISOString(),
 category:'Combiné',
 ticket_id:'MRXP-'+day.replaceAll('-',''),  // référence de simulation, jamais une référence bookmaker
 combined_odds:displayedOdds,
 combined_odds_estimated:estimatedCount>0,
 stake:money(stake),
 potential_win:money(potentialGain),
 stake_is_simulated:true,
 accepted_selection:true,
 completed:0,
 status:'Accepté',
 demo:true,
 legs:mapped,
};
const summary={
 day,mode,source:sourcePath,source_generated_at:raw.generated_at||null,
 available_today:allToday.length,used_in_video:videoIds.size,included:mapped.length,
 by_category:Object.fromEntries(['simple','pro','vip'].map(c=>[c,mapped.filter(m=>m.category===c).length])),
 estimated_odds:estimatedCount,bookmaker_or_consensus_odds:mapped.length-estimatedCount,
 home_logos_provided:mapped.filter(m=>m.home_logo).length,
 away_logos_provided:mapped.filter(m=>m.away_logo).length,
 combined_odds:doc.combined_odds,stake_fcfa:stake,potential_gain_fcfa:potentialGain,
 match_ids:mapped.map(m=>m.id)
};
fs.mkdirSync(path.dirname(dest),{recursive:true});
fs.mkdirSync(path.dirname(reportPath),{recursive:true});
fs.writeFileSync(dest,JSON.stringify(doc,null,2));
fs.writeFileSync(reportPath,JSON.stringify(summary,null,2));
console.log('ACCUMULATOR_TODAY_DATA_OK',JSON.stringify(summary));
