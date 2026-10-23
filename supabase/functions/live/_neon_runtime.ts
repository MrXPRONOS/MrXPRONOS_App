// Runtime-only compatibility for the historical Deno LIVE handler.
import { readFile } from "node:fs/promises";
const original = globalThis.Deno;
globalThis.Deno ??= {
 env: { get(name: string) { return process.env[name]; } },
 readFile: async (url: URL | string) => new Uint8Array(await readFile(url)),
};
export {};
