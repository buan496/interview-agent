import { request } from "@/lib/api-client";
import type { Submission } from "@/lib/types";

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
