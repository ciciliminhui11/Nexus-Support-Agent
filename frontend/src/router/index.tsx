/**
 * 路由表 + 守卫：
 * - RequireAuth：未登录 → /login?redirect=…，loading 态显示加载
 * - AdminOnly：非 admin → 首页（知识库管理端后续故事使用）
 * 已登录访问 /login、/register → /chat
 */
import type { ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import { Spin } from "antd";
import NotFound from "@/pages/NotFound";
import LoginPage from "@/pages/login/LoginPage";
import RegisterPage from "@/pages/login/RegisterPage";
import ChatPage from "@/pages/chat/ChatPage";
import AdminLayout from "@/pages/admin/AdminLayout";
import KnowledgePage from "@/pages/admin/KnowledgePage";
import { useAuthStore } from "@/stores/auth";

function FullPageLoading() {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Spin size="large" />
    </div>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status);
  if (status === "loading") return <FullPageLoading />;
  if (status !== "authenticated") {
    const path = window.location.pathname;
    // 退出瞬间（logout() 清状态 + navigate）守卫与路由切换存在竞态：此时 pathname
    // 可能已是 /login，若仍拼接 redirect 会生成自指跳转 /login?redirect=/login。
    // 目标已是公开页时直接去干净 /login，不追加 redirect（与 http.ts 401 处理一致）。
    if (path.startsWith("/login") || path.startsWith("/register")) {
      return <Navigate to="/login" replace />;
    }
    const redirect = encodeURIComponent(path + window.location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  return <>{children}</>;
}

export function AdminOnly({ children }: { children: ReactNode }) {
  const role = useAuthStore((s) => s.user?.role);
  if (role !== "admin") return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status);
  if (status === "authenticated") return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/chat" replace /> },
  {
    path: "/login",
    element: (
      <GuestOnly>
        <LoginPage />
      </GuestOnly>
    ),
  },
  {
    path: "/register",
    element: (
      <GuestOnly>
        <RegisterPage />
      </GuestOnly>
    ),
  },
  {
    path: "/chat",
    element: (
      <RequireAuth>
        <ChatPage />
      </RequireAuth>
    ),
  },
  {
    path: "/admin",
    element: (
      <RequireAuth>
        <AdminOnly>
          <AdminLayout />
        </AdminOnly>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/admin/knowledge" replace /> },
      { path: "knowledge", element: <KnowledgePage /> },
    ],
  },
  { path: "*", element: <NotFound /> },
]);
