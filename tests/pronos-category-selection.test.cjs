const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const script = fs.readFileSync(path.resolve(__dirname, "../assets/js/main.js"), "utf8");
const today = new Date().toISOString().slice(0, 10);
const kickoff = today + "T16:00:00Z";

function pick(id, category, overrides = {}) {
  return {
    id: "bsd:" + id, source: "bsd", event_date: kickoff, date: today,
    status: "notstarted", recommendation_eligible: true,
    is_finished: false, combo_only: false, category,
    home_team: "Equipe " + id, away_team: "Adversaire", league: "Test",
    final_score: 84, prediction: { selection_key: "OVER_15", confidence: 84 },
    ...overrides,
  };
}

function browserFixture(matches, search = "") {
  const url = { hostname: "localhost", search, href: "http://localhost/pronos.html" + search };
  const tabs = ["simple", "pro", "vip"].map(cat => ({
    dataset: { cat }, classList: { toggle() {} },
    setAttribute(name, value) { this[name] = value; },
    addEventListener(name, callback) { this[name] = callback; },
    tabIndex: -1,
  }));
  const counts = Object.fromEntries(["simple", "pro", "vip"].map(cat => [
    "count-" + cat, { textContent: "" },
  ]));
  const doc = {
    querySelectorAll(selector) {
      return selector === ".pronostic-category-tabs .tab-btn" ? tabs : [];
    },
    getElementById(id) { return counts[id] || null; },
    addEventListener() {},
  };
  const win = {
    location: url, history: { replaceState() {} },
    addEventListener() {},
    mockPanel: { setAttribute() {}, innerHTML: "" },
    testMatches: matches, renderedIds: [],
  };
  const context = vm.createContext({
    document: doc, window: win, location: url, URL, URLSearchParams,
    console, setTimeout, clearTimeout, Date,
  });
  vm.runInContext(script, context, { filename: "main.js" });
  vm.runInContext(
    'DOM.matches = window.mockPanel; allData = { matches: window.testMatches }; currentCategory = readInitialCategory(); renderMatches = function(matches) { window.renderedIds = matches.map(match => match.id); }; filterAndDisplay();',
    context
  );
  return {
    tabs, counts, context, window: win,
    get selected() { return vm.runInContext("currentCategory", context); },
    refresh(matchesAfter) {
      win.testMatches = matchesAfter;
      vm.runInContext("allData = { matches: window.testMatches }; filterAndDisplay();", context);
    },
    click(cat) {
      vm.runInContext("setupPronosticPageListeners()", context);
      tabs.find(tab => tab.dataset.cat === cat).click();
    },
  };
}

test("chooses Pro if Pro has the most visible predictions for today", () => {
  const browser = browserFixture([
    pick(1, "simple"), pick(2, "pro"), pick(3, "pro"),
    pick(4, "pro"), pick(5, "vip"),
  ]);
  assert.equal(browser.selected, "pro");
  assert.equal(browser.tabs[1]["aria-selected"], "true");
  assert.equal(browser.counts["count-pro"].textContent, "3");
  assert.equal(browser.window.renderedIds.length, 3);
});

test("chooses VIP if VIP has the largest number", () => {
  const browser = browserFixture([pick(1, "simple"), pick(2, "vip"), pick(3, "vip")]);
  assert.equal(browser.selected, "vip");
  assert.equal(browser.tabs[2].tabIndex, 0);
});

test("ties deterministically fall back to Simple then Pro then VIP", () => {
  assert.equal(browserFixture([
    pick(1, "simple"), pick(2, "pro"), pick(3, "vip"),
  ]).selected, "simple");
  assert.equal(browserFixture([
    pick(1, "pro"), pick(2, "vip"),
  ]).selected, "pro");
  assert.equal(browserFixture([]).selected, "simple");
});

test("only counts displayable matches from the selected date", () => {
  const browser = browserFixture([
    pick(1, "simple"),
    pick(2, "pro", { combo_only: true }),
    pick(3, "vip", { date: "2020-01-01" }),
    pick(4, "vip", { recommendation_eligible: false }),
  ]);
  assert.equal(browser.selected, "simple");
  assert.equal(browser.counts["count-vip"].textContent, "0");
});

test("a direct link ?cat=vip overrides automatic selection", () => {
  const browser = browserFixture([
    pick(1, "pro"), pick(2, "pro"), pick(3, "vip"),
  ], "?cat=vip");
  assert.equal(browser.selected, "vip");
});

test("manual tab selection stays in effect after a data refresh", () => {
  const initial = [pick(1, "pro"), pick(2, "pro"), pick(3, "simple")];
  const browser = browserFixture(initial);
  assert.equal(browser.selected, "pro");
  browser.click("simple");
  assert.equal(browser.selected, "simple");
  browser.refresh([...initial, pick(4, "pro"), pick(5, "pro")]);
  assert.equal(browser.selected, "simple");
  assert.equal(browser.tabs[0]["aria-selected"], "true");
});

test("automatic selection follows refreshed date-filtered data until a manual tab choice", () => {
  const browser = browserFixture([pick(1, "pro"), pick(2, "pro"), pick(3, "simple")]);
  assert.equal(browser.selected, "pro");
  browser.refresh([pick(4, "vip"), pick(5, "vip"), pick(6, "simple")]);
  assert.equal(browser.selected, "vip");
});
