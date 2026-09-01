/**
 * 文档操作列（US5）：详情（Modal 展示字段与 fail_msg）+ 删除（Popconfirm 二次确认）。
 * 重命名不提供——后端契约无 rename 端点（specs/002/contracts/knowledge-api.md）。
 */
import { useState } from "react";
import { Button, Descriptions, Modal, Popconfirm, Space, Typography } from "antd";
import { DeleteOutlined, EyeOutlined } from "@ant-design/icons";
import type { KnowledgeDoc } from "@/types";

export interface DocActionsProps {
  doc: KnowledgeDoc;
  /** 该文档是否正在删除（驱动按钮 loading） */
  deleting: boolean;
  onDelete: (doc: KnowledgeDoc) => void;
}

export default function DocActions({ doc, deleting, onDelete }: DocActionsProps) {
  const [detailOpen, setDetailOpen] = useState(false);

  return (
    <Space size={0} wrap>
      <Button
        type="link"
        size="small"
        icon={<EyeOutlined />}
        onClick={() => setDetailOpen(true)}
        aria-label={`查看 ${doc.doc_name} 详情`}
      >
        详情
      </Button>
      <Popconfirm
        title="确认删除该文档？"
        description="将级联清理向量与本地文件，且不可恢复。"
        okText="删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        onConfirm={() => onDelete(doc)}
      >
        <Button
          type="link"
          size="small"
          danger
          icon={<DeleteOutlined />}
          loading={deleting}
          aria-label={`删除 ${doc.doc_name}`}
        >
          删除
        </Button>
      </Popconfirm>

      <Modal
        open={detailOpen}
        title={`文档详情：${doc.doc_name}`}
        onCancel={() => setDetailOpen(false)}
        footer={
          <Button onClick={() => setDetailOpen(false)}>
            关闭
          </Button>
        }
      >
        <Descriptions column={1} size="small">
          <Descriptions.Item label="文件名">{doc.doc_name}</Descriptions.Item>
          <Descriptions.Item label="状态">{doc.status}</Descriptions.Item>
          <Descriptions.Item label="上传时间">{doc.upload_time}</Descriptions.Item>
          <Descriptions.Item label="文档 ID">{doc.doc_id}</Descriptions.Item>
          {doc.status === "失败" && doc.fail_msg ? (
            <Descriptions.Item label="失败原因">
              <Typography.Text type="danger">{doc.fail_msg}</Typography.Text>
            </Descriptions.Item>
          ) : null}
        </Descriptions>
      </Modal>
    </Space>
  );
}
