/**
 * US2 智能问答 + US3 会话列表 E2E（直连真实后端）。
 *
 * 前置：后端已在 :8000 运行（MySQL + DeepSeek 配置见根目录运行指南）。
 * 说明：知识库为空时后端返回兜底话术（不调用 LLM），知识库有数据时走完整
 * RAG 链路——两种情况下 AI 回复都会出现，用例断言「必有回复」而非具体文案。
 */
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "e2ePass1234";
const email = `e2e_chat_${Date.now()}@example.com`;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const res = await request.post("http://localhost:8000/api/auth/register", {
    data: { account_identifier: email, account_type: "email", password: PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
});

async function login(page: Page, identifier = email) {
  await page.goto("/login");
  await page.getByPlaceholder("请输入手机号或邮箱").fill(identifier);
  await page.getByPlaceholder("请输入密码").fill(PASSWORD);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
}

/** 注册一个全新账号并登录（会话/消息计数独立，避免与其它用例共用账号相互污染） */
async function registerAndLogin(page: Page) {
  const freshEmail = `e2e_chat_fresh_${Date.now()}@example.com`;
  const res = await page.request.post("http://localhost:8000/api/auth/register", {
    data: { account_identifier: freshEmail, account_type: "email", password: PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
  await login(page, freshEmail);
  return freshEmail;
}

test("US2-问答：提问收到回复（兜底话术或 AI 回答），发送按钮恢复", async ({ page }) => {
  await login(page);
  await expect(page.getByText(/您好，我是 Nexus 智能客服/)).toBeVisible();

  const question = "请问退货政策是什么？";
  await page.getByPlaceholder(/请输入您的问题/).fill(question);
  await page.keyboard.press("Enter");

  // 用户消息上屏
  await expect(page.getByText(question)).toBeVisible();
  // AI 回复出现（真实 LLM 流式可能较慢，放宽到 60s）
  const aiBubble = page.locator(".message-bubble--ai");
  await expect(aiBubble.first()).toBeVisible({ timeout: 60_000 });
  // 流式结束：停止按钮消失、发送按钮恢复
  await expect(page.getByRole("button", { name: "发送" })).toBeVisible({ timeout: 60_000 });
});

test("US3-会话：首条提问自动生成标题，刷新后历史回读", async ({ page }) => {
  // 用全新账号登录：US2 已用共享账号建过会话，若沿用会导致列表数量 >1 断言失败
  await registerAndLogin(page);

  // 新建会话 → 空态提示
  await page.getByRole("button", { name: "新建会话" }).click();
  await expect(page.getByText(/新会话开始/)).toBeVisible();

  const question = "请介绍下你们的配送时效";
  await page.getByPlaceholder(/请输入您的问题/).fill(question);
  await page.keyboard.press("Enter");
  // 等流式结束
  await expect(page.getByRole("button", { name: "发送" })).toBeVisible({ timeout: 60_000 });

  // 左侧会话列表出现 1 个会话项，标题已由首条提问自动生成（非「新会话」占位）
  await expect(page.locator("aside div[role='button']")).toHaveCount(1);
  await expect(page.locator("aside").getByText("新会话", { exact: true })).toHaveCount(0);

  // 刷新：会话保留、历史消息回读
  await page.reload();
  await expect(page.getByText(question)).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".message-bubble--ai").first()).toBeVisible();
});
