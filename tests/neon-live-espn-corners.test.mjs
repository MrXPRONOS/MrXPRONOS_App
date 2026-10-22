import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
const code=readFileSync("migration/free-stack/live/index.signals-safe.mjs","utf8");
execFileSync(process.execPath,["--check","migration/free-stack/live/index.signals-safe.mjs"],{stdio:"inherit"});
const snippets=[
 /function asNumber\(val\)\s*\{[\s\S]*?\n\}/,
 /function firstGood\(\.\.\.values\)\s*\{[\s\S]*?\n\}/,
 /function normalizeStatsList\(stats\)\s*\{[\s\S]*?\n\}/,
 /function fromTeams\(teams, homeId, awayId\)\s*\{[\s\S]*?\n\}/,
 /function buildLiveStats\(parts\)\s*\{[\s\S]*?\n\}/,
];
for(const regexp of snippets)assert.match(code,regexp);
const js=snippets.map(r=>code.match(r)[0]).join("\n")+"\nreturn {normalizeStatsList,fromTeams,buildLiveStats};";
const {normalizeStatsList,fromTeams,buildLiveStats}=new Function(js)();
const squads=[
 {team:{id:"501"},homeAway:"home",statistics:[{name:"wonCorners",displayValue:"2"},{name:"totalShots",displayValue:"6"},{name:"foulsCommitted",displayValue:"3"}]},
 {team:{id:"502"},homeAway:"away",statistics:[{name:"wonCorners",displayValue:"3"},{name:"totalShots",displayValue:"5"},{name:"foulsCommitted",displayValue:"4"}]}
];
const both=fromTeams(squads,"501","502"),stats=buildLiveStats(both);
assert.equal(stats.home.corner_kicks,2);
assert.equal(stats.away.corner_kicks,3);
assert.equal(stats.totals.corners,5);
assert.equal(stats.totals.total_shots,11);
assert.equal(stats.totals.fouls,7);
assert.equal(normalizeStatsList([{name:"wonCorners",displayValue:"0"}]).corner_kicks,0,"real zero must not be treated missing");
const partial=fromTeams([{team:{id:"501"},homeAway:"home",statistics:[{name:"totalShots",displayValue:"6"}]},
 {team:{id:"502"},homeAway:"away",statistics:[{name:"totalShots",displayValue:"4"}]}],"501","502");
assert.equal(buildLiveStats(partial).totals.corners,undefined,"never invent missing corner stats");
const alternate=normalizeStatsList([{name:"cornerKicks",displayValue:"5"}]);
assert.equal(alternate.corner_kicks,5,"retain historical label support");
assert.match(code,/live_with_corner_pairs/);
console.log("PASS: actual ESPN wonCorners -> verified two-sided corners; other markets preserved, missing stays missing");
