/**
 * US1 注册/登录 E2E（直连真实后端）。
 *
 * 前置：后端已在 :8000 运行（MySQL + DeepSeek 配置见根目录运行指南）。
 * 用户数据：beforeAll 通过 API 注册一个固定测试账号；UI 注册用例另注册唯一账号。
 */
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "e2ePass1234";
const email = `e2e_auth_${Date.now()}@example.com`;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const res = await request.post("http://localhost:8000/api/auth/register", {
    data: { account_identifier: email, account_type: "email", password: PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
});

async function login(page: Page, identifier: string, password: string) {
  await page.goto("/login");
  await page.getByPlaceholder("请输入手机号或邮箱").fill(identifier);
  await page.getByPlaceholder("请输入密码").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
}

test("US1-注册：注册成功自动登录进入主界面", async ({ page }) => {
  const uiEmail = `e2e_ui_${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByPlaceholder("请输入手机号或邮箱").fill(uiEmail);
  await page.getByPlaceholder("至少 8 位密码").fill(PASSWORD);
  await page.getByPlaceholder("再次输入密码").fill(PASSWORD);
  await page.getByRole("button", { name: "注册", exact: true }).click();

  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByText(uiEmail)).toBeVisible();
});

test("US1-退出：登录后点击退出回到登录页", async ({ page }) => {
  await login(page, email, PASSWORD);
  await expect(page).toHaveURL(/\/chat$/);
  await page.getByRole("button", { name: "退出" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("US1-登录：用已注册账号重新登录", async ({ page }) => {
  await login(page, email, PASSWORD);
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByText(email)).toBeVisible();
});

test("US1-登录失败：错误密码提示且停留登录页", async ({ page }) => {
  await login(page, email, "WrongPass000");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.locator(".ant-message")).toContainText(/密码错误|登录失败/i);
});
