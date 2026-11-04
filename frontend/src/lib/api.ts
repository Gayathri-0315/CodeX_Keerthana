export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** The server's double-submit CSRF token (a readable cookie), echoed in a header on every write. */
function csrfToken(): string | undefined {
  return document.cookie.split("; ").find((c) => c.startsWith("showup_csrf="))?.slice("showup_csrf=".length);
}

type Options = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal };

/** Requests index.html started before the app loaded; each is used once, by the first matching GET. */
function takeBoot(path: string): Promise<Response> | undefined {
  const boot = (window as { __boot?: Record<string, Promise<Response>> }).__boot;
  const p = boot?.[path];
  if (p) delete boot![path];
  return p;
}

// ---- waking a sleeping server (free hosting spins down after ~15 idle minutes) ----

/** The host answers these while the app is still starting; the request never reached ShowUp. */
const WAKING_STATUS = new Set([502, 503, 504]);
const SLOW_MS = 2500; // show "Waking up the server..." when a request takes longer than this
const WAKE_DEADLINE_MS = 90_000; // a cold start takes up to about a minute; give up after 90 s

let waking = false;
let everAnswered = false;
const listeners = new Set<() => void>();
function setWaking(v: boolean) {
  if (waking === v) return;
  waking = v;
  listeners.forEach((l) => l());
}
export const wakeState = {
  get: () => waking,
  subscribe: (l: () => void) => {
    listeners.add(l);
    return () => listeners.delete(l);
  },
};

const sleep = (ms: number) => new Promise((r) => window.setTimeout(r, ms));

/**
 * fetch, but patient while the server wakes up: retries 502/503/504 (any method: the app never saw it)
 * and network errors (GET only, so a write is never sent twice) with backoff, up to 90 s.
 */
async function patientFetch(path: string, init: RequestInit, early?: Promise<Response>): Promise<Response> {
  const started = Date.now();
  const slow = everAnswered ? 0 : window.setTimeout(() => setWaking(true), SLOW_MS);
  let attempt = 0;
  try {
    for (;;) {
      let res: Response | null = null;
      let failure: unknown = null;
      try {
        res = early && attempt === 0 ? await early : await fetch(`/api${path}`, init);
      } catch (e) {
        if ((e as Error).name === "AbortError") throw e;
        failure = e;
      }
      // ShowUp's own errors are JSON; a 502/503/504 page from the host means the app isn't up yet.
      const fromHost = res && WAKING_STATUS.has(res.status) && !(res.headers.get("content-type") ?? "").includes("application/json");
      const retryable = res ? fromHost : init.method === "GET" && navigator.onLine;
      if (!retryable || Date.now() - started > WAKE_DEADLINE_MS) {
        if (res) {
          everAnswered = true;
          setWaking(false);
          return res;
        }
        throw failure;
      }
      setWaking(true);
      attempt += 1;
      await sleep(Math.min(1000 * 2 ** (attempt - 1), 5000));
    }
  } finally {
    window.clearTimeout(slow);
  }
}

export async function api<T>(path: string, { method = "GET", body, form, signal }: Options = {}): Promise<T> {
  let res: Response;
  try {
    const early = method === "GET" && !form ? takeBoot(path) : undefined;
    const verb = form ? "POST" : method;
    const headers: Record<string, string> = {};
    // For FormData the browser sets the multipart boundary itself.
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const csrf = UNSAFE.has(verb) ? csrfToken() : undefined;
    if (csrf) headers["X-CSRF-Token"] = csrf;
    res = await patientFetch(path, {
      method: verb,
      headers,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
      credentials: "same-origin",
      signal,
    }, early);
  } catch (e) {
    setWaking(false);
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "offline", "You're offline. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(res.status, data?.error?.code ?? "error", data?.error?.message ?? "Something went wrong. Try again.");
  }
  return data as T;
}
