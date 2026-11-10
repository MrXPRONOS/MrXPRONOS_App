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
      range: () => Promise.resolve(records),
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
      rpc: async (name) => ({data: ["is_admin","admin_can"].includes(name) ? true : {}, error:null}),
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
    expect(page.locator("#view-title")).to_have_text("Tableau de bord")
    expect(page.locator("#tab-overview")).to_be_visible()
    expect(page.locator("#admin-overview-summary")).to_be_visible()
    expect(page.locator("#admin-overview-summary .mxh-kpi")).to_have_count(4)
    assert not page.locator("#supervisionFrame").get_attribute("src"), "Details frame must load on demand"
    page.locator("#admin-detailed-supervision summary").click()
    expect(page.locator("#admin-detailed-supervision")).to_have_attribute("open", "")
    expect(page.locator("#supervisionFrame")).to_have_attribute("src", "admin-supervision.html?embedded=1")
    page.locator("#admin-detailed-supervision summary").click()
    assert page.locator(".nav-item.tab").count() == 13  # Incidents + Administrateurs
    assert page.locator('[data-tab="media"]').count() == 1
    if mobile:
        expect(page.locator(".admin-mobile-nav")).to_be_visible()
    else:
        expect(page.locator("#sidebar-collapse")).to_be_visible()

    if mobile:
        expect(page.locator("#sidebar-open")).to_be_visible()
        page.locator("#sidebar-open").click()
        assert "menu-open" in (page.locator("#app").get_attribute("class") or "")
    page.locator('[data-tab="push"]').click()
    expect(page.locator("#view-title")).to_have_text("Notifications Push")
    expect(page.locator("#tab-overview")).to_be_hidden()
    expect(page.locator("#tab-push")).to_be_visible()
    expect(page.locator("#push_title")).to_be_visible()
    expect(page.locator("#push_audience")).to_have_value("")
    expect(page.locator("#push_preview")).to_be_visible()
    expect(page.locator(".mx2-push-device")).to_be_visible()
    expect(page.locator(".mx2-push-device-title")).to_have_text("Titre de la notification")
    page.locator("#push_preview").click()
    expect(page.locator("#push_status")).to_contain_text("Choisis les destinataires")
    expect(page.locator("#btnPublish")).to_be_hidden()
    assert page.url.endswith("#push")
    if mobile:
        assert "menu-open" not in (page.locator("#app").get_attribute("class") or "")
        page.locator("#sidebar-open").click()
    page.locator('.sidebar-nav [data-tab="articles"]').click()
    expect(page.locator("#tab-articles")).to_be_visible()
    expect(page.locator("#tab-push")).to_be_hidden()
    expect(page.locator("#btnPublish")).to_be_visible()
    expect(page.locator("#view-title")).to_have_text("Articles")
    expect(page.locator(".admin-cms-editor-toggle")).to_be_visible()
    assert page.locator(".admin-cms-editor-fields").get_attribute("hidden") is not None
    page.locator(".admin-cms-editor-toggle").click()
    expect(page.locator("#a_title")).to_be_visible()
    expect(page.locator(".mx2-editor-preview")).to_be_visible()
    page.locator("#a_title").fill("Un aperçu phase 2")
    expect(page.locator(".mx2-editor-preview-title")).to_have_text("Un aperçu phase 2")
    # The draft uses the public reader structure, with a sandboxed preview.
    page.locator(".mx-block-editor .mx-block-toolbar button", has_text="Prévisualiser").click()
    preview = page.locator(".mx-block-preview iframe")
    expect(preview).to_have_attribute("sandbox", "")
    reader = page.frame_locator(".mx-block-preview iframe").locator("article.mx-reader-article")
    expect(reader).to_be_visible()
    public_css = page.frame_locator(".mx-block-preview iframe").locator(
        'link[href="assets/css/article-detail-premium.css"]')
    expect(public_css).to_have_count(1)
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
