/**
 * 管理端布局（US5）：左侧导航（知识库管理 / 返回问答）+ 内容区（Outlet 子路由）。
 */
import { Layout, Menu } from "antd";
import { DatabaseOutlined, MessageOutlined } from "@ant-design/icons";
import { Outlet, useNavigate } from "react-router-dom";

export default function AdminLayout() {
  const navigate = useNavigate();

  // 当前仅知识库一个管理子页，直接高亮对应菜单项
  const selectedKey = "/admin/knowledge";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider theme="light" width={220} style={{ borderRight: "1px solid rgba(0,0,0,0.06)" }}>
        <div style={{ padding: "16px 24px", fontWeight: 600, fontSize: 16 }}>
          Nexus 管理端
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={[
            { key: "/admin/knowledge", icon: <DatabaseOutlined />, label: "知识库管理" },
            { key: "/chat", icon: <MessageOutlined />, label: "返回问答" },
          ]}
          onClick={({ key }) => navigate(key)}
        />
      </Layout.Sider>
      <Layout.Content style={{ padding: 24, background: "#f5f6fa" }}>
        <Outlet />
      </Layout.Content>
    </Layout>
  );
}
