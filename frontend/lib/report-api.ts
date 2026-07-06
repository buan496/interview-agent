import { request } from "@/lib/api-client";
import type { SessionReport } from "@/lib/types";

export function getReport(sessionId: string) {
  return request<SessionReport>(`/sessions/${sessionId}/report`);
}
