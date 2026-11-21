import test from "node:test";
import assert from "node:assert/strict";
import {
  isNewChannelPublication, reactionFor,
  enqueueChannelReactions, processReactionQueue,
} from "../channel-reactions.mjs";

function memoryDB() {
  let serial=0;
  const posts=[];
  const jobs=[];
  const terminal=[];
  const DB={
    prepare(sql){
      let p=[];
      const stmt={
        bind(...v){p=v;return stmt;},
        async run(){
          if(sql.startsWith('CREATE TABLE IF NOT EXISTS cine_telegram_send_quota'))return {meta:{changes:0}};
          if(sql.startsWith("INSERT OR IGNORE INTO channel_reaction_posts")){
            const [chat_id,message_id,media_group_id]=p;
            if(!posts.some(x=>x.chat_id===chat_id && (x.message_id===message_id || (media_group_id && x.media_group_id===media_group_id)))){
              posts.push({seq:++serial,chat_id,message_id,media_group_id});
              return {meta:{changes:1}};
            }
            return {meta:{changes:0}};
          }
          if(sql.startsWith("INSERT OR IGNORE INTO channel_reaction_jobs")){
            const [post_seq,bot_role,emoji]=p;
            if(!jobs.some(j=>j.post_seq===post_seq&&j.bot_role===bot_role))
              jobs.push({post_seq,bot_role,emoji,state:"pending",attempts:0});
            return {meta:{changes:1}};
          }
          if(sql.startsWith("INSERT OR IGNORE INTO channel_reaction_terminal_posts")){
            if(!terminal.some(t=>t.post_seq===p[0]))terminal.push({post_seq:p[0],reason:p[1]});
            return {meta:{changes:1}};
          }
          if(sql.startsWith("UPDATE channel_reaction_jobs SET state='retry',next_try_at='9999-12-31")){
            const j=jobs.find(x=>x.post_seq===p[0]&&x.bot_role===p[1]);
            if(!j)return {meta:{changes:0}};
            j.state="retry";j.last_error="terminal:message_not_found";
            return {meta:{changes:1}};
          }
          if(sql.startsWith("UPDATE channel_reaction_jobs SET state='sending'")){
            const j=jobs.find(x=>x.post_seq===p[0]&&x.bot_role===p[1]&&x.state!=="sent");
            if(!j)return {meta:{changes:0}};
            j.state="sending";j.attempts++;
            return {meta:{changes:1}};
          }
          if(sql.startsWith("UPDATE channel_reaction_jobs SET state='sent'")){
            const j=jobs.find(x=>x.post_seq===p[0]&&x.bot_role===p[1]);
            j.state="sent";return {meta:{changes:1}};
          }
          if(sql.startsWith("UPDATE channel_reaction_jobs SET state='retry'")){
            const j=jobs.find(x=>x.post_seq===p[2]&&x.bot_role===p[3]);
            j.state="retry";return {meta:{changes:1}};
          }
          throw new Error("Unexpected SQL run: "+sql);
        },
        async first(){
          if(sql.startsWith('INSERT INTO cine_telegram_send_quota'))return {used:1};
          if(sql.startsWith("SELECT seq,message_id FROM channel_reaction_posts")){
            return posts.find(x=>x.chat_id===p[0]&&(x.message_id===p[1]||(p[2]&&x.media_group_id===p[2])))||null;
          }
          if(sql.startsWith("SELECT state FROM channel_reaction_jobs")){
            return jobs.find(x=>x.post_seq===p[0]&&x.bot_role==="radar")||null;
          }
          throw new Error("Unexpected SQL first: "+sql);
        },
        async all(){
          if(sql.startsWith("SELECT j.post_seq,j.bot_role")){
            return {results:jobs
              .filter(x=>x.state==="pending"&&!terminal.some(t=>t.post_seq===x.post_seq))
              .sort((a,b)=>a.post_seq-b.post_seq || (a.bot_role==="radar"?-1:1))
              .slice(0,p[0]).map(x=>({...x,...posts.find(y=>y.seq===x.post_seq)}))};
          }
          throw new Error("Unexpected SQL all: "+sql);
        },
      };return stmt;
    },
    async batch(items){for(const item of items)await item.run();return [];},
  };
  return {DB,posts,jobs,terminal};
}
const post=(id,group)=>({
  chat:{id:-1001234567890,type:"channel"},message_id:id,
  ...(group?{media_group_id:group}:{}),
});

test("Only new channel posts are eligible",()=>{
  assert.equal(isNewChannelPublication(post(1)),true);
  assert.equal(isNewChannelPublication({chat:{id:42,type:"private"},message_id:1}),false);
  assert.equal(isNewChannelPublication({chat:{id:-1001,type:"supergroup"},message_id:1}),false);
  assert.equal(isNewChannelPublication({chat:{id:-1001,type:"channel"},message_id:0}),false);
});
test("Bots alternate heart and thumbs on consecutive posts",()=>{
  assert.equal(reactionFor(1,"radar"),"❤️");
  assert.equal(reactionFor(1,"canal"),"👍");
  assert.equal(reactionFor(2,"radar"),"👍");
  assert.equal(reactionFor(2,"canal"),"❤️");
});
test("Duplicate Telegram updates and media albums enqueue only one reaction pair",async()=>{
  const {DB,posts,jobs}=memoryDB();
  const env={DB};
  await enqueueChannelReactions(env,post(101,"album1"));
  await enqueueChannelReactions(env,post(101,"album1"));
  await enqueueChannelReactions(env,post(102,"album1"));
  await enqueueChannelReactions(env,post(103));
  assert.equal(posts.length,2);
  assert.equal(jobs.length,4);
  assert.deepEqual(jobs.map(j=>j.emoji),["❤️","👍","👍","❤️"]);
});
test("Second bot follows first, failures stay queued and no extra publication is sent",async()=>{
  const {DB,jobs}=memoryDB();
  const env={DB,TELEGRAM_TOKEN:"radar-token",CANAL_BOT_TOKEN:"canal-token"};
  await enqueueChannelReactions(env,post(105));
  const sent=[];
  const request=async(url,opts)=>{
    const method=url.split("/").at(-1);
    const token=url.includes("/botradar-token/")?"radar":"canal";
    const data=JSON.parse(opts.body);
    if(method==="getMe")return Response.json({ok:true,result:{username:token==="radar"?"CineRadarFr_Bot":"mrxpronos_canal_bot"}});
    assert.equal(method,"setMessageReaction");
    sent.push({token,...data});
    return Response.json({ok:true,result:true});
  };
  const a=await processReactionQueue(env,{request});
  assert.equal(a.sent,2);
  assert.equal(a.deferred,0);
  const b=await processReactionQueue(env,{request});
  assert.equal(b.sent,0);
  assert.equal(sent.length,2);
  assert.deepEqual(sent.map(x=>x.token),["radar","canal"]);
  assert.deepEqual(sent.map(x=>x.reaction[0].emoji),["❤️","👍"]);
  assert.equal(jobs.filter(x=>x.state==="sent").length,2);
  const c=await processReactionQueue(env,{request});
  assert.equal(c.sent,0);
});
test("Missing second bot token never sends a partial pair",async()=>{
  const {DB}=memoryDB();
  const env={DB,TELEGRAM_TOKEN:"radar-token"};
  await enqueueChannelReactions(env,post(106));
  assert.deepEqual(await processReactionQueue(env),{skipped:"missing_bot_credentials_or_database"});
});

test("Telegram missing messages are quarantined without blocking later channel publications",async()=>{
  const {DB,jobs,terminal}=memoryDB();
  const env={DB,TELEGRAM_TOKEN:"radar-token",CANAL_BOT_TOKEN:"canal-token"};
  await enqueueChannelReactions(env,post(901));
  const calls=[];
  const request=async(url,opts)=>{
    const method=url.split("/").at(-1);
    if(method==="getMe")return Response.json({ok:true,result:{
      username:url.includes("botradar-token")?"CineRadarFr_Bot":"mrxpronos_canal_bot",
    }});
    const payload=JSON.parse(opts.body);
    calls.push(payload.message_id);
    if(payload.message_id===901)return Response.json(
      {ok:false,description:"Bad Request: message to react not found"},{status:400}
    );
    return Response.json({ok:true,result:true});
  };
  const first=await processReactionQueue(env,{request});
  assert.equal(first.failed,1);
  assert.deepEqual(terminal,[{post_seq:1,reason:"telegram_message_not_found"}]);
  assert.equal(jobs[0].last_error,"terminal:message_not_found");
  assert.equal(jobs[1].state,"pending");
  const repeat=await processReactionQueue(env,{request});
  assert.equal(repeat.sent,0);
  assert.deepEqual(calls,[901]);
  await enqueueChannelReactions(env,post(902));
  const next=await processReactionQueue(env,{request});
  assert.equal(next.sent,2);
  assert.deepEqual(calls,[901,902,902]);
  assert.equal(jobs.filter(j=>j.state==="sent").length,2);
});
