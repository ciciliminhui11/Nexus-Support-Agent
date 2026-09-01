/**
 * JWT 读写抽象（v1 存 sessionStorage）。
 *
 * 生产硬化路径：升级 httpOnly Cookie + 刷新令牌（服务端控制），
 * 仅需替换本模块实现，上层 http/sse 不感知。
 */
const TOKEN_KEY = "nexus_auth_token";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // SSR/隐私模式下访问可能抛异常
  }
}

export function setToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}
