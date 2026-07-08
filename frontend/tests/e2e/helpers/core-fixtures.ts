import type { Page, Route } from "@playwright/test";

import type { AdminQuestion, Rubric } from "@/lib/admin-console-types";
import type { AbilityProfile, PracticePlan, SessionDetail, SessionReport, TrainingHistoryItem } from "@/lib/types";

export const metadata = {
  companies: [{ id: 1, name: "General Co", region: "CN", tier: 1 }],
  positions: [{ id: 2, name: "AI Engineer" }],
  tags: [{ id: 7, name: "Redis", category: "knowledge" }],
};

export const question = {
  id: 100,
  title: "Why is Redis fast?",
  body: null,
  difficulty: 3,
  qtype: "knowledge",
  source_type: "seed",
  source_note: null,
  company: null,
  position: null,
  tags: metadata.tags,
};

export const wrongBookItems = [
  {
    question_id: question.id,
    title: question.title,
    last_score: 52,
    fail_count: 2,
    next_review: "2026-07-08",
    tags: metadata.tags,
  },
];

export const practicePlan: PracticePlan = {
  id: 1,
  date: "2026-07-06",
  generated_reason: "Core flow smoke plan.",
  completed: false,
  created_at: "2026-07-06T00:00:00Z",
  updated_at: "2026-07-06T00:00:00Z",
  weak_tags: [{ tag_id: 7, tag: "Redis", category: "knowledge", avg_score: 52, attempts: 2 }],
  target_abilities: ["Redis"],
  recommended_tasks: [
    {
      id: "core-flow-training",
      type: "weak_tag_training",
      title: "Redis weak point training",
      reason: "Redis is currently the weakest knowledge point.",
      outcome: "Run one single-question practice and review the report.",
      action_label: "Start core flow",
      entrypoint: "create_session",
      payload: { mode: "single", tag_ids: [7] },
    },
  ],
};

export function sessionDetail(sessionId: number, status: "ongoing" | "finished" = "ongoing"): SessionDetail {
  const finished = status === "finished";
  return {
    session_id: sessionId,
    mode: "single",
    status,
    server_now: "2026-07-06T00:00:00Z",
    started_at: "2026-07-06T00:00:00Z",
    deadline_at: finished ? null : "2026-07-06T00:20:00Z",
    remaining_seconds: finished ? 0 : 1200,
    current_question_index: 1,
    total_questions: 1,
    max_followups: 3,
    current_followups: 0,
    end_reason: null,
    questions: [
      {
        sq_id: 1,
        question: {
          sq_id: 1,
          title: question.title,
          body: question.body,
          difficulty: question.difficulty,
          qtype: question.qtype,
          tags: question.tags,
        },
        status: finished ? "scored" : "answering",
        started_at: "2026-07-06T00:00:00Z",
        submitted_at: finished ? "2026-07-06T00:10:00Z" : null,
        scored_at: finished ? "2026-07-06T00:10:05Z" : null,
        followup_count: 0,
        final_score: finished ? 82 : null,
        mastery: finished ? "pass" : null,
        messages: [
          { id: 1, role: "interviewer", content: question.title, msg_type: "question" },
          ...(finished
            ? [
                { id: 2, role: "candidate" as const, content: "Redis is fast because it uses memory and an event loop.", msg_type: "answer" as const },
                {
                  id: 3,
                  role: "interviewer" as const,
                  content: "Good structure. Add IO multiplexing and data structure details.",
                  msg_type: "verdict" as const,
                  eval_json: {
                    verdict: {
                      score: 82,
                      mastery: "pass",
                      feedback: "Good structure. Add IO multiplexing and data structure details.",
                      ideal_answer: "Cover memory access, single-threaded event loop, IO multiplexing, and optimized data structures.",
                    },
                  },
                },
              ]
            : []),
        ],
      },
    ],
  };
}

export const sessionReport: SessionReport = {
  session_id: 42,
  mode: "single",
  status: "finished",
  overall_score: 82,
  summary: "Good structure with room to add event-loop and IO multiplexing details.",
  started_at: "2026-07-06T00:00:00Z",
  ended_at: "2026-07-06T00:18:00Z",
  radar: [{ tag: "Redis", avg_score: 82, attempts: 1 }],
  questions: [
    {
      sq_id: 1,
      title: question.title,
      qtype: "knowledge",
      difficulty: 3,
      score: 82,
      mastery: "pass",
      feedback: "Good structure. Add IO multiplexing and data structure details.",
      ideal_answer: "Cover memory access, single-threaded event loop, IO multiplexing, and optimized data structures.",
      strengths: ["Mentioned memory access"],
      missing_points: ["IO multiplexing"],
      expression_issues: ["Could be more specific"],
      action_items: ["Review and restate: IO multiplexing"],
      recommended_questions: [],
      tags: metadata.tags,
    },
  ],
};

export const trainingHistory: TrainingHistoryItem[] = [
  {
    session_id: 43,
    report_id: null,
    mode: "single",
    title: "Why is Redis fast?",
    status: "ongoing",
    overall_score: null,
    question_count: 1,
    started_at: "2026-07-06T01:00:00Z",
    completed_at: null,
    created_at: "2026-07-06T01:00:00Z",
    weak_tags: [],
    next_action: "continue",
  },
  {
    session_id: 42,
    report_id: 42,
    mode: "single",
    title: "Why is Redis fast?",
    status: "finished",
    overall_score: 82,
    question_count: 1,
    started_at: "2026-07-06T00:00:00Z",
    completed_at: "2026-07-06T00:18:00Z",
    created_at: "2026-07-06T00:00:00Z",
    weak_tags: ["Redis"],
    next_action: "view_report",
  },
];

export const abilityProfile: AbilityProfile = {
  overall_score: 76,
  total_sessions: 3,
  completed_sessions: 2,
  total_questions: 5,
  updated_at: "2026-07-06T00:18:00Z",
  strengths: [
    {
      tag_id: 7,
      tag: "Redis",
      category: "knowledge",
      average_score: 92,
      practice_count: 3,
      wrong_count: 0,
      mastery_level: "strong",
      last_practiced_at: "2026-07-06T00:18:00Z",
    },
  ],
  weaknesses: [
    {
      tag_id: 8,
      tag: "System Design",
      category: "ability",
      average_score: 58,
      practice_count: 2,
      wrong_count: 3,
      mastery_level: "weak",
      last_practiced_at: "2026-07-05T00:18:00Z",
    },
  ],
  tag_profiles: [
    {
      tag_id: 7,
      tag: "Redis",
      category: "knowledge",
      average_score: 92,
      practice_count: 3,
      wrong_count: 0,
      mastery_level: "strong",
      last_practiced_at: "2026-07-06T00:18:00Z",
    },
    {
      tag_id: 8,
      tag: "System Design",
      category: "ability",
      average_score: 58,
      practice_count: 2,
      wrong_count: 3,
      mastery_level: "weak",
      last_practiced_at: "2026-07-05T00:18:00Z",
    },
  ],
};

export const adminQuestion: AdminQuestion = {
  ...question,
  qtype: "knowledge",
  answer_reference: "Redis is fast because it uses memory, efficient data structures, a single-threaded event loop, and IO multiplexing.",
  status: "draft",
  default_rubric_version_id: 1,
  created_by_user_id: 1,
  updated_by_user_id: 1,
  created_at: "2026-07-06T00:00:00Z",
  updated_at: "2026-07-06T00:00:00Z",
  published_at: null,
  archived_at: null,
};

export const adminRubric: Rubric = {
  id: 1,
  name: "Agent Engineer Rubric",
  description: "Scores Agent engineering interview answers.",
  status: "published",
  created_by_user_id: 1,
  updated_by_user_id: 1,
  created_at: "2026-07-06T00:00:00Z",
  updated_at: "2026-07-06T00:00:00Z",
  versions: [
    {
      id: 1,
      rubric_id: 1,
      version: "v1",
      dimensions_json: [{ name: "Correctness", weight: 40 }],
      prompt_template: "Score the answer by correctness, completeness, expression, and engineering depth.",
      scoring_scale: "0-100",
      status: "published",
      created_by_user_id: 1,
      created_at: "2026-07-06T00:00:00Z",
      published_at: "2026-07-06T00:00:00Z",
      archived_at: null,
    },
  ],
};

export async function mockBaseApis(page: Page, options?: { wrongBookEmpty?: boolean }) {
  await page.route("**/api/questions/meta", async (route) => route.fulfill({ json: metadata }));
  await page.route("**/api/me/wrong-book", async (route) => route.fulfill({ json: options?.wrongBookEmpty ? [] : wrongBookItems }));
  await page.route("**/api/me/radar", async (route) => route.fulfill({ json: [{ tag: "Redis", avg_score: 52, attempts: 2 }] }));
  await page.route("**/api/me/reports", async (route) => route.fulfill({ json: [{ session_id: 42, mode: "single", status: "finished", overall_score: 82, started_at: "2026-07-06T00:00:00Z", ended_at: "2026-07-06T00:18:00Z" }] }));
  await page.route("**/api/sessions/history**", async (route) => route.fulfill({ json: trainingHistory }));
  await page.route("**/api/me/ability-profile", async (route) => route.fulfill({ json: abilityProfile }));
  await page.route("**/api/questions?**", async (route) => route.fulfill({ json: { items: [question], total: 1 } }));
  await page.route("**/api/me/practice-plan/today", async (route) => route.fulfill({ json: practicePlan }));
  await page.route("**/api/sessions/42/report", async (route) => route.fulfill({ json: sessionReport }));
}

export async function mockAdminApis(page: Page, options?: { forbidden?: boolean }) {
  let questions: AdminQuestion[] = [adminQuestion];
  let rubrics: Rubric[] = [adminRubric];

  await page.route("**/api/admin/questions**", async (route) => {
    if (options?.forbidden) {
      await route.fulfill({ status: 403, json: { detail: "Forbidden", request_id: "admin-denied" } });
      return;
    }

    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (method === "GET") {
      const status = url.searchParams.get("status");
      const difficulty = url.searchParams.get("difficulty");
      const tag = url.searchParams.get("tag");
      const position = url.searchParams.get("position");
      const items = questions.filter((item) => {
        if (status && item.status !== status) return false;
        if (difficulty && String(item.difficulty) !== difficulty) return false;
        if (tag && !item.tags.some((value) => value.name === tag)) return false;
        if (position && item.position?.name !== position) return false;
        return true;
      });
      await route.fulfill({ json: { items, total: items.length } });
      return;
    }

    if (method === "POST" && url.pathname.endsWith("/publish")) {
      const id = Number(url.pathname.split("/").at(-2));
      const item = questions.find((value) => value.id === id) ?? questions[0];
      item.status = "published";
      item.published_at = "2026-07-06T00:05:00Z";
      await route.fulfill({ json: item });
      return;
    }

    if (method === "POST" && url.pathname.endsWith("/archive")) {
      const id = Number(url.pathname.split("/").at(-2));
      const item = questions.find((value) => value.id === id) ?? questions[0];
      item.status = "archived";
      item.archived_at = "2026-07-06T00:06:00Z";
      await route.fulfill({ json: item });
      return;
    }

    if (method === "POST") {
      const payload = request.postDataJSON();
      const created: AdminQuestion = {
        id: 200 + questions.length,
        title: payload.title,
        body: payload.prompt,
        answer_reference: payload.answer_reference,
        difficulty: payload.difficulty,
        qtype: payload.qtype,
        source_type: "managed",
        source_note: payload.source_note,
        status: payload.status ?? "draft",
        default_rubric_version_id: payload.default_rubric_version_id,
        company: payload.company_name ? { id: 11, name: payload.company_name, region: "CN" } : null,
        position: payload.position_name ? { id: 12, name: payload.position_name } : null,
        tags: (payload.tags ?? []).map((name: string, index: number) => ({ id: 300 + index, name, category: "managed" })),
        created_by_user_id: 1,
        updated_by_user_id: 1,
        created_at: "2026-07-06T00:10:00Z",
        updated_at: "2026-07-06T00:10:00Z",
        published_at: null,
        archived_at: null,
      };
      questions = [created, ...questions];
      await route.fulfill({ json: created });
      return;
    }

    if (method === "PATCH") {
      const id = Number(url.pathname.split("/").at(-1));
      const payload = request.postDataJSON();
      const item = questions.find((value) => value.id === id) ?? questions[0];
      Object.assign(item, {
        title: payload.title ?? item.title,
        body: payload.prompt ?? item.body,
        answer_reference: payload.answer_reference ?? item.answer_reference,
        difficulty: payload.difficulty ?? item.difficulty,
        qtype: payload.qtype ?? item.qtype,
        source_note: payload.source_note ?? item.source_note,
        default_rubric_version_id: payload.default_rubric_version_id ?? item.default_rubric_version_id,
      });
      await route.fulfill({ json: item });
      return;
    }

    await route.fallback();
  });

  await page.route("**/api/admin/rubrics**", async (route) => {
    if (options?.forbidden) {
      await route.fulfill({ status: 403, json: { detail: "Forbidden", request_id: "admin-denied" } });
      return;
    }

    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (method === "GET") {
      const status = url.searchParams.get("status");
      const items = status ? rubrics.filter((item) => item.status === status) : rubrics;
      await route.fulfill({ json: { items, total: items.length } });
      return;
    }

    if (method === "POST" && /\/versions$/.test(url.pathname)) {
      const rubricId = Number(url.pathname.split("/").at(-2));
      const payload = request.postDataJSON();
      const rubric = rubrics.find((item) => item.id === rubricId) ?? rubrics[0];
      const created = {
        id: 50 + rubric.versions.length,
        rubric_id: rubric.id,
        version: payload.version,
        dimensions_json: payload.dimensions_json,
        prompt_template: payload.prompt_template,
        scoring_scale: payload.scoring_scale,
        status: "draft" as const,
        created_by_user_id: 1,
        created_at: "2026-07-06T00:12:00Z",
        published_at: null,
        archived_at: null,
      };
      rubric.versions = [created, ...rubric.versions];
      await route.fulfill({ json: created });
      return;
    }

    if (method === "POST") {
      const payload = request.postDataJSON();
      const created: Rubric = {
        id: 20 + rubrics.length,
        name: payload.name,
        description: payload.description,
        status: payload.status ?? "draft",
        created_by_user_id: 1,
        updated_by_user_id: 1,
        created_at: "2026-07-06T00:11:00Z",
        updated_at: "2026-07-06T00:11:00Z",
        versions: [],
      };
      rubrics = [created, ...rubrics];
      await route.fulfill({ json: created });
      return;
    }

    await route.fallback();
  });

  await page.route("**/api/admin/rubric-versions/**", async (route) => {
    if (options?.forbidden) {
      await route.fulfill({ status: 403, json: { detail: "Forbidden", request_id: "admin-denied" } });
      return;
    }

    const request = route.request();
    const url = new URL(request.url());
    const versionId = Number(url.pathname.split("/").at(-2));
    const version = rubrics.flatMap((item) => item.versions).find((item) => item.id === versionId) ?? rubrics[0].versions[0];
    if (url.pathname.endsWith("/publish")) {
      version.status = "published";
      version.published_at = "2026-07-06T00:13:00Z";
    }
    if (url.pathname.endsWith("/archive")) {
      version.status = "archived";
      version.archived_at = "2026-07-06T00:14:00Z";
    }
    await route.fulfill({ json: version });
  });
}

export function fulfillCreateSession(route: Route, sessionId = 42) {
  return route.fulfill({
    json: {
      session_id: sessionId,
      status: "ongoing",
      server_now: "2026-07-06T00:00:00Z",
      deadline_at: "2026-07-06T00:20:00Z",
      remaining_seconds: 1200,
      first_question: {
        sq_id: 1,
        title: question.title,
        body: question.body,
        difficulty: question.difficulty,
        qtype: question.qtype,
        tags: question.tags,
      },
    },
  });
}

export function fulfillAnswerSse(route: Route) {
  return route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body: [
      'event: token\ndata: {"text":"Good structure. Add IO multiplexing."}',
      'event: done\ndata: {"action":"done","sq_state":"DONE","verdict":{"score":82,"mastery":"pass","feedback":"Good structure. Add IO multiplexing and data structure details.","ideal_answer":"Cover memory access, single-threaded event loop, IO multiplexing, and optimized data structures."}}',
      "",
    ].join("\n\n"),
  });
}
