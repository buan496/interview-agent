import { request } from "@/lib/api-client";
import type { Submission } from "@/lib/types";

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
