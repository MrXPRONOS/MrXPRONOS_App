import test from "node:test";
import assert from "node:assert/strict";
import {indexQualifiedChannels} from "../worker.mjs";
import {maintenance} from "../radar-features.mjs";

const rows=[
 {username:"GoodCinema999",title:"Public cinéma",link:"https://t.me/GoodCinema999",content_type:"films",genre:"general",matching_pairs:3,technical_status:"qualified",rights_status:"unverified"},
 {username:"NonVerified11",title:"Non validé",link:"https://t.me/NonVerified11",content_type:"films",genre:"general",matching_pairs:1,technical_status:"rejected_format",rights_status:"unverified"},
 {username:"DeadChannel99",title:"Ancien canal",link:"https://t.me/DeadChannel99",content_type:"films",genre:"general",matching_pairs:4,technical_status:"qualified",rights_status:"link_dead"}
];
function makeDB(){
 const state={candidates:rows.map(x=>({...x})),channels:[],checks:new Map(),deletions:[]};
 const db={
  state,
  prepare(sql){
   let params=[];
   const q={
    bind(...args){params=args;return q},
    async all(){
     if(sql.includes("FROM discovery_candidates WHERE technical_status='qualified'"))return {results:state.candidates.filter(x=>x.technical_status==="qualified"&&x.matching_pairs>=2&&!["link_dead","rejected"].includes(x.rights_status))};
     if(sql.includes("FROM channels c LEFT JOIN channel_telemetry")&&sql.includes("previous_status"))return {results:state.channels.map(c=>({id:c.id,link:c.link,previous_status:state.checks.get(c.id)||"unknown"}))};
     return {results:[]};
    },
    async first(){return null},
    async run(){
     if(sql.startsWith("INSERT INTO channels")){
      if(!state.channels.some(c=>c.link===params[1]))state.channels.push({id:state.channels.length+1,title:params[0],link:params[1],status:"approved"});
     }
     if(sql.startsWith("INSERT INTO channel_telemetry"))state.checks.set(params[0],params[1]);
     if(sql.startsWith("UPDATE discovery_candidates SET rights_status='link_dead'")){
      const c=state.candidates.find(x=>x.link===params[0]);if(c){c.rights_status="link_dead";c.technical_status="rejected_format";}
     }
     if(sql.startsWith("DELETE FROM channels")){state.channels=state.channels.filter(c=>c.id!==params[0]);state.deletions.push(params[0]);}
     return {meta:{changes:1}};
    }
   };return q;
  },
  async batch(statements){for(const x of statements)await x.run();return [];}
 };
 return db;
}

test("Public discovery automatically indexes verified photo/video channel without a manual license flag",async()=>{
 const db=makeDB();const result=await indexQualifiedChannels({DB:db});
 assert.equal(result.indexed,1);
 assert.equal(db.state.channels.length,1);
 assert.match(db.state.channels[0].link,/GoodCinema999/);
});
test("Repeated sync does not create duplicate links",async()=>{
 const db=makeDB();await indexQualifiedChannels({DB:db});await indexQualifiedChannels({DB:db});
 assert.equal(db.state.channels.length,1);
});
test("Two confirmed double-404 checks purge channel and blacklist stale discovery",async()=>{
 const saved=globalThis.fetch;const db=makeDB();
 await indexQualifiedChannels({DB:db});
 globalThis.fetch=async()=>new Response("gone",{status:404});
 try{
  await maintenance({DB:db},"activity");
  assert.equal(db.state.channels.length,1);
  assert.equal(db.state.checks.get(1),"not_found");
  await maintenance({DB:db},"activity");
  assert.equal(db.state.channels.length,0);
  assert.equal(db.state.candidates[0].technical_status,"rejected_format");
  assert.equal(db.state.candidates[0].rights_status,"link_dead");
  await indexQualifiedChannels({DB:db});
  assert.equal(db.state.channels.length,0);
 }finally{globalThis.fetch=saved;}
});
test("One 404 with an accessible public landing page does not delete",async()=>{
 const saved=globalThis.fetch;const db=makeDB();await indexQualifiedChannels({DB:db});
 globalThis.fetch=async url=>new Response("",{status:String(url).includes("/s/")?404:200});
 try{await maintenance({DB:db},"activity");await maintenance({DB:db},"activity");assert.equal(db.state.channels.length,1);}finally{globalThis.fetch=saved;}
});
test("Temporary Telegram HTTP 429 never deletes listings",async()=>{
 const saved=globalThis.fetch;const db=makeDB();await indexQualifiedChannels({DB:db});
 globalThis.fetch=async()=>new Response("Flood control",{status:429});
 try{await maintenance({DB:db},"activity");await maintenance({DB:db},"activity");assert.equal(db.state.channels.length,1);}finally{globalThis.fetch=saved;}
});
