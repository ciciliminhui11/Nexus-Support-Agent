/**
 * 纯函数表单校验单测（与后端契约对齐：手机号、邮箱、密码、问题、上传）。
 */
import { describe, expect, it } from "vitest";
import {
  detectIdentifierType,
  getFileExtension,
  isAllowedUploadType,
  isValidEmail,
  isValidPassword,
  isValidPhone,
  isValidQuestion,
  isWithinUploadSize,
  MAX_QUESTION_LENGTH,
  MAX_UPLOAD_MB,
  MIN_PASSWORD_LENGTH,
  passwordsMatch,
} from "@/utils/validation";

describe("detectIdentifierType", () => {
  it("识别合法手机号", () => {
    expect(detectIdentifierType("13800138000")).toBe("phone");
  });

  it("识别合法邮箱", () => {
    expect(detectIdentifierType("user@example.com")).toBe("email");
  });

  it("非法输入返回 null", () => {
    expect(detectIdentifierType("12345")).toBeNull();
    expect(detectIdentifierType("")).toBeNull();
    expect(detectIdentifierType("1380013800")).toBeNull(); // 少一位
  });
});

describe("isValidPhone", () => {
  it("仅接受 1[3-9] 开头 11 位", () => {
    expect(isValidPhone("13800138000")).toBe(true);
    expect(isValidPhone("19900123456")).toBe(true);
    expect(isValidPhone("12800138000")).toBe(false);
    expect(isValidPhone("1380013800a")).toBe(false);
  });
});

describe("isValidEmail", () => {
  it("接受常规邮箱", () => {
    expect(isValidEmail("a.b+c@sub.example.com")).toBe(true);
  });
  it("拒绝缺 @ 或缺域名", () => {
    expect(isValidEmail("not-an-email")).toBe(false);
    expect(isValidEmail("a@b")).toBe(false);
  });
});

describe("isValidPassword / passwordsMatch", () => {
  it(`密码至少 ${MIN_PASSWORD_LENGTH} 位`, () => {
    expect(isValidPassword("12345678")).toBe(true);
    expect(isValidPassword("short7")).toBe(false);
  });
  it("两次输入需一致", () => {
    expect(passwordsMatch("abc12345", "abc12345")).toBe(true);
    expect(passwordsMatch("abc12345", "abc1234x")).toBe(false);
  });
});

describe("isValidQuestion", () => {
  it("空白 / 超长问题不合法", () => {
    expect(isValidQuestion("   ")).toBe(false);
    expect(isValidQuestion("")).toBe(false);
    expect(isValidQuestion("A".repeat(MAX_QUESTION_LENGTH))).toBe(true);
    expect(isValidQuestion("A".repeat(MAX_QUESTION_LENGTH + 1))).toBe(false);
  });
});

describe("上传类型与大小", () => {
  it("仅 .txt/.md（对齐后端白名单）", () => {
    expect(isAllowedUploadType("说明.txt")).toBe(true);
    expect(isAllowedUploadType("guide.MD")).toBe(true); // 大小写不敏感
    expect(isAllowedUploadType("scan.pdf")).toBe(false); // 后端不支持 .pdf
    expect(isAllowedUploadType("photo.png")).toBe(false);
    expect(isAllowedUploadType("noext")).toBe(false);
  });

  it("≤ 20MB", () => {
    expect(isWithinUploadSize(MAX_UPLOAD_MB * 1024 * 1024)).toBe(true);
    expect(isWithinUploadSize(MAX_UPLOAD_MB * 1024 * 1024 + 1)).toBe(false);
  });

  it("getFileExtension 提取小写后缀", () => {
    expect(getFileExtension("a.tar.gz")).toBe(".gz");
    expect(getFileExtension("noext")).toBe("");
  });
});
