import type { ThemeConfig } from "antd";

/**
 * AntD 主题令牌单一来源（对齐 contracts/design-system.md 企业专业浅色风）。
 * 全站颜色/圆角/字号/间距均从本 token 派生，禁止内联硬编码（SC-009）。
 */
export const themeConfig: ThemeConfig = {
  token: {
    // 品牌主色
    colorPrimary: "#2F6BFF",
    // 语义色
    colorSuccess: "#52c41a",
    colorWarning: "#faad14",
    colorError: "#ff4d4f",
    // 背景/文本层级
    colorBgLayout: "#f5f6fa",
    colorBgContainer: "#ffffff",
    colorText: "rgba(0, 0, 0, 0.88)",
    colorTextSecondary: "rgba(0, 0, 0, 0.65)",
    // 圆角 / 字号
    borderRadius: 8,
    fontSize: 14,
    // 间距体系（AntD 默认 8px 基数）
    controlHeight: 36,
  },
  components: {
    Layout: {
      headerBg: "#ffffff",
      headerHeight: 56,
    },
  },
};
