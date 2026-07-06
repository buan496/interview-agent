export type Company = {
  id: number;
  name: string;
  name_en?: string | null;
  region: string;
  tier?: number | null;
  logo_url?: string | null;
};

export type Position = {
  id: number;
  name: string;
};

export type Tag = {
  id: number;
  name: string;
  category?: string | null;
};

export type Metadata = {
  companies: Company[];
  positions: Position[];
  tags: Tag[];
};

export type Question = {
  id: number;
  title: string;
  body?: string | null;
  difficulty: number;
  qtype: string;
  source_type: string;
  source_note?: string | null;
  company?: Company | null;
  position?: Position | null;
  tags: Tag[];
};

export type CreateSessionResponse = {
  session_id: number;
  status: string;
  server_now: string;
  deadline_at?: string | null;
  remaining_seconds?: number | null;
  first_question: {
    sq_id: number;
    title: string;
    body?: string | null;
    difficulty: number;
    qtype: string;
    tags: Tag[];
  };
};

export type RadarItem = {
  tag: string;
  avg_score: number;
  attempts: number;
};

export type Message = {
  id: number;
  role: "interviewer" | "candidate";
  content: string;
  msg_type: "question" | "answer" | "followup" | "hint" | "verdict";
  eval_json?: Record<string, unknown> | null;
};

export type SessionDetail = {
  session_id: number;
  mode: string;
  status: string;
  server_now: string;
  started_at?: string | null;
  deadline_at?: string | null;
  remaining_seconds?: number | null;
  current_question_index: number;
  total_questions: number;
  max_followups: number;
  current_followups: number;
  end_reason?: string | null;
  questions: Array<{
    sq_id: number;
    question: CreateSessionResponse["first_question"];
    status: string;
    started_at?: string | null;
    submitted_at?: string | null;
    scored_at?: string | null;
    followup_count: number;
    final_score?: number | null;
    mastery?: string | null;
    messages: Message[];
  }>;
};

export type Verdict = {
  score: number;
  mastery: "pass" | "weak" | "fail";
  feedback: string;
  ideal_answer: string;
};

export type SseDonePayload = {
  action: string;
  sq_state: "FOLLOWUP" | "DONE";
  verdict?: Verdict | null;
  next_question?: CreateSessionResponse["first_question"] | null;
};

export type SessionReport = {
  session_id: number;
  mode: string;
  status: string;
  overall_score: number;
  summary: string;
  started_at: string;
  ended_at?: string | null;
  radar: RadarItem[];
  questions: Array<{
    sq_id: number;
    title: string;
    qtype: string;
    difficulty: number;
    score: number;
    mastery: string;
    feedback: string;
    ideal_answer: string;
    tags: Tag[];
  }>;
};

export type ReportListItem = {
  session_id: number;
  mode: string;
  status: string;
  overall_score: number;
  started_at: string;
  ended_at?: string | null;
};

export type PracticePlanTask = {
  id: string;
  type:
    | "wrong_book_review"
    | "resume_session"
    | "weak_tag_training"
    | "mock_interview"
    | "single_question"
    | "project_expression"
    | "system_design";
  title: string;
  reason: string;
  outcome: string;
  action_label: string;
  entrypoint: "create_session" | "open_page";
  payload: {
    mode?: "single" | "mock";
    question_id?: number | null;
    company_id?: number | null;
    position_id?: number | null;
    tag_ids?: number[] | null;
    difficulty?: number | null;
    href?: string;
    session_id?: number | null;
  };
};

export type PracticePlan = {
  id: number;
  date: string;
  recommended_tasks: PracticePlanTask[];
  weak_tags: Array<{
    tag_id: number;
    tag: string;
    category?: string | null;
    avg_score: number;
    attempts: number;
  }>;
  target_abilities: string[];
  generated_reason: string;
  completed: boolean;
  created_at: string;
  updated_at?: string | null;
};

export type WrongBookItem = {
  question_id: number;
  title: string;
  last_score?: number | null;
  fail_count: number;
  next_review?: string | null;
  tags: Array<{ id: number; name: string }>;
};

export type Submission = {
  id: number;
  submitter_name?: string | null;
  company_name: string;
  position_name: string;
  title: string;
  body?: string | null;
  answer_key: string;
  difficulty: number;
  qtype: string;
  source_type: string;
  tags: Array<{ name: string; category?: string | null }>;
  status: string;
  review_note?: string | null;
  created_question_id?: number | null;
  created_at: string;
  reviewed_at?: string | null;
};
