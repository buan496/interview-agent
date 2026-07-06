import { request } from "@/lib/api-client";
import type { PracticePlan } from "@/lib/types";

export function getTodayPracticePlan() {
  return request<PracticePlan>("/me/practice-plan/today");
}

export function completePracticePlan(planId: number) {
  return request<PracticePlan>(`/me/practice-plan/${planId}/complete`, {
    method: "POST",
  });
}
