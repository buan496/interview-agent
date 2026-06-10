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
  company?: Company | null;
  position?: Position | null;
  tags: Tag[];
};

export type CreateSessionResponse = {
  session_id: number;
  first_question: {
    sq_id: number;
    title: string;
    body?: string | null;
    difficulty: number;
    qtype: string;
    tags: Tag[];
  };
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
  questions: Array<{
    sq_id: number;
    question: CreateSessionResponse["first_question"];
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
  next_question?: unknown;
};

