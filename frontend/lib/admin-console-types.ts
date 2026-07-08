import type { Company, Position, Tag } from "@/lib/types";

export type AdminQuestionStatus = "draft" | "published" | "archived";
export type AdminQuestionType = "behavioral" | "knowledge" | "coding" | "system_design";

export type AdminQuestion = {
  id: number;
  title: string;
  body?: string | null;
  answer_reference: string;
  difficulty: number;
  qtype: AdminQuestionType;
  source_type: string;
  source_note?: string | null;
  status: AdminQuestionStatus;
  default_rubric_version_id?: number | null;
  company?: Company | null;
  position?: Position | null;
  tags: Tag[];
  created_by_user_id?: number | null;
  updated_by_user_id?: number | null;
  created_at: string;
  updated_at?: string | null;
  published_at?: string | null;
  archived_at?: string | null;
};

export type AdminQuestionList = {
  items: AdminQuestion[];
  total: number;
};

export type AdminQuestionPayload = {
  title: string;
  prompt?: string | null;
  answer_reference: string;
  difficulty: number;
  qtype: AdminQuestionType;
  company_name?: string | null;
  position_name?: string | null;
  tags: string[];
  source_note?: string | null;
  status?: "draft" | "published";
  default_rubric_version_id?: number | null;
};

export type AdminQuestionFilters = {
  status?: string;
  tag?: string;
  difficulty?: string;
  position?: string;
  limit?: number;
  offset?: number;
};

export type RubricStatus = "draft" | "published" | "archived";

export type RubricVersion = {
  id: number;
  rubric_id: number;
  version: string;
  dimensions_json: Array<Record<string, unknown>>;
  prompt_template: string;
  scoring_scale: string;
  status: RubricStatus;
  created_by_user_id?: number | null;
  created_at: string;
  published_at?: string | null;
  archived_at?: string | null;
};

export type Rubric = {
  id: number;
  name: string;
  description?: string | null;
  status: RubricStatus;
  created_by_user_id?: number | null;
  updated_by_user_id?: number | null;
  created_at: string;
  updated_at?: string | null;
  versions: RubricVersion[];
};

export type RubricList = {
  items: Rubric[];
  total: number;
};

export type RubricPayload = {
  name: string;
  description?: string | null;
  status: "draft" | "published";
};

export type RubricVersionPayload = {
  version: string;
  dimensions_json: Array<Record<string, unknown>>;
  prompt_template: string;
  scoring_scale: string;
};

