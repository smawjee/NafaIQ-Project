/**
 * Client error capture.
 *
 * Before this, a crash in the app reached `console.error` in the user's own
 * browser and nowhere else — nobody found out unless they emailed support.
 *
 * Three rules, because error reporting that misbehaves is worse than none:
 *   1. It must never throw. It runs on the failure path; an exception here
 *      turns a handled error into a broken page.
 *   2. It must never loop. A reporting failure must not report itself.
 *   3. It must never block. Fire-and-forget, `keepalive` so a report survives
 *      the navigation that a crash often triggers.
 */
import { apiUrl } from "@/lib/api";

const ENDPOINT = "/api/telemetry/errors";

/** Build id, so an error can be tied to the deploy that introduced it. */
const APP_VERSION =
  (import.meta as { env?: Record<string, string> }).env?.VITE_APP_VERSION ?? "dev";

/**
 * Client-side de-dup. A render loop can throw the same error dozens of times a
 * second; the server rate-limits too, but there's no reason to spend the user's
 * bandwidth finding that out.
 */
const seen = new Map<string, number>();
const DEDUP_WINDOW_MS = 60_000;
const MAX_PER_SESSION = 25;
let sent = 0;

/** Guards rule 2 — set while a report is in flight. */
let reporting = false;

function shouldSend(key: string): boolean {
  if (sent >= MAX_PER_SESSION) return false;
  const now = Date.now();
  const last = seen.get(key);
  if (last && now - last < DEDUP_WINDOW_MS) return false;
  seen.set(key, now);
  if (seen.size > 100) {
    for (const [k, t] of seen) if (now - t > DEDUP_WINDOW_MS) seen.delete(k);
  }
  return true;
}

export function reportError(
  error: unknown,
  context?: { route?: string; componentStack?: string },
): void {
  try {
    if (reporting) return;

    const err = error instanceof Error ? error : new Error(String(error));
    const message = (err.message || "Unknown error").slice(0, 2000);
    const route = context?.route ?? window.location.pathname;

    // Key on message + route only: the stack varies by line between builds, so
    // including it would defeat de-dup after every deploy.
    if (!shouldSend(`${message}|${route}`)) return;

    const stack = [err.stack, context?.componentStack].filter(Boolean).join("\n\n").slice(0, 20000);

    reporting = true;
    sent += 1;

    void fetch(apiUrl(ENDPOINT), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Survives an unload — a crash frequently precedes a navigation away.
      keepalive: true,
      body: JSON.stringify({ message, stack: stack || undefined, route, app_version: APP_VERSION }),
    })
      .catch(() => {
        // Swallowed on purpose (rule 2): if telemetry is down, the user's
        // actual problem is not "telemetry is down".
      })
      .finally(() => {
        reporting = false;
      });
  } catch {
    // Rule 1.
  }
}

/**
 * Attach global handlers for errors React never sees — event handlers, async
 * callbacks, and rejected promises, which an ErrorBoundary cannot catch.
 *
 * Returns a teardown function.
 */
export function installGlobalErrorReporting(): () => void {
  const onError = (event: ErrorEvent) => {
    reportError(event.error ?? event.message, { route: window.location.pathname });
  };
  const onRejection = (event: PromiseRejectionEvent) => {
    reportError(event.reason, { route: window.location.pathname });
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}
