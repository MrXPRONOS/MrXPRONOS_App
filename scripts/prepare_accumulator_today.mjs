#!/usr/bin/env node
/**
 * Prépare un combiné de DIAGNOSTIC depuis data.json, sans inventer de pari.
 * Tous les matchs du jour sont inclus, sans préférence Simple/Pro/VIP.
 * Le test reste distinct de la future sélection éditoriale de production.
 */
import fs from 'node:fs';
import path from 'node:path';

const day = process.env.ACCUMULATOR_TEST_DATE || new Date().toISOString().slice(0,10);
if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error('Date UTC invalide (YYYY-MM-DD)');
const sourcePath=process.env.ACCUMULATOR_SOURCE||'data.json';
const dest=process.env.ACCUMULATOR_INPUT||'telegram_out/accumulator_today.json';
const reportPath=process.env.ACCUMULATOR_DATA_REPORT||'telegram_out/accumulator_data_report.json';
const raw=JSON.parse(fs.readFileSync(sourcePath,'utf-8'));
const items=Array.isArray(raw.matches)?raw.matches:[];
const selected=items.filter(m=>String(m?.event_date||m?.date||'').slice(0,10)===day);
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
  const state=(m.is_finished===true&&m.verified_prediction===true)?'Terminé':'Prévision';
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
const doc={
 date:day,
 created_at:raw.generated_at||new Date().toISOString(),
 category:'Combiné',
 ticket_id:'MRXP-'+day.replaceAll('-',''),  // référence de simulation, jamais une référence bookmaker
 combined_odds:combinedOdds.toFixed(3),
 combined_odds_estimated:estimatedCount>0,
 stake:'—',
 potential_win:'—',
 completed:mapped.filter(m=>m.status==='Terminé').length,
 status:'Prévision',
 demo:true,
 legs:mapped,
};
const summary={
 day,source:sourcePath,source_generated_at:raw.generated_at||null,
 available_today:selected.length,included:mapped.length,
 by_category:Object.fromEntries(['simple','pro','vip'].map(c=>[c,mapped.filter(m=>m.category===c).length])),
 estimated_odds:estimatedCount,bookmaker_or_consensus_odds:mapped.length-estimatedCount,
 home_logos_provided:mapped.filter(m=>m.home_logo).length,
 away_logos_provided:mapped.filter(m=>m.away_logo).length,
 combined_odds:doc.combined_odds,
 match_ids:mapped.map(m=>m.id)
};
fs.mkdirSync(path.dirname(dest),{recursive:true});
fs.mkdirSync(path.dirname(reportPath),{recursive:true});
fs.writeFileSync(dest,JSON.stringify(doc,null,2));
fs.writeFileSync(reportPath,JSON.stringify(summary,null,2));
console.log('ACCUMULATOR_TODAY_DATA_OK',JSON.stringify(summary));
