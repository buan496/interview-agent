import { request } from "@/lib/api-client";
import type { TrainingHistoryItem } from "@/lib/types";

export function getTrainingHistory(params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<TrainingHistoryItem[]>(`/sessions/history${suffix}`);
}
