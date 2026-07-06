import { expect, test } from "@playwright/test";

import { fulfillCreateSession, mockBaseApis, question, sessionDetail } from "./helpers/core-fixtures";

test("global navigation links practice, wrong-book, and mock routes", async ({ page }) => {
  await mockBaseApis(page);

  await page.goto("/practice");
  const nav = page.locator("nav");

  await nav.getByRole("link", { name: "错题本" }).click();
  await expect(page).toHaveURL(/\/wrong-book$/);
  await expect(page.getByRole("heading", { name: "把低分题重新拉回训练闭环" })).toBeVisible();

  await nav.getByRole("link", { name: "今日训练", exact: true }).click();
  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("heading", { name: "今天，从一次高质量模拟面试开始" })).toBeVisible();

  await nav.getByRole("link", { name: "模拟面试" }).click();
  await expect(page).toHaveURL(/\/mock$/);
  await expect(page.getByRole("button", { name: "开始模拟面试" })).toBeVisible();
});

test("wrong-book can return to today training through page action", async ({ page }) => {
  await mockBaseApis(page);

  await page.goto("/wrong-book");

  await expect(page.getByRole("heading", { name: "把低分题重新拉回训练闭环" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始推荐训练" })).toBeVisible();

  await page.getByRole("link", { name: "返回今日训练" }).first().click();

  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("heading", { name: "今天，从一次高质量模拟面试开始" })).toBeVisible();
});

test("wrong-book retry creates a single-question session", async ({ page }) => {
  await mockBaseApis(page);
  let requestBody: unknown;

  await page.route("**/api/sessions", async (route) => {
    requestBody = route.request().postDataJSON();
    await fulfillCreateSession(route, 88);
  });
  await page.route("**/api/sessions/88", async (route) => route.fulfill({ json: sessionDetail(88) }));

  await page.goto("/wrong-book");
  await page.getByRole("button", { name: "重新训练" }).click();

  await expect.poll(() => requestBody).toEqual({ mode: "single", question_id: question.id });
  await expect(page).toHaveURL(/\/session\/88$/);
  await expect(page.getByText(question.title).first()).toBeVisible();
});

test("mobile navigation is visible and does not overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockBaseApis(page);

  await page.goto("/practice");
  const nav = page.locator("nav");

  await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
  await expect(nav.getByRole("link", { name: "今日训练", exact: true })).toBeVisible();
  await expect(nav.getByRole("link", { name: "错题本" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "模拟面试" })).toBeVisible();
  await expect.poll(async () => page.evaluate(() => document.body.scrollWidth <= window.innerWidth)).toBe(true);

  await nav.getByRole("link", { name: "错题本" }).click();

  await expect(page).toHaveURL(/\/wrong-book$/);
  await expect(page.getByRole("heading", { name: "把低分题重新拉回训练闭环" })).toBeVisible();
  await expect.poll(async () => page.evaluate(() => document.body.scrollWidth <= window.innerWidth)).toBe(true);
});
