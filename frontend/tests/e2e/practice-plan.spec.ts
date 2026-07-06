import { expect, test, type Page } from "@playwright/test";

import type { PracticePlan } from "../../lib/types";

const metadata = {
  companies: [{ id: 1, name: "General Co", region: "CN", tier: 1 }],
  positions: [{ id: 2, name: "AI Engineer" }],
  tags: [{ id: 7, name: "Redis", category: "knowledge" }],
};

const question = {
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

function sessionDetail(sessionId: number) {
  return {
    session_id: sessionId,
    mode: "single",
    status: "ongoing",
    server_now: "2026-07-06T00:00:00Z",
    started_at: "2026-07-06T00:00:00Z",
    deadline_at: "2026-07-06T00:20:00Z",
    remaining_seconds: 1200,
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
        status: "answering",
        started_at: "2026-07-06T00:00:00Z",
        submitted_at: null,
        scored_at: null,
        followup_count: 0,
        final_score: null,
        mastery: null,
        messages: [{ id: 1, role: "interviewer", content: question.title, msg_type: "question" }],
      },
    ],
  };
}

const practicePlan: PracticePlan = {
  id: 1,
  date: "2026-07-06",
  generated_reason: "Generated from unfinished sessions, wrong answers, and weak tags.",
  completed: false,
  created_at: "2026-07-06T00:00:00Z",
  updated_at: "2026-07-06T00:00:00Z",
  weak_tags: [{ tag_id: 7, tag: "Redis", category: "knowledge", avg_score: 52, attempts: 2 }],
  target_abilities: ["Redis"],
  recommended_tasks: [
    {
      id: "resume-session-42",
      type: "resume_session",
      title: "Resume unfinished session",
      reason: "You have an in-progress single-question session.",
      outcome: "Finish the already-started training before starting a new one.",
      action_label: "Continue training",
      entrypoint: "open_page",
      payload: { session_id: 42, href: "/session/42" },
    },
    {
      id: "weak-tag-training",
      type: "weak_tag_training",
      title: "Weak tag focus",
      reason: "Redis is currently averaging 52 and should be reinforced.",
      outcome: "Run single-question practice to refresh the ability radar.",
      action_label: "Start focus",
      entrypoint: "create_session",
      payload: { mode: "single", tag_ids: [7] },
    },
  ],
};

async function mockPracticeApis(page: Page, plan = practicePlan) {
  await page.route("**/api/questions/meta", async (route) => route.fulfill({ json: metadata }));
  await page.route("**/api/me/wrong-book", async (route) => route.fulfill({ json: [] }));
  await page.route("**/api/me/radar", async (route) =>
    route.fulfill({ json: [{ tag: "Redis", avg_score: 52, attempts: 2 }] })
  );
  await page.route("**/api/me/reports", async (route) => route.fulfill({ json: [] }));
  await page.route("**/api/questions?**", async (route) => route.fulfill({ json: { items: [question], total: 1 } }));
  await page.route("**/api/me/practice-plan/today", async (route) =>
    route.fulfill({
      json: plan,
    })
  );
  await page.route("**/api/sessions/42", async (route) => route.fulfill({ json: sessionDetail(42) }));
  await page.route("**/api/sessions/88", async (route) => route.fulfill({ json: sessionDetail(88) }));
}

test("shows backend-owned practice plan and resumes unfinished session", async ({ page }) => {
  await mockPracticeApis(page);

  await page.goto("/practice");

  await expect(page.getByText("Resume unfinished session")).toBeVisible();
  await expect(page.getByText("Weak tag focus")).toBeVisible();
  await expect(page.getByText("Generated from unfinished sessions, wrong answers, and weak tags.")).toBeVisible();

  await page.getByRole("button", { name: "Continue training" }).click();

  await expect(page).toHaveURL(/\/session\/42$/);
  await expect(page.getByText("Why is Redis fast?").first()).toBeVisible();
});

test("creates a session from weak-tag practice task payload", async ({ page }) => {
  await mockPracticeApis(page);
  let requestBody: unknown;
  await page.route("**/api/sessions", async (route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({
      json: {
        session_id: 88,
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
  });

  await page.goto("/practice");
  await page.getByRole("button", { name: "Start focus" }).click();

  await expect.poll(() => requestBody).toEqual({ mode: "single", tag_ids: [7] });
  await expect(page).toHaveURL(/\/session\/88$/);
});

test("starts same-question retry from report follow-up task", async ({ page }) => {
  await mockPracticeApis(page, {
    ...practicePlan,
    generated_reason: "Latest report action items are included as targeted retry tasks.",
    recommended_tasks: [
      {
        id: "evaluation-followup-5",
        type: "single_question",
        title: "Report follow-up retry",
        reason: "Latest report feedback: IO multiplexing",
        outcome: "Retry the same question so the feedback turns into updated ability data.",
        action_label: "Retry from report",
        entrypoint: "create_session",
        payload: { mode: "single", question_id: 100 },
      },
    ],
  });
  let requestBody: unknown;
  await page.route("**/api/sessions", async (route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({
      json: {
        session_id: 88,
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
  });

  await page.goto("/practice");

  await expect(page.getByText("Report follow-up retry")).toBeVisible();
  await expect(page.getByText("Latest report feedback: IO multiplexing")).toBeVisible();
  await page.getByRole("button", { name: "Retry from report" }).click();

  await expect.poll(() => requestBody).toEqual({ mode: "single", question_id: 100 });
  await expect(page).toHaveURL(/\/session\/88$/);
  await expect(page.getByText("Why is Redis fast?").first()).toBeVisible();
});
