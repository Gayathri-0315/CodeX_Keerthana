export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

type Options = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal };

/** Requests index.html started before the app loaded; each is used once, by the first matching GET. */
function takeBoot(path: string): Promise<Response> | undefined {
  const boot = (window as { __boot?: Record<string, Promise<Response>> }).__boot;
  const p = boot?.[path];
  if (p) delete boot![path];
  return p;
}

export async function api<T>(path: string, { method = "GET", body, form, signal }: Options = {}): Promise<T> {
  let res: Response;
  try {
    const early = method === "GET" && !form ? takeBoot(path) : undefined;
    res = early ? await early : await fetch(`/api${path}`, {
      method: form ? "POST" : method,
      // For FormData the browser sets the multipart boundary itself.
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
      credentials: "same-origin",
      signal,
    });
  } catch (e) {
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
