import { expect, test } from "@playwright/test";

import { fulfillAnswerSse, fulfillCreateSession, mockBaseApis, question, sessionDetail } from "./helpers/core-fixtures";

test("completes practice to session to report and returns to today training", async ({ page }) => {
  await mockBaseApis(page);

  let submitted = false;
  await page.route("**/api/sessions", async (route) => fulfillCreateSession(route, 42));
  await page.route("**/api/sessions/42", async (route) => route.fulfill({ json: sessionDetail(42, submitted ? "finished" : "ongoing") }));
  await page.route("**/api/sessions/42/answer", async (route) => {
    submitted = true;
    await fulfillAnswerSse(route);
  });

  await page.goto("/practice");
  await page.getByRole("button", { name: "开始今日训练" }).click();

  await expect(page).toHaveURL(/\/session\/42$/);
  await expect(page.getByText(question.title).first()).toBeVisible();

  await page.locator("textarea").fill("Redis is fast because it keeps data in memory and uses an event loop.");
  await page.getByRole("button", { name: "提交回答" }).click();

  await expect(page.getByText("Good structure. Add IO multiplexing").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "查看报告" }).first()).toBeVisible();

  await page.locator('a[href="/report/42"]').first().click();

  await expect(page).toHaveURL(/\/report\/42$/);
  await expect(page.getByRole("heading", { name: "本轮面试报告" })).toBeVisible();
  await expect(page.getByText("综合得分").first()).toBeVisible();
  await expect(page.getByText("题目复盘")).toBeVisible();

  await page.getByRole("link", { name: "去今日训练" }).first().click();

  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("heading", { name: "今天，从一次高质量模拟面试开始" })).toBeVisible();
});
