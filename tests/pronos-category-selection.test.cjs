const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

// vm.Script executes a classic-script fixture: remove only the new ESM import,
 // while the real browser loads the module normally.
const script = fs.readFileSync(path.resolve(__dirname, "../assets/js/main.js"), "utf8")
  .replace(/^import \{ safeCmsUrl, isSafeCmsUrl \} from "\.\/cms-url-guard\.mjs";\r?\n/m, "");
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
  const cats = ["all", "pro", "vip"];
  const tabs = cats.map(cat => ({
    dataset: { cat }, classList: { toggle() {} },
    setAttribute(name, value) { this[name] = value; },
    addEventListener(name, callback) { this[name] = callback; },
    tabIndex: -1,
  }));
  const counts = Object.fromEntries(cats.map(cat => [
    "count-" + cat, { textContent: "" },
  ]));
  const doc = {
    querySelector() { return null; },
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

test("Tous only displays Pro and VIP with confidence >=79, even when a stale cache has Simple", () => {
  const browser = browserFixture([
    pick(1, "simple"), pick(2, "pro"), pick(3, "pro", {
      prediction: { selection_key: "1X", confidence: 78.9 }
    }), pick(4, "vip"), pick(5, "simple"),
  ]);
  assert.equal(browser.selected, "all");
  assert.equal(browser.tabs.length, 3);
  assert.equal(browser.counts["count-all"].textContent, "2");
  assert.equal(browser.counts["count-pro"].textContent, "1");
  assert.equal(browser.counts["count-vip"].textContent, "1");
  assert.deepEqual([...browser.window.renderedIds], ["bsd:2", "bsd:4"]);
});

test("Tous filters out combo-only, old-day, disabled and under-79 matches", () => {
  const browser = browserFixture([
    pick(1, "simple"), pick(2, "pro", { combo_only: true }),
    pick(3, "vip", { date: "2020-01-01" }),
    pick(4, "vip", { recommendation_eligible: false }),
    pick(5, "pro", { prediction: { confidence: 78.999 } }),
    pick(6, "vip", { prediction: { confidence: 79 } }),
  ]);
  assert.equal(browser.counts["count-all"].textContent, "1");
  assert.deepEqual([...browser.window.renderedIds], ["bsd:6"]);
});

test("legacy direct ?cat=simple falls back to Tous and cannot expose Simple", () => {
  const browser = browserFixture([
    pick(1, "simple"), pick(2, "pro"), pick(3, "vip"),
  ], "?cat=simple");
  assert.equal(browser.selected, "all");
  assert.deepEqual([...browser.window.renderedIds], ["bsd:2", "bsd:3"]);
});

test("Pro and VIP deep links still work", () => {
  const browser = browserFixture([pick(1, "pro"), pick(2, "pro"), pick(3, "vip")], "?cat=vip");
  assert.equal(browser.selected, "vip");
  assert.deepEqual([...browser.window.renderedIds], ["bsd:3"]);
});

test("a manual Pro choice survives feed refresh and Simple stays invisible", () => {
  const initial = [pick(1, "pro"), pick(2, "vip"), pick(3, "simple")];
  const browser = browserFixture(initial);
  browser.click("pro");
  assert.equal(browser.selected, "pro");
  browser.refresh([...initial, pick(4, "pro"), pick(5, "simple")]);
  assert.equal(browser.selected, "pro");
  assert.equal(browser.tabs[1]["aria-selected"], "true");
  assert.deepEqual([...browser.window.renderedIds], ["bsd:1", "bsd:4"]);
});

test("Tous remains default after refresh", () => {
  const browser = browserFixture([pick(1, "pro"), pick(2, "simple")]);
  browser.refresh([pick(3, "vip"), pick(4, "vip"), pick(5, "simple")]);
  assert.equal(browser.selected, "all");
  assert.deepEqual([...browser.window.renderedIds], ["bsd:3", "bsd:4"]);
});
