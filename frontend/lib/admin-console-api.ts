import { request } from "@/lib/api-client";
import type {
  AdminQuestion,
  AdminQuestionFilters,
  AdminQuestionList,
  AdminQuestionPayload,
  Rubric,
  RubricList,
  RubricPayload,
  RubricVersion,
  RubricVersionPayload,
} from "@/lib/admin-console-types";

function withQuery(path: string, params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export function getAdminQuestions(filters: AdminQuestionFilters = {}) {
  return request<AdminQuestionList>(
    withQuery("/admin/questions", {
      status: filters.status,
      tag: filters.tag,
      difficulty: filters.difficulty,
      position: filters.position,
      limit: filters.limit ?? 50,
      offset: filters.offset ?? 0,
    })
  );
}

export function createAdminQuestion(payload: AdminQuestionPayload) {
  return request<AdminQuestion>("/admin/questions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAdminQuestion(id: number, payload: Partial<AdminQuestionPayload>) {
  return request<AdminQuestion>(`/admin/questions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function publishAdminQuestion(id: number) {
  return request<AdminQuestion>(`/admin/questions/${id}/publish`, { method: "POST" });
}

export function archiveAdminQuestion(id: number) {
  return request<AdminQuestion>(`/admin/questions/${id}/archive`, { method: "POST" });
}

export function getAdminRubrics(filters: { status?: string; limit?: number; offset?: number } = {}) {
  return request<RubricList>(
    withQuery("/admin/rubrics", {
      status: filters.status,
      limit: filters.limit ?? 50,
      offset: filters.offset ?? 0,
    })
  );
}

export function createAdminRubric(payload: RubricPayload) {
  return request<Rubric>("/admin/rubrics", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createAdminRubricVersion(rubricId: number, payload: RubricVersionPayload) {
  return request<RubricVersion>(`/admin/rubrics/${rubricId}/versions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function publishAdminRubricVersion(versionId: number) {
  return request<RubricVersion>(`/admin/rubric-versions/${versionId}/publish`, { method: "POST" });
}

export function archiveAdminRubricVersion(versionId: number) {
  return request<RubricVersion>(`/admin/rubric-versions/${versionId}/archive`, { method: "POST" });
}

