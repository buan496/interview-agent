export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem("access_token");
}

export function clearToken() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem("access_token");
  }
}

export function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(response: Response): Promise<ApiError> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const payload = await response.json().catch(() => null);
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : payload;
    return new ApiError(typeof detail === "string" ? detail : response.statusText, response.status, detail);
  }
  const text = await response.text().catch(() => "");
  return new ApiError(text || response.statusText, response.status, text || undefined);
}

async function ensureOk(response: Response): Promise<Response> {
  if (response.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return response;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await ensureOk(
    await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeader(),
        ...(init?.headers ?? {})
      },
      cache: "no-store"
    })
  );
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function requestForm<T>(path: string, form: FormData, init?: RequestInit): Promise<T> {
  const response = await ensureOk(
    await fetch(`${API_BASE}${path}`, {
      ...init,
      method: init?.method ?? "POST",
      headers: {
        ...authHeader(),
        ...(init?.headers ?? {})
      },
      body: form,
      cache: "no-store"
    })
  );
  return response.json() as Promise<T>;
}

export async function requestStream(path: string, init?: RequestInit): Promise<Response> {
  return ensureOk(
    await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeader(),
        ...(init?.headers ?? {})
      },
      cache: "no-store"
    })
  );
}
