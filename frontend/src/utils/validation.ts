/**
 * 纯函数表单校验（供 AntD Form rules 复用，无副作用、可单测）。
 * 规则与后端契约一致：手机号 `^1[3-9]\d{9}$`、密码 ≥8、问题 ≤500 字、
 * 上传类型 `.txt/.md` 且 ≤20MB。
 */

export const PHONE_REGEX = /^1[3-9]\d{9}$/;
export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_QUESTION_LENGTH = 500;
export const MAX_UPLOAD_MB = 20;
// 对齐后端上传白名单（{".txt",".md"}，见 specs/002/contracts/knowledge-api.md）
export const UPLOAD_ALLOWED_EXT = [".txt", ".md"];

export type IdentifierType = "phone" | "email";

export function isValidPhone(value: string): boolean {
  return PHONE_REGEX.test(value);
}

export function isValidEmail(value: string): boolean {
  return EMAIL_REGEX.test(value);
}

/** 判定账号标识是手机号还是邮箱（都不合法返回 null） */
export function detectIdentifierType(value: string): IdentifierType | null {
  if (isValidPhone(value)) return "phone";
  if (isValidEmail(value)) return "email";
  return null;
}

export function isValidPassword(value: string): boolean {
  return value.length >= MIN_PASSWORD_LENGTH;
}

/** 两次密码一致（用于「确认密码」校验） */
export function passwordsMatch(password: string, confirm: string): boolean {
  return password === confirm;
}

export function isValidQuestion(value: string): boolean {
  return value.trim().length > 0 && value.trim().length <= MAX_QUESTION_LENGTH;
}

export function getFileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot < 0 ? "" : filename.slice(dot).toLowerCase();
}

export function isAllowedUploadType(filename: string): boolean {
  return UPLOAD_ALLOWED_EXT.includes(getFileExtension(filename));
}

export function isWithinUploadSize(bytes: number): boolean {
  return bytes <= MAX_UPLOAD_MB * 1024 * 1024;
}
