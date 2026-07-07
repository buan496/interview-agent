import { expect, test, type Page } from "@playwright/test";

import { mockBaseApis } from "./helpers/core-fixtures";

const emptyAbilityProfile = {
  overall_score: null,
  total_sessions: 0,
  completed_sessions: 0,
  total_questions: 0,
  updated_at: null,
  strengths: [],
  weaknesses: [],
  tag_profiles: [],
};

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const root = document.documentElement;
        return root.scrollWidth <= root.clientWidth + 1;
      })
    )
    .toBe(true);
}

test("shows ability profile with strengths, weaknesses, and tag dimensions", async ({ page }) => {
  await mockBaseApis(page);
  await page.goto("/ability");

  await expect(page.getByRole("heading", { name: "看清自己的优势和薄弱项，再决定下一轮训练" })).toBeVisible();
  await expect(page.getByText("综合得分")).toBeVisible();
  await expect(page.getByText("优势能力")).toBeVisible();
  await expect(page.getByText("薄弱能力")).toBeVisible();
  await expect(page.getByText("Redis").first()).toBeVisible();
  await expect(page.getByText("System Design").first()).toBeVisible();
  await expect(page.getByText("3 次错题").first()).toBeVisible();
});

test("navigates to ability profile from AppHeader", async ({ page }) => {
  await mockBaseApis(page);
  await page.goto("/practice");

  await page.getByRole("link", { name: /能力画像/ }).click();

  await expect(page).toHaveURL(/\/ability$/);
  await expect(page.getByRole("heading", { name: "看清自己的优势和薄弱项，再决定下一轮训练" })).toBeVisible();
});

test("shows empty ability profile state on mobile without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockBaseApis(page);
  await page.route("**/api/me/ability-profile", async (route) => route.fulfill({ json: emptyAbilityProfile }));

  await page.goto("/ability");

  await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
  await expect(page.getByRole("heading", { name: "看清自己的优势和薄弱项，再决定下一轮训练" })).toBeVisible();
  await expect(page.getByText("还没有能力画像")).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
