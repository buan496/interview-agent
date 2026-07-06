import { expect, test, type Page } from "@playwright/test";

import { mockBaseApis, sessionDetail } from "./helpers/core-fixtures";

const visualDir = "test-results/visual";

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

async function mockVisualApis(page: Page) {
  await mockBaseApis(page);
  await page.route("**/api/sessions/42", async (route) => route.fulfill({ json: sessionDetail(42) }));
}

async function capture(page: Page, name: string) {
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: `${visualDir}/${name}.png`, fullPage: true });
}

test.describe("desktop visual smoke screenshots", () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  test("captures login desktop", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByRole("heading", { name: "训练闭环，让进步可见" })).toBeVisible();
    await expect(page.getByRole("button", { name: "登录并进入训练" })).toBeVisible();

    await capture(page, "login-desktop");
  });

  test("captures practice desktop", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/practice");

    await expect(page.getByRole("heading", { name: "今天，从一次高质量模拟面试开始" })).toBeVisible();
    await expect(page.getByRole("button", { name: "开始今日训练" })).toBeVisible();

    await capture(page, "practice-desktop");
  });

  test("captures mock desktop", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/mock");

    await expect(page.getByRole("heading", { name: "模拟面试", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "开始模拟面试" }).first()).toBeVisible();

    await capture(page, "mock-desktop");
  });

  test("captures session desktop", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/session/42");

    await expect(page.getByText("单题训练 Session")).toBeVisible();
    await expect(page.getByText("Why is Redis fast?").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "提交回答" })).toBeVisible();

    await capture(page, "session-desktop");
  });

  test("captures report desktop", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/report/42");

    await expect(page.getByRole("heading", { name: "本轮面试报告" })).toBeVisible();
    await expect(page.getByText("综合得分").first()).toBeVisible();
    await expect(page.getByText("题目复盘")).toBeVisible();

    await capture(page, "report-desktop");
  });

  test("captures wrong-book desktop", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/wrong-book");

    await expect(page.getByRole("heading", { name: "把低分题重新拉回训练闭环" })).toBeVisible();
    await expect(page.getByRole("button", { name: "开始推荐训练" })).toBeVisible();

    await capture(page, "wrong-book-desktop");
  });
});

test.describe("mobile visual smoke screenshots", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("captures practice mobile", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/practice");

    await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
    await expect(page.getByRole("heading", { name: "今天，从一次高质量模拟面试开始" })).toBeVisible();
    await expect(page.getByRole("button", { name: "开始今日训练" })).toBeVisible();

    await capture(page, "practice-mobile");
  });

  test("captures mock mobile", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/mock");

    await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
    await expect(page.getByRole("heading", { name: "模拟面试", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "开始模拟面试" }).first()).toBeVisible();

    await capture(page, "mock-mobile");
  });

  test("captures session mobile", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/session/42");

    await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
    await expect(page.getByText("单题训练 Session")).toBeVisible();
    await expect(page.getByRole("button", { name: "提交回答" })).toBeVisible();

    await capture(page, "session-mobile");
  });

  test("captures report mobile", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/report/42");

    await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
    await expect(page.getByRole("heading", { name: "本轮面试报告" })).toBeVisible();
    await expect(page.getByRole("link", { name: "去今日训练" }).first()).toBeVisible();

    await capture(page, "report-mobile");
  });

  test("captures wrong-book mobile", async ({ page }) => {
    await mockVisualApis(page);
    await page.goto("/wrong-book");

    await expect(page.getByText("大厂面试训练 Agent")).toBeVisible();
    await expect(page.getByRole("heading", { name: "把低分题重新拉回训练闭环" })).toBeVisible();
    await expect(page.getByRole("button", { name: "开始推荐训练" })).toBeVisible();

    await capture(page, "wrong-book-mobile");
  });
});
