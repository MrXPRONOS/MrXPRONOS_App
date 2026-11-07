#!/usr/bin/env python3
"""End-to-end A/B UI smoke: REAL site assets, mocked Supabase, no production writes."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit,unquote
import json,mimetypes
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
ORIGIN="https://mrxpronos.test"
FIXTURE={
    "generated_at":datetime.now(timezone.utc).isoformat(),
    "matches":[{
        "id":"ci-fixture-1","home_team":"Real Madrid",
        "away_team":"FC Barcelone","league":"La Liga","date":datetime.now(timezone.utc).date().isoformat(),
        "event_date":datetime.now(timezone.utc).date().isoformat()+"T19:00:00Z",
        "category":"pro","recommendation_eligible":True,
        "combo_only":False,"status":"scheduled","is_finished":False,
        "prediction":{"confidence":83,"type":"Test de sélection"}
    }]
}
MOCK_SDK=r"""
export function createClient(){
  const chain={
    select:()=>chain,eq:()=>chain,order:()=>chain,limit:()=>chain,
    single:async()=>({data:{},error:null}),
    then:resolve=>Promise.resolve({data:[],error:null}).then(resolve)
  };
  return {
    auth:{getUser:async()=>({data:{user:null},error:null})},
    rpc:async (name,params)=>{
      window.__phase5Calls.push({name,params});
      if(name==="experiment_variant_v1")return {data:{enabled:true,variant:"b"},error:null};
      if(name==="track_experiment_v1")return {data:true,error:null};
      if(name==="track_visitor_session_v2")return {data:true,error:null};
      if(name==="track_pwa_install_event_v2")return {data:true,error:null};
      if(name==="track_acquisition_v1")return {data:true,error:null};
      if(name==="increment_counter")return {data:true,error:null};
      return {data:null,error:null};
    },
    from:()=>chain,
    channel:()=>({on(){return this},subscribe(){return this}}),
    removeChannel:()=>{}
  };
}
"""

def asset(route):
    url=urlsplit(route.request.url)
    path=unquote(url.path).lstrip("/")
    if not path: path="index.html"
    if path=="data.json":
        return route.fulfill(status=200,content_type="application/json",
                             body=json.dumps(FIXTURE))
    target=(ROOT/path).resolve()
    if not target.is_relative_to(ROOT) or not target.is_file():
        return route.fulfill(status=404,body="Not found")
    mime=mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if target.suffix in (".mjs",".js"):mime="text/javascript"
    return route.fulfill(status=200,content_type=mime,body=target.read_bytes())

def ready(page,id,kind):
    page.wait_for_function("""(arg) =>
      window.__phase5Calls.some(c=>c.name==="track_experiment_v1" &&
        c.params?.p_kind===arg.kind && c.params?.p_experiment===arg.id)
    """,arg={"id":id,"kind":kind},timeout=12000)

def run(browser,width):
    ctx=browser.new_context(viewport={"width":width,"height":850},service_workers="block")
    ctx.add_init_script("""
      window.__phase5Calls=[];
      try { localStorage.setItem("mx_user_id","MX-phase5-ci-browser-2026"); }
      catch(e) {}
    """)
    ctx.route(ORIGIN+"/**",asset)
    ctx.route("https://esm.sh/**",lambda route:route.fulfill(
        status=200,content_type="text/javascript",body=MOCK_SDK,
        headers={"Access-Control-Allow-Origin":"*"}))
    page=ctx.new_page()

    page.goto(ORIGIN+"/index.html",wait_until="domcontentloaded")
    panel=page.locator("#mx-install-panel")
    panel.wait_for(state="visible",timeout=15000)
    expect(page.locator("#mx-install-panel-title")).to_have_text(
        "Mr XPRONOS directement sur votre écran d’accueil.",timeout=12000)
    panel.scroll_into_view_if_needed()
    ready(page,"install_value_v1","exposure")
    page.locator(".mx-install-panel-button").click(timeout=10000)
    ready(page,"install_value_v1","conversion")

    page.goto(ORIGIN+"/aujourdhui.html",wait_until="domcontentloaded")
    expect(page.locator("#favorites-title")).to_have_text(
        "Suivez vos équipes favorites.",timeout=12000)
    favorites=page.locator("#daily-favorites")
    favorites.scroll_into_view_if_needed()
    ready(page,"favorites_guidance_v1","exposure")
    page.locator("#daily-favorite-kind").select_option("teams")
    page.locator("#daily-favorite-options option").first.wait_for(state="attached",timeout=12000)
    page.locator("#daily-favorite-name").fill("Real Madrid")
    page.locator("#daily-add-favorite button[type=submit]").click()
    page.get_by_text("Favori enregistré : Real Madrid").wait_for(timeout=12000)
    ready(page,"favorites_guidance_v1","conversion")
    assert page.evaluate("""() => window.__phase5Calls.filter(
      c=>c.name==="track_experiment_v1" && c.params?.p_kind==="conversion"
    ).length""")==1, "Exactly one genuine favorite conversion expected in this page"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+3"),"Mobile horizontal overflow"
    ctx.close()

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width in (390,1200):run(browser,width)
    browser.close()
print("PHASE5_PUBLIC_AB_COPY_EXPOSURE_TRUE_CLICK_FAVORITE_MOBILE_OK")
