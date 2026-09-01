import { defineConfig, devices } from "@playwright/test";

// E2E 配置：直连真实后端（验收走全链路）。
//
// 前置条件（运行方式见 frontend/README.md 与根目录运行指南）：
//   1. MySQL 已启动，后端依赖已安装
//   2. 后端已在本机 8000 端口运行（npm run dev 的 API_BASE=http://localhost:8000 直连）
//
// 说明：MVP 阶段仅启动 Vite dev server；后端需单独拉起（playwright 不负责
// MySQL / DeepSeek 等环境装配）。`mock:sse` 服务仅供无后端时本地调试问答流，
// 不参与 E2E。
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      // channel: "chrome" 用系统已装的 Google Chrome（本机 152.x），免去 npx playwright install
      // 下载 200MB 浏览器二进制（官方 CDN 国内不可达，镜像 ~35KB/s 不现实）。
      // 如改用 Playwright 自带 chromium，删掉本行并执行 `npx playwright install chromium`。
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
  webServer: [
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
