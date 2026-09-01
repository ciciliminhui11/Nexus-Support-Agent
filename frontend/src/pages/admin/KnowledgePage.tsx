/**
 * 知识库管理页（US5）：
 * - 上传（DocUpload，.txt/.md、≤20MB、进度）
 * - 列表（DocTable，客户端搜索/分页/空态）
 * - 存在「处理中」文档时轮询刷新（5s），删除/上传成功后即时刷新
 */
import { useState } from "react";
import { App, Card, Flex, Typography } from "antd";
import {
  useDeleteKnowledgeDoc,
  useKnowledgeDocs,
  useUploadKnowledgeDoc,
} from "@/api/queries";
import DocTable from "@/components/knowledge/DocTable";
import DocUpload from "@/components/knowledge/DocUpload";
import type { KnowledgeDoc } from "@/types";

/** 管理端一次取回最大上限，搜索/分页在客户端完成 */
const PAGE_SIZE = 100;

export default function KnowledgePage() {
  const { message } = App.useApp();
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const docs = useKnowledgeDocs(1, PAGE_SIZE, {
    // 函数式 refetchInterval：存在「处理中」文档时每 5s 轮询，处理完自动停止
    refetchInterval: (q) => {
      const items = (q.state.data as { items?: KnowledgeDoc[] } | undefined)?.items ?? [];
      return items.some((d) => d.status === "处理中") ? 5000 : false;
    },
  });
  const items = docs.data?.items ?? [];

  const uploadDoc = useUploadKnowledgeDoc();
  const deleteDoc = useDeleteKnowledgeDoc();

  const handleUpload = async (file: File, onProgress: (percent: number) => void) => {
    try {
      const res = await uploadDoc.mutateAsync({ file, onProgress });
      message.success(`「${res.doc_name}」已上传，正在处理`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "上传失败，请稍后重试");
      throw err; // 交由 Upload customRequest 标记该文件失败
    }
  };

  const handleDelete = async (doc: KnowledgeDoc) => {
    setDeletingId(doc.doc_id);
    try {
      await deleteDoc.mutateAsync(doc.doc_id);
      message.success(`「${doc.doc_name}」已删除`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "删除失败，请稍后重试");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Flex vertical gap={16} style={{ maxWidth: 960, margin: "0 auto" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        知识库管理
      </Typography.Title>

      <Card title="上传文档" variant="borderless">
        <DocUpload uploading={uploadDoc.isPending} onUpload={handleUpload} />
      </Card>

      <Card title="文档列表" variant="borderless">
        <DocTable
          items={items}
          loading={docs.isLoading}
          deletingId={deletingId}
          onDelete={(doc) => void handleDelete(doc)}
        />
      </Card>
    </Flex>
  );
}
