/**
 * 管理员配额管理页面：展示用户列表及其额度信息，支持设置用户自定义额度。
 */
import { useEffect, useState } from "react";
import { Table, Typography, InputNumber, Button, Space, Tag, App as AntApp } from "antd";
import { EditOutlined, CheckOutlined, CloseOutlined } from "@ant-design/icons";
import http from "@/api/http";

interface UserQuotaItem {
  user_id: number;
  account_identifier: string;
  account_type: string;
  role: string;
  daily_quota: number | null;
  used_today: number;
  effective_limit: number;
}

interface UserQuotaListResponse {
  total: number;
  items: UserQuotaItem[];
}

interface GlobalQuotaResponse {
  daily_quota_limit: number;
}

export default function QuotaPage() {
  const { message } = AntApp.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<UserQuotaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [globalQuota, setGlobalQuota] = useState<number>(100);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState<number | null>(null);

  const fetchData = async (p: number, ps: number) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(p));
      params.set("page_size", String(ps));
      const res = await http.get<UserQuotaListResponse>(
        `/api/admin/users?${params.toString()}`
      );
      setData(res.items);
      setTotal(res.total);
    } catch {
      // 错误已由 http 拦截器处理
    } finally {
      setLoading(false);
    }
  };

  const fetchGlobalQuota = async () => {
    try {
      const res = await http.get<GlobalQuotaResponse>("/api/admin/quota/global");
      setGlobalQuota(res.daily_quota_limit);
    } catch {
      // 错误已由 http 拦截器处理
    }
  };

  useEffect(() => {
    fetchData(page, pageSize);
    fetchGlobalQuota();
  }, []);

  const handleTableChange = (p: number, ps: number) => {
    setPage(p);
    setPageSize(ps);
    fetchData(p, ps);
  };

  const handleEdit = (userId: number, currentValue: number | null) => {
    setEditingUserId(userId);
    setEditValue(currentValue);
  };

  const handleCancelEdit = () => {
    setEditingUserId(null);
    setEditValue(null);
  };

  const handleSave = async (userId: number) => {
    try {
      await http.put(`/api/admin/users/${userId}/quota`, {
        daily_quota: editValue,
      });
      message.success("额度设置成功");
      setEditingUserId(null);
      setEditValue(null);
      fetchData(page, pageSize);
    } catch {
      // 错误已由 http 拦截器处理
    }
  };

  const columns = [
    {
      title: "用户ID",
      dataIndex: "user_id",
      width: 80,
    },
    {
      title: "账号标识",
      dataIndex: "account_identifier",
    },
    {
      title: "账号类型",
      dataIndex: "account_type",
      width: 100,
      render: (type: string) => (type === "phone" ? "手机" : "邮箱"),
    },
    {
      title: "角色",
      dataIndex: "role",
      width: 80,
      render: (role: string) => (
        <Tag color={role === "admin" ? "gold" : "blue"}>
          {role === "admin" ? "管理员" : "用户"}
        </Tag>
      ),
    },
    {
      title: "个人额度",
      dataIndex: "daily_quota",
      width: 180,
      render: (quota: number | null, record: UserQuotaItem) => {
        if (editingUserId === record.user_id) {
          return (
            <Space>
              <InputNumber
                min={1}
                max={10000}
                value={editValue ?? undefined}
                onChange={(v) => setEditValue(v)}
                placeholder={String(globalQuota)}
                style={{ width: 100 }}
              />
              <Button
                type="text"
                icon={<CheckOutlined />}
                onClick={() => handleSave(record.user_id)}
              />
              <Button
                type="text"
                icon={<CloseOutlined />}
                onClick={handleCancelEdit}
              />
            </Space>
          );
        }
        return quota !== null ? (
          <span>
            {quota} <Typography.Text type="secondary">（自定义）</Typography.Text>
          </span>
        ) : (
          <span>
            {globalQuota} <Typography.Text type="secondary">（全局）</Typography.Text>
          </span>
        );
      },
    },
    {
      title: "今日已用",
      dataIndex: "used_today",
      width: 100,
      render: (used: number, record: UserQuotaItem) => {
        const percent = Math.round((used / record.effective_limit) * 100);
        const color = percent >= 100 ? "red" : percent >= 80 ? "orange" : "green";
        return (
          <span>
            <Typography.Text type={percent >= 100 ? "danger" : undefined}>
              {used}
            </Typography.Text>
            <Typography.Text type="secondary"> / {record.effective_limit}</Typography.Text>
          </span>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      render: (_: unknown, record: UserQuotaItem) => {
        if (editingUserId === record.user_id) return null;
        return (
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record.user_id, record.daily_quota)}
          >
            编辑
          </Button>
        );
      },
    },
  ];

  return (
    <div style={{ background: "#fff", padding: 24, borderRadius: 8 }}>
      <Space style={{ marginBottom: 16 }} align="center">
        <Typography.Title level={4} style={{ margin: 0 }}>
          用户额度管理
        </Typography.Title>
        <Tag color="blue">全局限额：{globalQuota}</Tag>
      </Space>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="user_id"
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: handleTableChange,
        }}
      />
    </div>
  );
}
