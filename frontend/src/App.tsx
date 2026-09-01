/**
 * 根组件：装配 QueryClientProvider、AntD ConfigProvider（主题 token）、
 * AntD App（全局 message/modal 宿主）、Router。
 * 启动时若 sessionStorage 有令牌则拉取用户信息恢复登录态。
 */
import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { router } from "@/router";
import { themeConfig } from "@/styles/theme";
import { getToken } from "@/api/authTokenStore";
import { useAuthStore } from "@/stores/auth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    if (getToken()) {
      // 401（过期/无效令牌）由 http 拦截器统一清理并跳登录
      fetchMe().catch(() => {
        /* 已由拦截器处理 */
      });
    }
  }, [fetchMe]);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={themeConfig}
        button={{ autoInsertSpace: false }}
      >
        <AntApp>
          <RouterProvider router={router} />
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
