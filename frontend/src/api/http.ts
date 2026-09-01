/**
 * axios 实例：注入 Bearer 令牌、401 → 清登录态并跳登录、契约错误码映射。
 */
import axios, { AxiosError } from "axios";
import { clearToken, getToken } from "./authTokenStore";
import type { ApiErrorBody } from "@/types";

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

const http = axios.create({
  baseURL: API_BASE,
  timeout: 20_000,
  headers: { "Content-Type": "application/json" },
});

// 请求拦截：注入 JWT
http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** 统一的业务错误：code/message 来自后端契约 `{code, message}` */
export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function extractError(error: AxiosError<ApiErrorBody>): ApiError {
  const data = error.response?.data;
  const status = error.response?.status ?? 0;
  return new ApiError(data?.code ?? "network_error", data?.message ?? "网络异常，请稍后重试", status);
}

// 响应拦截：401 统一清登录态并跳登录
http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      clearToken();
      const current = window.location.pathname;
      if (!current.startsWith("/login") && !current.startsWith("/register")) {
        window.location.href = `/login?redirect=${encodeURIComponent(current + window.location.search)}`;
      }
    }
    return Promise.reject(extractError(error));
  },
);

export default http;
