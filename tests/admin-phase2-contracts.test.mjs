import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {inspectCmsEditorial} from '../assets/js/cms-quality.mjs';
import {createServerDraftStore} from '../assets/js/admin-draft-sync.mjs';
const read=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');

function draftDb(){
 const store=new Map(),user_id='11111111-1111-4111-8111-111111111111';
 const pick=(kind,identity)=>user_id+'|'+kind+'|'+identity;
 const sb={
   auth:{getUser:async()=>({data:{user:{id:user_id}},error:null})},
   from(table){
    assert.equal(table,'cms_editor_drafts');
    let op='read',value={},keys={};
    const q={
     select(){return q;},
     insert(v){op='insert';value=v;return q;},
     update(v){op='update';value=v;return q;},
     eq(k,v){keys[k]=v;return q;},
     async maybeSingle(){
      const key=pick(keys.kind,keys.identity),found=store.get(key)||null;
      if(op==='read')return {data:found,error:null};
      if(op==='update'){
       if(!found||found.revision!==keys.revision)return {data:null,error:null};
       const next={...found,...value};
       store.set(key,next);return {data:next,error:null};
      }
      return {data:null,error:{message:'Unexpected request'}};
     },
     async single(){
      const key=pick(value.kind,value.identity);
      if(store.has(key))return {data:null,error:{code:'23505',message:'duplicate'}};
      store.set(key,{...value});
      return {data:store.get(key),error:null};
     }
    };
    return q;
   }
 };
 return {sb,store,key:pick};
}
test('Drafts synchronize across reloads and reject conflicting edits',async()=>{
 const {sb,store,key}=draftDb();
 const spec={kind:'articles',getIdentity:()=> 'new'};
 const first=createServerDraftStore(sb,spec);
 await first.read();await first.save('Version 1');
 const second=createServerDraftStore(sb,spec);
 assert.equal((await second.read()).content,'Version 1');
 await first.save('Version 2');
 await assert.rejects(()=>second.save('Change from stale tab'),/modifié ailleurs/);
 assert.equal(store.get(key('articles','new')).content,'Version 2');
});
test('Draft IDs cannot mix documents',async()=>{
 const {sb,store,key}=draftDb();let id='article-a';
 const item=createServerDraftStore(sb,{kind:'articles',getIdentity:()=>id});
 await item.read();await item.save('A');
 id='article-b';await item.read();await item.save('B');
 assert.equal(store.get(key('articles','article-a')).content,'A');
 assert.equal(store.get(key('articles','article-b')).content,'B');
});
test('CMS QA stops bad slugs, duplicates and private media in published content',()=>{
 let bad=inspectCmsEditorial('articles',{title:'Annonce',slug:'bad slug',content:'ok',status:'published'});
 assert.match(bad.errors.join(' '),/Slug invalide/);
 bad=inspectCmsEditorial('articles',{id:'x2',title:'Annonce',slug:'demo',content:'ok',status:'published'},
  [{id:'x1',slug:'demo'}]);
 assert.match(bad.errors.join(' '),/existe déjà/);
 bad=inspectCmsEditorial('infos',{title:'Info',content:'ok',status:'published',
  image_url:'https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/sign/cms-drafts/asset.jpg'});
 assert.match(bad.errors.join(' '),/médias privés/);
});
test('CMS QA warns on missing SEO but does not require verbose content',()=>{
 const q=inspectCmsEditorial('articles',{title:'Titre',slug:'titre',content:'Court.',status:'published'});
 assert.equal(q.errors.length,0);
 assert.ok(q.warnings.some(w=>w.includes('SEO')));
});
test('Storage draft and publication stay separate; no public URL for unpublished upload',()=>{
 const media=read('assets/js/cms-media-library.mjs'),api=read('supabase/functions/admin-media-publish/index.ts');
 assert.match(media,/PRIVATE_BUCKET="cms-drafts"/);
 assert.match(media,/is_private:true/);
 assert.match(media,/createSignedUrl/);
 assert.match(api,/admin_can/);
 assert.match(api,/bucket_id:"cms-media"/);
});
test('Push campaigns have queue-level claims, idempotency, OIDC and explicit targets',()=>{
 const api=read('supabase/functions/admin-push/index.ts'),ui=read('assets/js/admin-real.js');
 assert.match(api,/\.eq\("status","queued"\)/);
 assert.match(api,/request_id/);
 assert.match(api,/jwtVerify/);
 assert.match(api,/mrxpronos-admin-push/);
 assert.match(api,/audience/);
 assert.match(ui,/pendingRequestId=crypto.randomUUID/);
 assert.match(ui,/Cette demande a déjà été enregistrée/);
 assert.match(ui,/Nouvelle campagne/);
 const workflow=read('.github/workflows/admin-push-dispatch.yml');
 assert.match(workflow,/id-token: write/);
 assert.match(workflow,/schedule:/);
 assert.doesNotMatch(workflow,/secrets\.CRON_SECRET/);
});
test('Subscribers and actual Push dispatch page through the database',()=>{
 const list=read('supabase/functions/admin-list-subscribers/index.ts');
 const send=read('supabase/functions/push-notifications/index.ts');
 assert.match(list,/range\(page\*pageSize,\(page\+1\)\*pageSize-1\)/);
 assert.match(send,/range\(offset,offset\+999\)/);
});
test('Admin access policies cannot silently demote the final owner',()=>{
 const sql=read('supabase/migrations/20261107075300_admin_last_owner_guard.sql');
 const roles=read('supabase/migrations/20261107075200_admin_role_scoped_rls.sql');
 assert.match(sql,/admin_protect_last_owner_delete/);
 assert.match(sql,/admin_protect_last_owner/);
 assert.match(roles,/admin_can\('cms'\)/);
 assert.match(roles,/admin_can\('vip'\)/);
});
test('The incident center and full archive search are wired to admin screens',()=>{
 const admin=read('assets/js/admin-real.js'),html=read('admin.html');
 assert.match(admin,/mountIncidentCenter/);
 assert.match(admin,/mountCmsServerSearch/);
 assert.match(html,/id="tab-incidents"/);
 assert.match(html,/id="tab-users"/);
 assert.match(admin,/adminPermissions/);
});
