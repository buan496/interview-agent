import { expect, test, type Page } from "@playwright/test";

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

async function mockNavigationApis(page: Page) {
  await page.route("**/api/me/wrong-book", async (route) =>
    route.fulfill({
      json: [
        {
          question_id: 100,
          title: question.title,
          last_score: 52,
          fail_count: 2,
          next_review: "2026-07-08",
          tags: metadata.tags,
        },
      ],
    })
  );
  await page.route("**/api/questions/meta", async (route) => route.fulfill({ json: metadata }));
  await page.route("**/api/me/radar", async (route) => route.fulfill({ json: [{ tag: "Redis", avg_score: 52, attempts: 2 }] }));
  await page.route("**/api/me/reports", async (route) => route.fulfill({ json: [] }));
  await page.route("**/api/questions?**", async (route) => route.fulfill({ json: { items: [question], total: 1 } }));
  await page.route("**/api/me/practice-plan/today", async (route) =>
    route.fulfill({
      json: {
        id: 1,
        date: "2026-07-06",
        generated_reason: "Navigation smoke plan.",
        completed: false,
        created_at: "2026-07-06T00:00:00Z",
        updated_at: "2026-07-06T00:00:00Z",
        weak_tags: [{ tag_id: 7, tag: "Redis", category: "knowledge", avg_score: 52, attempts: 2 }],
        target_abilities: ["Redis"],
        recommended_tasks: [],
      },
    })
  );
}

test("wrong-book can return to today training through unified navigation", async ({ page }) => {
  await mockNavigationApis(page);

  await page.goto("/wrong-book");

  await expect(page.getByRole("heading", { name: "把低分题重新拉回训练闭环" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始推荐训练" })).toBeVisible();

  await page.getByRole("link", { name: "返回今日训练" }).first().click();

  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("heading", { name: "今天，从一次高质量模拟面试开始" })).toBeVisible();
});
