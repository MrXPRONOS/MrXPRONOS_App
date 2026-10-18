#!/usr/bin/env python3
"""Smoke-test new admin menu and isolated screens without real credentials."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8000"
FAKE_SUPABASE = r"""
window.supabase = {
  createClient() {
    const records = {data: [], error: null};
    const chain = {
      select: () => chain,
      order: () => chain,
      limit: () => Promise.resolve(records),
      eq: () => chain,
      single: () => Promise.resolve({data: {}, error: null}),
      then: (resolve) => Promise.resolve(records).then(resolve)
    };
    return {
      auth: {
        getSession: async () => ({data:{session:{access_token:"test-only"}}}),
        getUser: async () => ({data:{user:{email:"qa@example.invalid"}}}),
        signInWithPassword: async () => ({error:null}),
        signOut: async () => ({error:null})
      },
      rpc: async (name) => ({data: name === "is_admin" ? true : {}, error:null}),
      from: () => chain
    };
  }
};
"""

def run(page, mobile=False):
    page.route("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2", lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=FAKE_SUPABASE))
    # The full live iframe is tested independently; navigation must not need live Supabase.
    page.route("**/admin-supervision.html?embedded=1", lambda route: route.fulfill(
        status=200, content_type="text/html",
        body="<html><body><h2>Supervision intégrée</h2></body></html>"))
    page.goto(BASE + "/admin.html", wait_until="domcontentloaded")
    expect(page.locator("#app")).to_be_visible(timeout=15000)
    expect(page.locator("#view-title")).to_have_text("Vue générale")
    expect(page.locator("#tab-overview")).to_be_visible()
    assert page.locator("#supervisionFrame").get_attribute("src").endswith("embedded=1")
    assert page.locator(".nav-item").count() == 10

    if mobile:
        expect(page.locator("#sidebar-open")).to_be_visible()
        page.locator("#sidebar-open").click()
        expect(page.locator("#app")).to_have_class("admin-workspace menu-open")
    page.locator('[data-tab="push"]').click()
    expect(page.locator("#view-title")).to_have_text("Notifications Push")
    expect(page.locator("#tab-overview")).to_be_hidden()
    expect(page.locator("#tab-push")).to_be_visible()
    expect(page.locator("#push_title")).to_be_visible()
    expect(page.locator("#btnPublish")).to_be_hidden()
    assert page.url.endswith("#push")
    if mobile:
        assert "menu-open" not in (page.locator("#app").get_attribute("class") or "")
        page.locator("#sidebar-open").click()
    page.locator('[data-tab="articles"]').click()
    expect(page.locator("#tab-articles")).to_be_visible()
    expect(page.locator("#tab-push")).to_be_hidden()
    expect(page.locator("#btnPublish")).to_be_visible()
    expect(page.locator("#view-title")).to_have_text("Articles")
    if mobile:
        page.locator("#sidebar-open").click()
        page.keyboard.press("Escape")
        assert "menu-open" not in (page.locator("#app").get_attribute("class") or "")
    page.screenshot(path=str(Path("artifacts/admin-navigation") / ("mobile.png" if mobile else "desktop.png")), full_page=True)


if __name__ == "__main__":
    Path("artifacts/admin-navigation").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        desktop = browser.new_page(viewport={"width":1440,"height":900})
        run(desktop)
        mobile = browser.new_page(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
        run(mobile,mobile=True)
        browser.close()
    print("Unified admin sidebar: desktop and mobile smoke passed")
