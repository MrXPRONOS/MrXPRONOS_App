import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const script=path.resolve('scripts/prepare_accumulator_today.mjs');
function setup(total=6, excluded=['bsd:101','bsd:102']){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'mrxp-accumulator-'));
  const day=new Date(Date.now()+86400000).toISOString().slice(0,10);
  const fixtureDate=day+'T18:00:00Z';
  const matches=Array.from({length:total},(_,i)=>({
    source:'bsd',id:'bsd:'+(101+i),event_date:fixtureDate,date:day,
    home_team:'Home '+i,away_team:'Away '+i,
    league:'Competition',category:'pro',status:'notstarted',
    is_finished:false,recommendation_eligible:true,
    prediction:{selection_key:'1X',label:'1X',odds:1.4,confidence:83,
      odds_source:'bsd_consensus',recommendation_eligible:true}
  }));
  const source=path.join(dir,'data.json');
  const ledger=path.join(dir,'video.json');
  const output=path.join(dir,'accumulator.json');
  const report=path.join(dir,'report.json');
  fs.writeFileSync(source,JSON.stringify({source:'bsd',model_version:'bsd-v2-isolated',
    generated_at:new Date().toISOString(),matches}));
  if(excluded!==null)fs.writeFileSync(ledger,JSON.stringify({
    date:day,kind:'shorts_video_coupon',published_video_ids:excluded
  }));
  const env={...process.env,ACCUMULATOR_MODE:'production',ACCUMULATOR_TEST_DATE:day,
    ACCUMULATOR_SOURCE:source,ACCUMULATOR_VIDEO_MANIFEST:ledger,
    ACCUMULATOR_INPUT:output,ACCUMULATOR_DATA_REPORT:report};
  const result=spawnSync(process.execPath,[script],{env,encoding:'utf8'});
  return {dir,result,output,report};
}
test('Four remaining matches after video create one coupon, excluding all video IDs',()=>{
  const {result,output,report}=setup();
  assert.equal(result.status,0,result.stderr);
  const acc=JSON.parse(fs.readFileSync(output,'utf8'));
  const diagnostics=JSON.parse(fs.readFileSync(report,'utf8'));
  assert.equal(acc.legs.length,4);
  assert.equal(acc.status,'Accepté');
  assert.equal(acc.stake_is_simulated,true);
  assert.equal(diagnostics.used_in_video,2);
  assert.equal(diagnostics.included,4);
  assert.deepEqual(acc.legs.map(x=>x.id),['bsd:103','bsd:104','bsd:105','bsd:106']);
  assert.equal(Number(acc.combined_odds),(1.4**4).toFixed(3)*1);
  assert.equal(acc.potential_win.replace(/\D/g,''),String(Math.round(Number(acc.combined_odds)*50000)));
});
test('Three remaining matches means no accumulator publication',()=>{
  const {result,output}=setup(6,['bsd:101','bsd:102','bsd:103']);
  assert.equal(result.status,3,result.stderr);
  assert.equal(fs.existsSync(output),false);
});
test('No confirmed video publication blocks coupon',()=>{
  const {result,output}=setup(6,[]);
  assert.equal(result.status,3,result.stderr);
  assert.equal(fs.existsSync(output),false);
});
test('Missing video ledger fails closed',()=>{
  const {result,output}=setup(6,null);
  assert.notEqual(result.status,0);
  assert.equal(fs.existsSync(output),false);
});
