import { safeEspnDate, parseEspnNumber, fetchSharedEspnScoreboard } from "../functions/_shared/espn.ts";

Deno.test("ESPN numeric parsing handles percent, locale and missing", () => {
  if (parseEspnNumber("55%") !== 55) throw new Error("percent failed");
  if (parseEspnNumber("12,5") !== 12.5) throw new Error("decimal failed");
  if (parseEspnNumber("1,234") !== 1234) throw new Error("thousands failed");
  if (parseEspnNumber("-") !== null) throw new Error("missing failed");
  if (parseEspnNumber("NaN") !== null) throw new Error("NaN failed");
});
Deno.test("ESPN dates are validated", () => {
  if (safeEspnDate("bad date") !== null) throw new Error("invalid date accepted");
  if (!safeEspnDate("2026-10-13T12:00:00Z")) throw new Error("valid date rejected");
});
Deno.test("ESPN scoreboard validates date before any outgoing call", async () => {
  let threw = false;
  try { await fetchSharedEspnScoreboard("2026-10-13"); }
  catch { threw = true; }
  if (!threw) throw new Error("bad date accepted");
});
Deno.test("ESPN scoreboard uses valid fresh cache without HTTP", async () => {
  let fetches = 0;
  const previous = globalThis.fetch;
  globalThis.fetch = ((_url: any, _opts: any) => {
    fetches++;
    throw new Error("Unexpected network request");
  }) as typeof fetch;
  const store = {
    async read(_key: string) {
      return { payload: { events: [{ id: "123" }] }, expires_at: new Date(Date.now() + 120000).toISOString() };
    },
    async write(_row: any) { throw new Error("Unexpected write"); },
  };
  try {
    const data = await fetchSharedEspnScoreboard("20261012", store);
    if (data.events[0].id !== "123" || fetches !== 0) throw new Error("cache miss");
  } finally { globalThis.fetch = previous; }
});
