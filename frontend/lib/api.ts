import type { CreateSessionResponse, Metadata, Question, SessionDetail } from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function getMetadata() {
  return request<Metadata>("/questions/meta");
}

export function getQuestions(params: URLSearchParams) {
  return request<{ items: Question[]; total: number }>(`/questions?${params.toString()}`);
}

export function createSession(payload: {
  mode: "single";
  company_id?: number;
  position_id?: number;
  tag_ids?: number[];
  difficulty?: number;
}) {
  return request<CreateSessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getSession(sessionId: string) {
  return request<SessionDetail>(`/sessions/${sessionId}`);
}

