import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
const s=readFileSync("assets/js/live.precompiled.js","utf8");
execFileSync(process.execPath,["--check","assets/js/live.precompiled.js"],{stdio:"inherit"});
const zstart=s.indexOf('function z(e,s="home"){'),oStart=s.indexOf("function oe(e){",zstart);
const end=s.indexOf("const K=",oStart);
assert(zstart>=0&&oStart>zstart&&end>oStart&&end-zstart<1500);
const {team,league}=new Function(s.slice(zstart,oStart).replace("function z(","function team(")+";"+s.slice(oStart,end).replace("function oe(","function league(")+";return {team,league};")();
const row={
 home_team:"Binghamton",away_team:"NJIT",
 home_logo:"https://a.espncdn.com/i/teamlogos/ncaa/500/2066.png",
 away_logo:"https://a.espncdn.com/i/teamlogos/ncaa/500/2885.png",
 league_logo:"https://a.espncdn.com/i/leaguelogos/soccer/500/uefa.png"
};
assert.equal(team(row,"home"),row.home_logo);
assert.equal(team(row,"away"),row.away_logo);
assert.equal(league(row),row.league_logo);
assert.equal(team({home_team_obj:{logo:"https://img.thesports.com/football/team/team.png"}},"home"),"https://img.thesports.com/football/team/team.png");
assert.equal(team({raw_data:{away_logo:"https://img.thesports.com/football/team/away.png"}},"away"),"https://img.thesports.com/football/team/away.png");
assert.equal(team({home_logo:"javascript:alert(1)"},"home"),null);
assert.equal(team({},"home"),null);
const html=readFileSync("live.html","utf8");
assert(html.includes("assets/js/live.precompiled.js?v=20261022-real-logos1"));
console.log("PASS: browser bundle syntax, team logos, league logo, nested URL fallback, safe absent logo");
