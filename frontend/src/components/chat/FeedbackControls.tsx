/**
 * 消息反馈控件（US4，T037）：点赞/点踩可切换，均可展开可选文字说明。
 * 仅挂载于已落库的 AI 消息（messageId 就绪且非流式中）。
 */
import { useState } from "react";
import { Button, Flex, Input } from "antd";
import {
  DislikeFilled,
  DislikeOutlined,
  LikeFilled,
  LikeOutlined,
} from "@ant-design/icons";
import { useFeedbackMutation, useFeedbackQuery } from "@/api/queries";

export interface FeedbackControlsProps {
  messageId: number;
}

export default function FeedbackControls({ messageId }: FeedbackControlsProps) {
  const { data, isLoading } = useFeedbackQuery(messageId);
  const mutation = useFeedbackMutation();
  const [editing, setEditing] = useState(false);
  const [editingType, setEditingType] = useState<"like" | "dislike" | null>(null);
  const [draftText, setDraftText] = useState("");

  const mineType = data?.mine?.feedback_type ?? null;
  const mineText = data?.mine?.feedback_text ?? null;
  const busy = isLoading || mutation.isPending;

  const submit = () => {
    if (!editingType) return;
    mutation.mutate({
      messageId,
      feedback_type: editingType,
      feedback_text: draftText.trim() || null,
    });
    setEditing(false);
    setEditingType(null);
    setDraftText("");
  };

  const handleLikeClick = () => {
    if (busy) return;
    // 点击已选中的点赞按钮：展开文字输入框
    if (mineType === "like") {
      setDraftText(mineText ?? "");
      setEditingType("like");
      setEditing(true);
      return;
    }
    // 当前是点踩或无反馈：先切换为点赞
    mutation.mutate({ messageId, feedback_type: "like", feedback_text: null });
  };

  const handleDislikeClick = () => {
    if (busy) return;
    // 点击已选中的点踩按钮：展开文字输入框
    if (mineType === "dislike") {
      setDraftText(mineText ?? "");
      setEditingType("dislike");
      setEditing(true);
      return;
    }
    // 当前是点赞或无反馈：先切换为点踩
    mutation.mutate({ messageId, feedback_type: "dislike", feedback_text: null });
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditingType(null);
    setDraftText("");
  };

  return (
    <Flex align="center" gap={4} style={{ marginTop: 8 }} className="feedback-controls">
      <Button
        type="text"
        size="small"
        icon={mineType === "like" ? <LikeFilled /> : <LikeOutlined />}
        onClick={handleLikeClick}
        disabled={busy}
        aria-label="点赞"
        style={mineType === "like" ? { color: "#2f6bff" } : undefined}
      />
      <Button
        type="text"
        size="small"
        icon={mineType === "dislike" ? <DislikeFilled /> : <DislikeOutlined />}
        onClick={handleDislikeClick}
        disabled={busy}
        aria-label="点踩"
        style={mineType === "dislike" ? { color: "#ff4d4f" } : undefined}
      />

      {editing && (
        <Flex gap={4} align="center">
          <Input.TextArea
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            placeholder="补充说明（可选）"
            autoSize={{ minRows: 1, maxRows: 3 }}
            maxLength={200}
            aria-label="反馈说明"
            style={{ width: 220, fontSize: 12 }}
          />
          <Button
            type="primary"
            size="small"
            loading={mutation.isPending}
            onClick={submit}
          >
            提交
          </Button>
          <Button size="small" onClick={cancelEdit}>
            取消
          </Button>
        </Flex>
      )}
    </Flex>
  );
}