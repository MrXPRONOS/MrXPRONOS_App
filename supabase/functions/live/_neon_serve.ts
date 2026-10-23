type Handler = (request: Request) => Response | Promise<Response>;
let handler: Handler | null = null;
export function serve(fn: Handler) { handler = fn; }
export function neonGetHandler(): Handler {
 if (!handler) throw new Error("LIVE_HANDLER_NOT_REGISTERED");
 return handler;
}
