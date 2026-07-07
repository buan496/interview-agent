import { expect, test } from "@playwright/test";

import { mockBaseApis, sessionDetail, trainingHistory } from "./helpers/core-fixtures";

test("history page shows current-user training records and opens report or session", async ({ page }) => {
  await mockBaseApis(page);
  await page.route("**/api/sessions/43", async (route) => route.fulfill({ json: sessionDetail(43) }));

  await page.goto("/history");

  await expect(page.getByRole("heading", { name: "历史训练记录" })).toBeVisible();
  await expect(page.getByText("Why is Redis fast?").first()).toBeVisible();
  await expect(page.getByText("82 分")).toBeVisible();

  await page.getByRole("link", { name: "查看报告" }).click();
  await expect(page).toHaveURL(/\/report\/42$/);
  await expect(page.getByText("Why is Redis fast?").first()).toBeVisible();
  await expect(page.getByText("82").first()).toBeVisible();

  await page.goto("/history");
  await page.getByRole("link", { name: "继续训练" }).click();
  await expect(page).toHaveURL(/\/session\/43$/);
  await expect(page.getByText("Why is Redis fast?").first()).toBeVisible();
});

test("history page shows empty state and mobile layout does not overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockBaseApis(page);
  await page.route("**/api/sessions/history**", async (route) => route.fulfill({ json: [] }));

  await page.goto("/history");

  await expect(page.getByText("还没有训练历史")).toBeVisible();
  await expect(page.getByRole("link", { name: "去今日训练" }).first()).toBeVisible();
  await expect.poll(async () => page.evaluate(() => document.body.scrollWidth <= window.innerWidth)).toBe(true);
});

test("history navigation entry is available from global nav", async ({ page }) => {
  await mockBaseApis(page);

  await page.goto("/practice");
  await page.locator("nav").getByRole("link", { name: "训练历史" }).click();

  await expect(page).toHaveURL(/\/history$/);
  await expect(page.getByRole("heading", { name: "历史训练记录" })).toBeVisible();
  await expect.poll(() => trainingHistory.length).toBe(2);
});
