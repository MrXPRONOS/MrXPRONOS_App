#!/usr/bin/env python3
"""Authenticated and unauthenticated dashboard browser smoke with mocked RPC data.
Mock data is ONLY for CI, never production. Backend grants are tested independently.
"""
from __future__ import annotations
import json
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
    rpc: async (name) => {
      if(name==="is_admin")return {data:!!window.__mxAuditAdmin,error:null};
      if(!window.__mxAuditAdmin)return {data:null,error:{message:"Admin required"}};
      if(name==="admin_audience_dashboard_v1")
        return {data:window.__mxDashboardData,error:null};
      if(name==="admin_pwa_install_funnel_v2")
        return {data:window.__mxDashboardPwa,error:null};
      return {data:null,error:{message:"Unexpected RPC"}};
    }
  };
}
"""

def page_for(browser, allowed: bool, width: int):
    context = browser.new_context(viewport={"width":width,"height":850},accept_downloads=True)
    context.add_init_script(
        "window.__mxAuditAdmin="+str(allowed).lower()+";"+
        "window.__mxDashboardData="+json.dumps(DATA)+";"+
        "window.__mxDashboardPwa="+json.dumps(PWA)+";"
    )
    page=context.new_page()
    page.route("https://esm.sh/**", lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=MOCK))
    return context,page

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for width in (390,1200):
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
            page.locator("#tab-audience").click()
            with page.expect_download() as download_info:
                page.locator("#export").click()
            assert download_info.value.suggested_filename.endswith(".csv")
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 3"
            ),"Horizontal page overflow at %d" % width
            ctx.close()
        browser.close()
    print("PHASE4_BROWSER_DASHBOARD_AUTH_CHARTS_CSV_MOBILE_OK")

if __name__=="__main__":
    main()
