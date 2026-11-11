#!/usr/bin/env python3
"""Authenticated and unauthenticated dashboard browser smoke with mocked RPC data.
Mock data is ONLY for CI, never production. Backend grants are tested independently.
"""
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/statistiques-audience.html"
DATA = {
    "period_days": 30, "start_day":"2026-10-08", "end_day":"2026-11-06",
    "summary": {
        "dau": 2, "wau": 8, "mau": 15, "visitors_period": 15,
        "sessions": 22, "page_views": 47, "engaged_sessions": 12,
        "standalone_sessions": 4, "returning_visitor_ids": 5
    },
    "cohorts":{
        "j1":{"eligible":3,"returned":1},
        "j7":{"eligible":0,"returned":0},
        "j30":{"eligible":0,"returned":0}
    },
    "daily":[{"day":"2026-11-06","visitors":2,"sessions":3,
              "page_views":5,"engaged_sessions":1,"standalone_sessions":0}],
    "install_funnel":{"cta_visible":6,"cta_click":3,"prompt_accepted":1,
                      "appinstalled":1,"standalone_open":2,"guide_open":1},
    "acquisition":[{"channel":"whatsapp","visitors":3,"cta_clicks":1,
                    "appinstalled":0,"standalone_open":1}],
    "campaigns":[{"campaign":"pronos_novembre","channel":"whatsapp","visitors":3}],
    "pages":[{"page":"/aujourdhui.html","views":7}],
    "quality":{"legacy_raw_visits":200,"legacy_high_rate_minutes":2,
               "legacy_historic_ci_window_visits":12,"days_without_telemetry":3,
               "session_events":47,"acquisition_visitor_ids":6,
               "installation_events":8}
}
AB = {
    "period_days":30,
    "experiments":[
        {"id":"install_value_v1","label":"Texte du panneau d’installation",
         "goal":"install_cta_click","enabled":True,
         "variants":[{"variant":"a","exposed":240,"converted":60,
                       "matured_exposed":215,"matured_converted":45},
                     {"variant":"b","exposed":245,"converted":72,
                       "matured_exposed":220,"matured_converted":60}]},
        {"id":"favorites_guidance_v1","label":"Présentation des favoris",
         "goal":"favorite_added","enabled":False,
         "variants":[{"variant":"a","exposed":15,"converted":2,
                       "matured_exposed":0,"matured_converted":0},
                     {"variant":"b","exposed":16,"converted":4,
                       "matured_exposed":0,"matured_converted":0}]}
    ],
    "daily":[{"day":"2026-11-06","experiment":"install_value_v1",
             "variant":"a","exposed":3,"converted":1},
            {"day":"2026-11-06","experiment":"install_value_v1",
             "variant":"b","exposed":5,"converted":2}]
}

PWA = {
    "platforms":[{"platform":"android","cta_visible":5,
                   "cta_click":2,"standalone_open":2}],
    "surfaces":[{"surface":"home","cta_visible":4,"cta_click":1}]
}
MOCK = """
export function createClient() {
  return {
    auth: {
      getUser: async () => ({data:{user:window.__mxAuditAdmin?{id:"demo"}:null},error:null}),
      signInWithPassword:async () => ({error:{message:"CI only: login disabled"}}),
      signOut:async () => ({error:null})
    },
    rpc: async (name, params) => {
      if(name==="is_admin")return {data:!!window.__mxAuditAdmin,error:null};
      if(!window.__mxAuditAdmin)return {data:null,error:{message:"Admin required"}};
      if(name==="admin_audience_dashboard_v1")
        return {data:window.__mxDashboardData,error:null};
      if(name==="admin_pwa_install_funnel_v2")
        return {data:window.__mxDashboardPwa,error:null};
      if(name==="admin_experiment_report_v1")
        return {data:window.__mxDashboardAb,error:null};
      if(name==="admin_set_experiment_v1") {
        const target=window.__mxDashboardAb.experiments.find(e=>e.id===params?.p_experiment);
        if(target)target.enabled=!!params.p_enabled;
        return {data:{enabled:!!params?.p_enabled},error:null};
      }
      return {data:null,error:{message:"Unexpected RPC"}};
    }
  };
}
"""

def page_for(browser, allowed: bool, width: int):
    context = browser.new_context(viewport={"width":width,"height":{320:720,390:844,768:1024,1440:900}[width]},accept_downloads=True,device_scale_factor=1,is_mobile=width<=390,has_touch=width<=390)
    context.add_init_script(
        "window.__mxAuditAdmin="+str(allowed).lower()+";"+
        "window.__mxDashboardData="+json.dumps(DATA)+";"+
        "window.__mxDashboardPwa="+json.dumps(PWA)+";"+
        "window.__mxDashboardAb="+json.dumps(AB)+";"
    )
    page=context.new_page()
    page.route("https://esm.sh/**", lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=MOCK,
        headers={"Access-Control-Allow-Origin":"*",
                 "Cross-Origin-Resource-Policy":"cross-origin"}))
    return context,page

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,channel="chrome",args=["--no-sandbox"])
        for width in (320,390,768,1440):
            ctx,page=page_for(browser,False,width)
            page.goto(URL,wait_until="domcontentloaded")
            page.locator("#auth-form").wait_for(state="visible",timeout=15000)
            assert page.locator("#dashboard").is_hidden(), "Anonymous user sees dashboard"
            assert "administrateur" in page.locator("#status").inner_text().lower()
            ctx.close()

            ctx,page=page_for(browser,True,width)
            page.goto(URL,wait_until="domcontentloaded")
            page.locator("#dashboard").wait_for(state="visible",timeout=15000)
            page.get_by_text("22",exact=True).first.wait_for(timeout=5000)
            assert page.locator("#kpi-sessions").inner_text()=="22"
            assert page.locator("#ret-j1").inner_text().replace("\u00a0"," ").replace("\u202f"," ")=="33,3 %"
            assert page.locator("#ret-j7").inner_text()=="—"
            assert page.locator("#kpi-pageviews").inner_text()=="47"
            assert page.locator("#data-note").is_visible()
            page.locator("#tab-acquisition").click()
            assert page.locator("#panel-acquisition").is_visible()
            assert "pronos_novembre" in page.locator("#campaign-rows").inner_text()
            page.locator("#tab-installation").click()
            assert page.locator("#ins-clicks").inner_text()=="3"
            page.locator("#tab-retention").click()
            assert "cohorte" in page.locator("#panel-retention").inner_text().lower()
            page.locator("#tab-experiments").click()
            assert page.locator("#panel-experiments").is_visible()
            assert page.locator("#experiment-results tr").count() == 4
            assert page.locator("#experiment-cards .card").count() == 2
            assert "Aucune cohorte" not in page.locator("#experiment-results").inner_text()
            page.once("dialog",lambda dialog: dialog.accept())
            page.locator("#experiment-cards .experiment-action").first.click()
            page.locator("#experiment-cards .experiment-action").first.wait_for(state="visible")
            assert "EN PAUSE" in page.locator("#experiment-cards .card").first.inner_text()
            page.locator("#tab-audience").click()
            with page.expect_download() as download_info:
                page.locator("#export").click()
            assert download_info.value.suggested_filename.endswith(".csv")
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 3"
            ),"Horizontal page overflow at %d" % width
            # Validate computed V3 visuals and capture actual desktop/tablet/mobile screenshots.
            assert page.locator("body").get_attribute("data-admin-ui") == "analytics-premium-v3"
            assert page.locator(".back-admin").is_visible(), "Back-to-admin shortcut missing"
            assert page.locator(".intro h1").inner_text().strip().startswith("Statistiques")
            premium = page.evaluate("""() => {
                const c = getComputedStyle(document.body);
                const k = getComputedStyle(document.querySelector(".kpi"));
                const hero = getComputedStyle(document.querySelector(".intro"));
                return {background:c.backgroundImage,card:k.backgroundImage,border:k.borderRadius,hero:hero.backgroundImage};
            }""")
            assert "gradient" in premium["background"] and "gradient" in premium["card"], premium
            assert "gradient" in premium["hero"], premium
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 3"
            ), "V3 horizontal overflow at width %d" % width
            out = Path("artifacts/audience-phase4-visual")
            out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out/("analytics-v3-%d.png" % width)),
                            full_page=True,animations="disabled")
            ctx.close()
        browser.close()
    print("PHASE4_BROWSER_DASHBOARD_AUTH_CHARTS_CSV_MOBILE_V3_OK")

if __name__=="__main__":
    main()
