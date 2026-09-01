/**
 * 反馈管理页面：展示所有用户反馈列表，支持按类型筛选。
 */
import { useEffect, useState } from "react";
import { Table, Tag, Typography, Select, Space, Empty } from "antd";
import { LikeOutlined, DislikeOutlined } from "@ant-design/icons";
import http from "@/api/http";
import type { FeedbackListItem } from "@/types";

interface FeedbackListResponse {
  total: number;
  items: FeedbackListItem[];
}

export default function FeedbackPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<FeedbackListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [feedbackType, setFeedbackType] = useState<string | null>(null);

  const fetchData = async (p: number, ps: number, type: string | null) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(p));
      params.set("page_size", String(ps));
      if (type) params.set("feedback_type", type);

      const res = await http.get<FeedbackListResponse>(
        `/api/message/admin/feedback/list?${params.toString()}`
      );
      setData(res.items);
      setTotal(res.total);
    } catch {
      // 错误已由 http 拦截器处理
    } finally {
      setLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    fetchData(page, pageSize, feedbackType);
  }, []);

  const handleTableChange = (p: number, ps: number) => {
    setPage(p);
    setPageSize(ps);
    fetchData(p, ps, feedbackType);
  };

  const handleTypeChange = (type: string | null) => {
    setFeedbackType(type);
    setPage(1);
    fetchData(1, pageSize, type);
  };

  const columns = [
    {
      title: "反馈ID",
      dataIndex: "feedback_id",
      width: 80,
    },
    {
      title: "消息ID",
      dataIndex: "message_id",
      width: 80,
    },
    {
      title: "用户ID",
      dataIndex: "user_id",
      width: 80,
    },
    {
      title: "反馈类型",
      dataIndex: "feedback_type",
      width: 100,
      render: (type: string) =>
        type === "like" ? (
          <Tag icon={<LikeOutlined />} color="blue">
            点赞
          </Tag>
        ) : (
          <Tag icon={<DislikeOutlined />} color="red">
            点踩
          </Tag>
        ),
    },
    {
      title: "文字说明",
      dataIndex: "feedback_text",
      render: (text: string | null) =>
        text ? (
          <Typography.Text style={{ maxWidth: 300 }} ellipsis={{ tooltip: text }}>
            {text}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">无</Typography.Text>
        ),
    },
    {
      title: "消息内容",
      dataIndex: "message_content",
      render: (content: string) => (
        <Typography.Text type="secondary" style={{ maxWidth: 200 }} ellipsis={{ tooltip: content }}>
          {content}
        </Typography.Text>
      ),
    },
    {
      title: "反馈时间",
      dataIndex: "updated_at",
      width: 180,
      render: (time: string) => new Date(time).toLocaleString("zh-CN"),
    },
  ];

  return (
    <div style={{ background: "#fff", padding: 24, borderRadius: 8 }}>
      <Space style={{ marginBottom: 16 }} align="center">
        <Typography.Title level={4} style={{ margin: 0 }}>
          用户反馈列表
        </Typography.Title>
        <Select
          allowClear
          placeholder="筛选反馈类型"
          style={{ width: 150 }}
          value={feedbackType}
          onChange={handleTypeChange}
          options={[
            { label: "点赞", value: "like" },
            { label: "点踩", value: "dislike" },
          ]}
        />
      </Space>

      {total === 0 && !loading ? (
        <Empty description="暂无反馈数据" />
      ) : (
        <Table
          columns={columns}
          dataSource={data}
          rowKey="feedback_id"
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
      )}
    </div>
  );
}