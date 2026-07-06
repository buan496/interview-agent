import { expect, test, type Page } from "@playwright/test";

const report = {
  session_id: 42,
  mode: "single",
  status: "finished",
  overall_score: 72,
  summary: "Good structure, but missing event-loop and memory-model details.",
  started_at: "2026-07-06T00:00:00Z",
  ended_at: "2026-07-06T00:18:00Z",
  radar: [{ tag: "Redis", avg_score: 72, attempts: 1 }],
  questions: [
    {
      sq_id: 1,
      title: "Why is Redis fast?",
      qtype: "knowledge",
      difficulty: 3,
      score: 72,
      mastery: "weak",
      feedback: "Mentioned memory access and simple data structures.",
      ideal_answer: "Cover memory access, single-threaded event loop, IO multiplexing, and optimized data structures.",
      strengths: ["Mentioned memory access"],
      missing_points: ["IO multiplexing", "single-threaded event loop"],
      expression_issues: ["Answer is too abstract"],
      action_items: ["Review and restate: IO multiplexing", "Review and restate: single-threaded event loop"],
      recommended_questions: [],
      tags: [{ id: 7, name: "Redis", category: "knowledge" }],
    },
  ],
};

async function mockReportApis(page: Page) {
  await page.route("**/api/sessions/42/report", async (route) => route.fulfill({ json: report }));
}

test("shows localized structured report review workbench", async ({ page }) => {
  await mockReportApis(page);

  await page.goto("/report/42");

  await expect(page.getByRole("heading", { name: "本轮面试报告" })).toBeVisible();
  await expect(page.getByText("下一轮优先补齐")).toBeVisible();
  await expect(page.getByText("能力诊断")).toBeVisible();
  await expect(page.getByText("题目复盘")).toBeVisible();
  await expect(page.getByText("IO multiplexing").first()).toBeVisible();
  await expect(page.getByText("Review and restate: IO multiplexing").first()).toBeVisible();
  await expect(page.getByText("Answer is too abstract")).toBeVisible();
  await expect(page.getByText("知识题")).toBeVisible();
  await expect(page.getByText("薄弱", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "去今日训练" }).first()).toHaveAttribute("href", "/practice");
});
