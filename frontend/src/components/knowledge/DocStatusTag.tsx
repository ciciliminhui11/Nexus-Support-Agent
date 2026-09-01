/**
 * 文档状态标签（US5）：处理中=processing / 就绪=success / 失败=error。
 * 失败状态附带 fail_msg（后端入库失败原因），无 fail_msg 时仅显示标签。
 */
import { Flex, Tag, Typography } from "antd";
import type { KnowledgeDocStatus } from "@/types";

export interface DocStatusTagProps {
  status: KnowledgeDocStatus;
  /** 失败原因（仅 status==="失败" 时展示） */
  failMsg?: string | null;
}

const COLOR_MAP: Record<KnowledgeDocStatus, string> = {
  处理中: "processing",
  就绪: "success",
  失败: "error",
};

export default function DocStatusTag({ status, failMsg }: DocStatusTagProps) {
  return (
    <Flex align="center" gap={4}>
      <Tag color={COLOR_MAP[status]}>{status}</Tag>
      {status === "失败" && failMsg ? (
        <Typography.Text type="danger" style={{ fontSize: 12 }} ellipsis={{ tooltip: failMsg }}>
          {failMsg}
        </Typography.Text>
      ) : null}
    </Flex>
  );
}
