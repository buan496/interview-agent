import { request } from "@/lib/api-client";
import type { Metadata, Question } from "@/lib/types";

export function getMetadata() {
  return request<Metadata>("/questions/meta");
}

export function getQuestions(params: URLSearchParams) {
  return request<{ items: Question[]; total: number }>(`/questions?${params.toString()}`);
}
