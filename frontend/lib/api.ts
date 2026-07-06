import type { CreateSessionResponse, Metadata, Question, SessionDetail, SessionReport, Submission } from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export function authHeader(): Record<string, string> {
  const token = typeof window === "undefined" ? null : window.localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
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

export function requestLoginCode(phone: string) {
  return request<{ status: string; expires_in: number; development_code?: string }>("/auth/request-code", {
    method: "POST",
    body: JSON.stringify({ phone })
  });
}

export function login(phone: string, code: string) {
  return request<{ access_token: string; token_type: string; expires_in: number }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ phone, code })
  });
}

export function getMetadata() {
  return request<Metadata>("/questions/meta");
}

export function getQuestions(params: URLSearchParams) {
  return request<{ items: Question[]; total: number }>(`/questions?${params.toString()}`);
}

export function createSession(payload: {
  mode: "single" | "mock";
  question_id?: number;
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

export function getReport(sessionId: string) {
  return request<SessionReport>(`/sessions/${sessionId}/report`);
}

export function getWrongBook() {
  return request<
    Array<{
      question_id: number;
      title: string;
      last_score?: number | null;
      fail_count: number;
      next_review?: string | null;
      tags: Array<{ id: number; name: string }>;
    }>
  >("/me/wrong-book");
}

export function createSubmission(payload: {
  submitter_name?: string;
  company_name: string;
  position_name: string;
  title: string;
  body?: string;
  answer_key: string;
  difficulty: number;
  qtype: string;
  tags: string[];
}) {
  return request<Submission>("/submissions", { method: "POST", body: JSON.stringify(payload) });
}

export function getSubmissions(status = "pending_review") {
  return request<Submission[]>(`/admin/submissions?status=${encodeURIComponent(status)}`);
}

export function reviewSubmission(id: number, action: "approve" | "reject", note?: string) {
  return request<Submission>(`/admin/submissions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ action, note })
  });
}

export function generateFromJd(payload: { jd_text: string; company: string; position: string; count: number }) {
  return request<{ items: Submission[] }>("/admin/generate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
