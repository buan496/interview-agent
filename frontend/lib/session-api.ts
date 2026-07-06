import { request, requestForm, requestStream } from "@/lib/api-client";
import type { CreateSessionResponse, SessionDetail } from "@/lib/types";

export type CreateSessionPayload = {
  mode: "single" | "mock";
  question_id?: number;
  company_id?: number;
  position_id?: number;
  tag_ids?: number[];
  difficulty?: number;
};

export function createSession(payload: CreateSessionPayload) {
  return request<CreateSessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getSession(sessionId: string) {
  return request<SessionDetail>(`/sessions/${sessionId}`);
}

export function submitAnswer(sessionId: string, payload: { sq_id: number; content: string }) {
  return requestStream(`/sessions/${sessionId}/answer`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function transcribeAudio(file: Blob, filename = "answer.webm") {
  const form = new FormData();
  form.append("file", file, filename);
  return requestForm<{ text: string }>("/audio/transcribe", form);
}
