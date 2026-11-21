import test from "node:test";
import assert from "node:assert/strict";
import { isChannelPublication, observeChannelPublication } from "../channel-reaction-observer.mjs";

function fakeDB() {
  const calls=[];
  const posts=[];
  return {
    calls, posts,
    DB: {
      prepare(sql) {
        assert.match(sql, /^INSERT OR IGNORE INTO channel_reaction_posts\(/);
        return {
          bind(...args) {
            return {
              async run() {
                calls.push({sql,args});
                const [chat_id,message_id,media_group_id]=args;
                if (!posts.some(p => p.chat_id===chat_id &&
                    (p.message_id===message_id ||
                     (media_group_id && p.media_group_id===media_group_id))))
                  posts.push({chat_id,message_id,media_group_id});
                return {meta:{changes:1}};
              }
            };
          }
        };
      }
    }
  };
}

const post = (message_id, media_group_id) => ({
  chat: {type:"channel",id:-1003921647496},
  message_id, ...(media_group_id?{media_group_id}:{}),
});

test("new channel publications only; edited, private and automatic forwards excluded", () => {
  assert.equal(isChannelPublication(post(375)),true);
  assert.equal(isChannelPublication({...post(375),is_automatic_forward:true}),false);
  assert.equal(isChannelPublication({...post(375),chat:{type:"private",id:77}}),false);
  assert.equal(isChannelPublication({...post(375),message_id:0}),false);
});

test("observer writes only one D1 INSERT per update, no queue reads or sends", async () => {
  const storage=fakeDB();
  await observeChannelPublication(storage,post(371,"album-A"));
  await observeChannelPublication(storage,post(372,"album-A"));
  await observeChannelPublication(storage,post(373));
  await observeChannelPublication(storage,post(373));
  assert.equal(storage.calls.length,4);
  assert.equal(storage.posts.length,2);
  assert.ok(storage.calls.every(x=>x.sql.startsWith("INSERT OR IGNORE INTO channel_reaction_posts")));
  assert.deepEqual(storage.posts.map(x=>x.message_id),[371,373]);
});

test("non-channel updates do not touch the D1 database",async()=>{
  const storage=fakeDB();
  assert.deepEqual(await observeChannelPublication(storage, {
    chat:{type:"group",id:-1003921647496},message_id:1,
  }),{observed:false});
  assert.equal(storage.calls.length,0);
});
