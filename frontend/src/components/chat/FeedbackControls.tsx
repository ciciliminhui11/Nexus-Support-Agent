/**
 * 消息反馈控件（US4，T037）：点赞/点踩可切换，踩时展开可选文字说明。
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
  const [editingDislike, setEditingDislike] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");

  const mineType = data?.mine?.feedback_type ?? null;
  const busy = isLoading || mutation.isPending;

  const submit = (type: "like" | "dislike") => {
    mutation.mutate({
      messageId,
      feedback_type: type,
      feedback_text: type === "dislike" ? feedbackText.trim() || null : null,
    });
    setEditingDislike(false);
    setFeedbackText("");
  };

  const handleLike = () => {
    if (mineType === "like" || busy) return;
    submit("like");
  };

  const handleDislikeClick = () => {
    if (mineType === "dislike" || busy) return;
    setEditingDislike(true);
  };

  return (
    <Flex align="center" gap={4} style={{ marginTop: 8 }} className="feedback-controls">
      <Button
        type="text"
        size="small"
        icon={mineType === "like" ? <LikeFilled /> : <LikeOutlined />}
        onClick={handleLike}
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

      {editingDislike && (
        <Flex gap={4} align="center">
          <Input.TextArea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
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
            onClick={() => submit("dislike")}
          >
            提交
          </Button>
          <Button size="small" onClick={() => setEditingDislike(false)}>
            取消
          </Button>
        </Flex>
      )}
    </Flex>
  );
}
