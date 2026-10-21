// Runtime adapter: reproduce Supabase EdgeRuntime.waitUntil on a long-lived
// Render Deno server without modifying LIVE business logic.
// The live.ts coordinator returns HTTP 202 immediately; the promise continues
// in the same server process. Database leases + cron_runs track true completion.
const tasks = new Set<Promise<unknown>>();
(globalThis as typeof globalThis & { EdgeRuntime?: { waitUntil(p:Promise<unknown>):void } }).EdgeRuntime = {
  waitUntil(promise:Promise<unknown>) {
    tasks.add(promise);
    void promise.catch(err => {
      console.error("RENDER_LIVE_BACKGROUND_TASK_ERROR", String(err));
    }).finally(() => { tasks.delete(promise); });
  },
};
console.log("RENDER_EDGE_RUNTIME_WAITUNTIL_READY");
await import("../../supabase/functions/live/index.ts");
