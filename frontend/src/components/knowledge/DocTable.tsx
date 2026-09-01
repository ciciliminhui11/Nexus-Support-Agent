/**
 * 文档列表（US5）：客户端搜索（按文件名过滤）+ 表格（名称/状态/上传时间/操作）+ 分页 + 空态。
 * 数据由 KnowledgePage 一次性取回（page_size=100），搜索/分页在本地完成。
 */
import { useEffect, useMemo, useState } from "react";
import { Empty, Input, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import DocStatusTag from "./DocStatusTag";
import DocActions from "./DocActions";
import type { KnowledgeDoc } from "@/types";

export interface DocTableProps {
  items: KnowledgeDoc[];
  loading: boolean;
  /** 正在删除的文档 ID（驱动该行按钮 loading） */
  deletingId: number | null;
  onDelete: (doc: KnowledgeDoc) => void;
}

/** 客户端分页每页条数 */
const PAGE_SIZE = 10;

/** 后端 ISO 时间 → 本地 "YYYY-MM-DD HH:mm"（不引额外依赖） */
function formatUploadTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function DocTable({ items, loading, deletingId, onDelete }: DocTableProps) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((d) => d.doc_name.toLowerCase().includes(q));
  }, [items, search]);

  // 删除末页最后一条或搜索缩窄后，若当前页越界则回退到最后一页
  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (page > maxPage) setPage(maxPage);
  }, [filtered.length, page]);

  const columns: ColumnsType<KnowledgeDoc> = [
    {
      title: "名称",
      dataIndex: "doc_name",
      key: "doc_name",
      ellipsis: true,
      render: (name: string) => <Typography.Text ellipsis={{ tooltip: name }}>{name}</Typography.Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 240,
      render: (_: unknown, doc: KnowledgeDoc) => (
        <DocStatusTag status={doc.status} failMsg={doc.fail_msg} />
      ),
    },
    {
      title: "上传时间",
      dataIndex: "upload_time",
      key: "upload_time",
      width: 180,
      render: (t: string) => formatUploadTime(t),
    },
    {
      title: "操作",
      key: "actions",
      width: 160,
      render: (_: unknown, doc: KnowledgeDoc) => (
        <DocActions doc={doc} deleting={deletingId === doc.doc_id} onDelete={onDelete} />
      ),
    },
  ];

  return (
    <div>
      <Input.Search
        placeholder="按文件名搜索"
        allowClear
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);
        }}
        style={{ maxWidth: 320, marginBottom: 12 }}
        aria-label="搜索文件名"
      />
      <Table<KnowledgeDoc>
        rowKey="doc_id"
        columns={columns}
        dataSource={filtered}
        loading={loading}
        pagination={{
          current: page,
          onChange: setPage,
          pageSize: PAGE_SIZE,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 条`,
        }}
        locale={{
          emptyText: loading ? "加载中…" : <Empty description="暂无文档，请上传 .txt/.md 文件" />,
        }}
      />
    </div>
  );
}
