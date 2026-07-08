import { expect, test } from "@playwright/test";

import { mockAdminApis } from "./helpers/core-fixtures";

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
}

test("admin can open console and reach question and rubric management", async ({ page }) => {
  await mockAdminApis(page);

  await page.goto("/admin");

  await expect(page.getByRole("heading", { name: "后台管理控制台" })).toBeVisible();
  await expect(page.getByRole("link", { name: /题库管理/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /评分标准管理/ })).toBeVisible();

  await page.getByRole("link", { name: /题库管理/ }).click();
  await expect(page).toHaveURL(/\/admin\/questions$/);
  await expect(page.getByRole("heading", { name: "题库管理" })).toBeVisible();

  await page.goto("/admin");
  await page.getByRole("link", { name: /评分标准管理/ }).click();
  await expect(page).toHaveURL(/\/admin\/rubrics$/);
  await expect(page.getByRole("heading", { name: "评分标准管理" })).toBeVisible();
});

test("admin can create, publish, and archive managed questions", async ({ page }) => {
  await mockAdminApis(page);
  let createdPayload: Record<string, unknown> | undefined;

  await page.route("**/api/admin/questions", async (route) => {
    if (route.request().method() === "POST") {
      createdPayload = route.request().postDataJSON();
    }
    await route.fallback();
  });

  await page.goto("/admin/questions");

  await expect(page.getByText("Why is Redis fast?")).toBeVisible();
  await expect(page.getByRole("button", { name: "发布" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "归档" }).first()).toBeVisible();

  await page.getByLabel("题目标题").fill("如何设计 Agent 工具调用链路？");
  await page.getByLabel("题目正文 / Prompt").fill("请说明工具选择、参数构造、错误处理和观测性。");
  await page.getByLabel("参考答案").fill("应该覆盖工具选择、schema 校验、参数生成、失败重试、request_id 观测和安全边界。");
  await page.getByPlaceholder("例如 AI Agent 工程师").fill("AI Agent 工程师");
  await page.getByPlaceholder("逗号分隔，例如 RAG, Tool Use, Redis").fill("Agent, Tool Use");
  await page.getByRole("button", { name: "创建题目" }).click();

  await expect.poll(() => createdPayload?.title).toBe("如何设计 Agent 工具调用链路？");
  await expect(page.getByText("如何设计 Agent 工具调用链路？")).toBeVisible();

  await page.getByRole("button", { name: "发布" }).first().click();
  await expect(page.locator("span").filter({ hasText: "已发布" }).first()).toBeVisible();
  await page.getByRole("button", { name: "归档" }).first().click();
  await expect(page.locator("span").filter({ hasText: "已归档" }).first()).toBeVisible();
});

test("admin can create rubric and rubric version", async ({ page }) => {
  await mockAdminApis(page);
  let rubricPayload: Record<string, unknown> | undefined;
  let versionPayload: Record<string, unknown> | undefined;

  await page.route("**/api/admin/rubrics", async (route) => {
    if (route.request().method() === "POST") {
      rubricPayload = route.request().postDataJSON();
    }
    await route.fallback();
  });
  await page.route("**/api/admin/rubrics/*/versions", async (route) => {
    if (route.request().method() === "POST") {
      versionPayload = route.request().postDataJSON();
    }
    await route.fallback();
  });

  await page.goto("/admin/rubrics");

  await expect(page.getByRole("heading", { name: "Agent Engineer Rubric" })).toBeVisible();
  await page.getByLabel("名称").fill("系统设计 Rubric");
  await page.getByLabel("描述").fill("用于系统设计和 Agent 工程题。");
  await page.getByRole("button", { name: "创建 Rubric" }).click();

  await expect.poll(() => rubricPayload?.name).toBe("系统设计 Rubric");
  await expect(page.getByRole("heading", { name: "系统设计 Rubric" })).toBeVisible();

  await page.getByLabel("版本号").fill("v2");
  await page.getByLabel("Prompt Template").fill("请按照系统设计、Agent 工程能力、表达结构和风险意识进行评分，并输出结构化建议。");
  await page.getByRole("button", { name: "创建 Version" }).click();

  await expect.poll(() => versionPayload?.version).toBe("v2");
  await expect(page.getByText("v2")).toBeVisible();
  await page.getByRole("button", { name: "发布" }).first().click();
  await expect(page.locator("span").filter({ hasText: "已发布" }).first()).toBeVisible();
  await page.getByRole("button", { name: "归档" }).first().click();
  await expect(page.locator("span").filter({ hasText: "已归档" }).first()).toBeVisible();
});

test("ordinary user sees forbidden state for admin console", async ({ page }) => {
  await mockAdminApis(page, { forbidden: true });

  await page.goto("/admin");

  await expect(page.getByRole("heading", { name: "没有后台权限" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "返回今日训练" })).toBeVisible();
});

test("content operator can access question and rubric management APIs", async ({ page }) => {
  await mockAdminApis(page);

  await page.goto("/admin/questions");
  await expect(page.getByRole("heading", { name: "题库管理" })).toBeVisible();
  await expect(page.getByText("Why is Redis fast?")).toBeVisible();

  await page.goto("/admin/rubrics");
  await expect(page.getByRole("heading", { name: "评分标准管理" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Agent Engineer Rubric" })).toBeVisible();
});

test("mobile admin overview has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockAdminApis(page);

  await page.goto("/admin");

  await expect(page.getByRole("heading", { name: "后台管理控制台" })).toBeVisible();
  await expect(page.getByRole("link", { name: /题库管理/ })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
