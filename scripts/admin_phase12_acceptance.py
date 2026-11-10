#!/usr/bin/env python3
"""Phase 1/2 acceptance, screenshots and blocked side effects, using isolated fake Supabase."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path("artifacts/admin-phase12-acceptance")
BASE = "http://127.0.0.1:8000"
SIZES = {"desktop": (1440, 900), "tablet": (768, 1024), "mobile": (390, 844), "small": (320, 720)}
VIEWS = ["overview", "pronostics", "articles", "conseils", "vip", "push", "health", "audit"]

FAKE = r"""
(() => {
 const role=window.__qaRole||"owner";
 const permissions={
  owner:["read","cms","media","push","vip","users"],
  editor:["read","cms","media"],
  communications:["read","push"],
  viewer:["read"]
 };
 const dataset={
  cms_articles:[
   {id:"10000000-0000-4000-8000-000000000001",slug:"qa-article",title:"Analyse de match",
    content:"## Analyse\n\nContenu de test de la rédaction.",category:"Football",status:"draft",
    active:true,tags:["football"],updated_at:"2026-11-09T09:00:00Z"},
   {id:"10000000-0000-4000-8000-000000000002",slug:"qa-published",title:"Guide publié",
    content:"## Guide\n\nContenu publié fictif.",category:"Guides",status:"published",
    active:true,tags:["guide"],updated_at:"2026-11-08T09:00:00Z"}
  ],
  cms_conseils:[
   {id:"10000000-0000-4000-8000-000000000003",slug:"qa-conseil",title:"Conseil débutant",
    content:"## Conseil\n\nPrudence et gestion.",difficulty:"debutant",category:"Conseils",
    status:"draft",active:true,tags:[],updated_at:"2026-11-09T09:00:00Z"}
  ],
  vip_access:[
   {user_id:"MX-QA-001",code:"VIP-QA-001",active:true,expires_at:"2027-01-01T00:00:00Z"},
   {user_id:"MX-QA-002",code:"VIP-QA-002",active:false,expires_at:"2027-01-01T00:00:00Z"},
   {user_id:"MX-QA-003",code:"VIP-QA-003",active:true,expires_at:"2025-01-01T00:00:00Z"}
  ],
  cron_runs:[
   {name:"Scraping LIVE",last_ok:true,last_run_at:"2026-11-09T10:00:00Z",meta:{expected_interval_minutes:30}},
   {name:"Publication Telegram",last_ok:false,last_run_at:"2026-11-09T09:00:00Z",meta:{expected_interval_minutes:60}}
  ],
  audit_log:[
   {created_at:"2026-11-09T11:00:00Z",action:"vip_reset",actor_user_id:"qa-owner",details:{user_id:"MX-QA-001"}},
   {created_at:"2026-11-09T10:00:00Z",action:"cms_publish",actor_user_id:"qa-owner",details:{source:"QA"}}
  ],
  admin_push_campaigns:[{status:"scheduled",summary:{}},{status:"sent",summary:{sent:9,failed:1}}],
  analytics:[],admin_users:[]
 };
 window.__qaWrites=[];
 const chain=(table)=> {
  const c={
   select:()=>c,order:()=>c,limit:()=>Promise.resolve({data:dataset[table]||[],error:null}),
   range:()=>Promise.resolve({data:dataset[table]||[],error:null}),
   eq:()=>c,gte:()=>c,in:()=>c,
   single:()=>Promise.resolve({data:{},error:null}),
   maybeSingle:()=>Promise.resolve({data:null,error:null}),
   upsert:async rows=>{window.__qaWrites.push({operation:"upsert",table,rows});return {error:null}},
   insert:async rows=>{window.__qaWrites.push({operation:"insert",table,rows});return {error:null}},
   then:(resolve,reject)=>Promise.resolve({data:dataset[table]||[],error:null}).then(resolve,reject)
  };return c;
 };
 window.supabase={
  createClient:()=>({
   auth:{
    getSession:async()=>({data:{session:{access_token:"mock-session-not-real"}}}),
    getUser:async()=>({data:{user:{email:"qa@example.invalid",id:"10000000-0000-4000-8000-000000000000"}}}),
    signInWithPassword:async()=>({error:null}),signOut:async()=>({error:null})
   },
   rpc:async(name,args)=>{
    if(name==="is_admin")return {data:true,error:null};
    if(name==="admin_can")return {data:permissions[role].includes(args?.p_permission),error:null};
    if(name==="admin_audience_dashboard_v1")return {data:{
     summary:{visitors_period:19},daily:["2026-11-04","2026-11-05","2026-11-06","2026-11-07","2026-11-08","2026-11-09","2026-11-10"].map((day,i)=>({day,visitors:[3,5,4,7,8,6,9][i]}))
    },error:null};
    if(name==="admin_monitor_snapshot")return {data:{
     analytics:{visits:26},live:{total:8,wins:3,losses:1},
     telegram:{total:5},push:{subscriptions:4},health:{}},error:null};
    if(name==="admin_reset_vip"){
     window.__qaWrites.push({operation:"rpc",name,args});
     return {data:[{code:"VIP-TEST",expires_at:"2027-01-01T00:00:00Z"}],error:null};
    }
    if(name==="admin_revoke_vip"){
     window.__qaWrites.push({operation:"rpc",name,args});return {data:true,error:null};
    }
    if(name==="admin_cms_search")return {data:{items:[],total:0,has_more:false},error:null};
    return {data:{},error:null};
   },
   from:chain,
   channel:()=>({on(){return this},subscribe(){return this},track:async()=>{},unsubscribe:async()=>{}}),
   functions:{invoke:async()=>({data:{},error:null})}
  })
 };
})();
"""
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
DATA = {
 "generated_at": TODAY+"T10:00:00Z",
 "matches":[
  {"event_date":TODAY+"T18:00:00Z","home_team":"Arsenal","away_team":"Chelsea",
   "league":"Premier League","category":"pro","home_score":2,"away_score":1,"status":"won",
   "prediction":{"type":"Double chance","confidence":86}},
  {"event_date":TODAY+"T19:00:00Z","home_team":"Paris","away_team":"Lyon",
   "league":"Ligue 1","category":"pro","status":"pending","prediction":{"type":"1X","confidence":90}},
  {"event_date":TODAY+"T20:00:00Z","home_team":"Madrid","away_team":"Valence",
   "league":"Liga","category":"vip","status":"lost","prediction":{"type":"Over 1.5","confidence":83}}
 ]
}

def load(page,role="owner"):
 page.add_init_script("window.__qaRole="+json.dumps(role))
 page.route("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2",
            lambda route:route.fulfill(status=200,content_type="application/javascript",body=FAKE))
 page.route("https://cdn.jsdelivr.net/npm/marked/marked.min.js",
            lambda route:route.fulfill(status=200,content_type="application/javascript",body="window.marked={parse:s=>String(s)};"))
 page.route("**/admin-supervision.html?embedded=1",
            lambda route:route.fulfill(status=200,content_type="text/html",body="<html><body>QA</body></html>"))
 page.route("**/data.json?*",
            lambda route:route.fulfill(status=200,content_type="application/json",body=json.dumps(DATA)))
 api_calls=[]
 def stub_api(route):
  body=route.request.post_data_json or {}
  api_calls.append(body)
  if body.get("operation")=="history": payload={"campaigns":[]}
  elif body.get("operation")=="schedule": payload={"status":"queued","scheduled_at":body.get("scheduled_at")}
  elif body.get("operation")=="send": payload={"status":"sent","summary":{"sent":1,"failed":0}}
  else:payload={"data":[]}
  route.fulfill(status=200,content_type="application/json",body=json.dumps(payload))
 page.route("**/functions/v1/admin-*",lambda route:route.fulfill(status=200,content_type="application/json",body="{}"))
 page.route("**/functions/v1/admin-push",stub_api)
 page.route("https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/runs?*",
            lambda route:route.fulfill(status=200,content_type="application/json",body=json.dumps({"workflow_runs":[
             {"name":"Generate pronostics","conclusion":"success","status":"completed","created_at":"2026-11-09T09:00:00Z", "html_url":"https://github.com/MrXPRONOS/MrXPRONOS_App/actions","event":"schedule"},
             {"name":"Telegram LIVE","conclusion":"failure","status":"completed","created_at":"2026-11-09T08:00:00Z", "html_url":"https://github.com/MrXPRONOS/MrXPRONOS_App/actions","event":"schedule"}]})))
 page.goto(BASE+"/admin.html",wait_until="domcontentloaded")
 expect(page.locator("#app")).to_be_visible(timeout=20000)
 return api_calls

def navigate(page,name,width):
 if width<=640 and name in ("overview","pronostics","articles","vip"):
  page.locator('.admin-mobile-nav [data-tab="'+name+'"]').click()
 else:
  if width<=820:
   page.locator("#sidebar-open").click()
  page.locator('.sidebar-nav [data-tab="'+name+'"]').click()
 expect(page.locator("#tab-"+name)).to_be_visible(timeout=15000)

def visual(page,tag,width):
 for name in VIEWS:
  navigate(page,name,width)
  if name=="overview":
   expect(page.locator("#tab-overview .mxh-dashboard")).to_be_visible()
   expect(page.locator("#tab-overview .mxh-kpi")).to_have_count(4)
   expect(page.locator("#mxh-subs")).to_have_text("4")
   expect(page.locator("#mxh-sent")).to_have_text("9")
   expect(page.locator("#mxh-rate")).to_have_text("90,0 %")
   expect(page.locator("#mxh-graph svg")).to_be_visible()
   expect(page.locator("#mxh-service-rows .mxh-service-row")).to_have_count(4)
   expect(page.locator("#mxh-activity-rows .mxh-activity-row")).to_have_count(2)
   page.locator("#mxh-period").select_option("30")
   expect(page.locator("#mxh-period-label")).to_have_text("30 jours")
   page.locator("#mxh-period").select_option("7")
   expect(page.locator("#mxh-period-label")).to_have_text("7 jours")
  elif name=="pronostics":
   expect(page.locator("#pList .mx2-pronos-cards")).to_be_visible(timeout=10000)
   expect(page.locator("#pList .mx2-match-card")).to_have_count(2)
   page.locator('[data-view="table"]').click()
   expect(page.locator("#pList table")).to_be_visible()
   page.locator('[data-view="cards"]').click()
  elif name in ("articles","conseils"):
   prefix="a" if name=="articles" else "c"
   page.locator("#tab-"+name+" .admin-cms-editor-toggle").click()
   expect(page.locator("#tab-"+name+" .mx2-editor-preview")).to_be_visible(timeout=12000)
   page.locator("#"+prefix+"_title").fill("QA "+name)
   expect(page.locator("#tab-"+name+" .mx2-editor-preview-title")).to_have_text("QA "+name)
  elif name=="vip":
   expect(page.locator(".mx2-vip-stat")).to_have_count(3)
   page.locator(".mx2-vip-toolbar input").fill("MX-QA-001")
   expect(page.locator("#tab-vip table tbody tr:visible")).to_have_count(1)
   page.locator(".mx2-vip-toolbar input").fill("")
  elif name=="push":
   expect(page.locator(".mx2-push-device")).to_be_visible()
   page.locator("#push_title").fill("QA Push")
   expect(page.locator(".mx2-push-device-title")).to_have_text("QA Push")
  elif name=="health":
   expect(page.locator("#tab-health .mx3-health-dashboard")).to_be_visible()
   expect(page.locator("#tab-health .mx3-stat")).to_have_count(5)
   expect(page.locator("#tab-health .mx3-health-bar")).to_be_visible()
   page.locator("#tab-health .mx3-health-filters select").select_option("error")
   expect(page.locator("#tab-health .mx3-automation").first).to_be_visible()
   page.locator("#tab-health .mx3-health-filters select").select_option("all")
  elif name=="audit":
   expect(page.locator("#tab-audit .mx3-audit-workbench")).to_be_visible()
   expect(page.locator("#tab-audit .mx3-mini-chart-group")).to_have_count(7)
   page.locator("#tab-audit .mx3-audit-filters input").fill("vip_reset")
   expect(page.locator("#tab-audit .mx3-audit-table tbody tr")).to_have_count(1)
   with page.expect_download() as dl:
    page.locator("#tab-audit .mx3-audit-actions button").last.click()
   artifact=dl.value
   assert artifact.suggested_filename.startswith("mrxpronos-audit-")
   csv_content=artifact.path().read_text(encoding="utf-8-sig")
   assert "vip_reset" in csv_content and "cms_publish" not in csv_content
   page.locator("#tab-audit .mx3-audit-filters input").fill("")
  if width>=1000:
   overflow=page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
   assert overflow<=3,(tag,name,"global horizontal overflow",overflow)
  path=ROOT/(tag+"-"+name+".png")
  path.parent.mkdir(parents=True,exist_ok=True)
  page.screenshot(path=str(path),full_page=True,animations="disabled")
 if width>=821:
  button=page.locator("#sidebar-collapse")
  button.click()
  expect(page.locator("#app")).to_have_class("admin-workspace sidebar-collapsed")
  button.click()
 else:
  page.locator("#sidebar-open").click()
  expect(page.locator("#app")).to_have_class("admin-workspace menu-open")
  page.keyboard.press("Escape")
  assert "menu-open" not in (page.locator("#app").get_attribute("class") or "")

def functional(page,api_calls):
 page.on("dialog",lambda dialog:dialog.accept())
 navigate(page,"articles",1440)
 page.locator("#tab-articles .admin-cms-editor-toggle").click()
 page.locator('[data-id="10000000-0000-4000-8000-000000000001"]').click()
 page.locator("#a_title").fill("QA article edited")
 page.locator("#a_save").click()
 expect(page.locator("#tab-articles")).to_be_visible()
 navigate(page,"conseils",1440)
 page.locator("#tab-conseils .admin-cms-editor-toggle").click()
 page.locator('[data-id="10000000-0000-4000-8000-000000000003"]').click()
 page.locator("#c_title").fill("QA conseil edited")
 page.locator("#c_save").click()
 navigate(page,"vip",1440)
 page.locator("#v_user").fill("MX-QA-ONLY")
 page.locator("#v_days").fill("3")
 page.locator("#v_reset").click()
 expect(page.locator(".mx3-dialog")).to_be_visible()
 page.locator(".mx3-dialog [data-admin-dialog-confirm]").click()
 expect(page.locator(".mx3-dialog")).to_be_visible()
 page.locator(".mx3-dialog [data-admin-dialog-confirm]").click()
 navigate(page,"push",1440)
 page.locator("#push_audience").select_option("user")
 page.locator("#push_user_id").fill("MX-QA-ONLY")
 page.locator("#push_title").fill("QA scheduled")
 page.locator("#push_body").fill("Never sent externally")
 at=(datetime.now()+timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
 page.locator("#push_schedule_at").fill(at)
 page.locator("#push_schedule").click()
 expect(page.locator(".mx3-dialog")).to_be_visible()
 page.locator(".mx3-dialog [data-admin-dialog-confirm]").click()
 expect(page.locator("#push_status")).to_contain_text("Campagne enregistrée")
 writes=page.evaluate("window.__qaWrites")
 assert any(x.get("table")=="cms_articles" and x.get("operation")=="upsert" for x in writes),writes
 assert any(x.get("table")=="cms_conseils" and x.get("operation")=="upsert" for x in writes),writes
 assert any(x.get("name")=="admin_reset_vip" for x in writes),writes
 assert any(x.get("operation")=="schedule" for x in api_calls),api_calls
 assert not any(x.get("operation")=="send" for x in api_calls),api_calls

def roles(browser):
 for role in ("viewer","editor","communications"):
  page=browser.new_page(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
  try:
   load(page,role)
   for name,permission in [("articles","cms"),("vip","vip"),("push","push")]:
    allowed=permission in {"viewer":[],"editor":["cms"],"communications":["push"]}[role]
    desktop=page.locator('.sidebar-nav [data-tab="'+name+'"]')
    assert desktop.is_hidden() is not allowed,(role,name,"sidebar",desktop.is_hidden())
    quick=page.locator('.admin-mobile-nav [data-tab="'+name+'"]')
    if quick.count():
     assert quick.is_hidden() is not allowed,(role,name,"mobile",quick.is_hidden())
   if role=="communications":
    expect(page.locator('.admin-mobile-nav [data-tab="articles"]')).to_be_hidden()
   page.screenshot(path=str(ROOT/("role-"+role+".png")),full_page=True,animations="disabled")
  finally:page.close()

def main():
 ROOT.mkdir(parents=True,exist_ok=True)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
  try:
   for tag,(width,height) in SIZES.items():
    page=browser.new_page(viewport={"width":width,"height":height},device_scale_factor=1,
                            is_mobile=width<=390,has_touch=width<=390)
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    calls=load(page)
    visual(page,tag,width)
    if tag=="desktop":functional(page,calls)
    assert not errors,(tag,errors)
    page.close()
   roles(browser)
  finally:browser.close()
 print("ADMIN_PHASE12_VISUAL_FUNCTIONAL_ROLES_PASS")
if __name__=="__main__":main()
