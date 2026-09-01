/**
 * Zustand 登录态：user / status / quota。
 * token 不落 store（收敛于 authTokenStore 的 sessionStorage 抽象）。
 */
import { create } from "zustand";
import http from "@/api/http";
import { clearToken, getToken, setToken } from "@/api/authTokenStore";
import type { AccountType, Quota, User } from "@/types";

type AuthStatus = "unauthenticated" | "loading" | "authenticated";

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: { user_id: number; role: string };
}

interface MeResponse extends User {
  quota: Quota;
}

interface AuthState {
  user: User | null;
  quota: Quota | null;
  status: AuthStatus;
  login: (account_identifier: string, account_type: AccountType, password: string) => Promise<void>;
  register: (account_identifier: string, account_type: AccountType, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  apply401: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  quota: null,
  // 已有令牌 → 启动后需 fetchMe 拉取用户，期间为 loading（避免登录页闪跳）
  status: getToken() ? "loading" : "unauthenticated",

  login: async (account_identifier, account_type, password) => {
    const { data } = await http.post<LoginResponse>("/api/auth/login", {
      account_identifier,
      account_type,
      password,
    });
    setToken(data.access_token);
    // 拉取完整用户信息 + 配额
    const me = await http.get<MeResponse>("/api/auth/me");
    const { quota, ...user } = me.data;
    set({ user, quota, status: "authenticated" });
  },

  register: async (account_identifier, account_type, password) => {
    await http.post("/api/auth/register", {
      account_identifier,
      account_type,
      password,
    });
    // 注册成功后自动登录
    const loginRes = await http.post<LoginResponse>("/api/auth/login", {
      account_identifier,
      account_type,
      password,
    });
    setToken(loginRes.data.access_token);
    const me = await http.get<MeResponse>("/api/auth/me");
    const { quota, ...user } = me.data;
    set({ user, quota, status: "authenticated" });
  },

  logout: () => {
    clearToken();
    set({ user: null, quota: null, status: "unauthenticated" });
  },

  fetchMe: async () => {
    set({ status: "loading" });
    try {
      const me = await http.get<MeResponse>("/api/auth/me");
      const { quota, ...user } = me.data;
      set({ user, quota, status: "authenticated" });
    } catch (err) {
      // 401（无有效令牌）→ 回到未登录态；其它错误保持 loading 由调用方处理
      clearToken();
      set({ user: null, quota: null, status: "unauthenticated" });
      throw err;
    }
  },

  apply401: () => {
    clearToken();
    set({ user: null, quota: null, status: "unauthenticated" });
  },
}));
