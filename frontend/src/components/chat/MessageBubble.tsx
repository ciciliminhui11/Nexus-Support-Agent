/**
 * 消息气泡（T028）：用户消息（主色浅底/右侧）与 AI 消息（卡片/左侧）。
 * AI 消息用 <Streamdown> 流式渲染（内置净化），内嵌流式光标、引用来源折叠区；
 * streaming 态展示停止按钮。反馈控件位预留（US4 接入）。
 */
import { memo } from "react";
import { Button, Flex } from "antd";
import { StopOutlined } from "@ant-design/icons";
import { Streamdown } from "streamdown";
import { createCodePlugin } from "@streamdown/code";
import { createMathPlugin } from "@streamdown/math";
import { createMermaidPlugin } from "@streamdown/mermaid";
import SourceList from "./SourceList";
import StreamCursor from "./StreamCursor";
import FeedbackControls from "./FeedbackControls";
import type { Source } from "@/types";

// 插件实例模块级单例，避免每次渲染重建（shiki/katex/mermaid 异步加载一次）
const streamdownPlugins = {
  code: createCodePlugin(),
  math: createMathPlugin(),
  mermaid: createMermaidPlugin(),
};

export interface MessageBubbleProps {
  role: "user" | "ai";
  content: string;
  sources?: Source[];
  streaming?: boolean;
  onStop?: () => void;
  errorText?: string | null;
  /** 已落库的 AI 消息 ID（历史回读与流式 finish 后都有值；空则不渲染反馈控件） */
  messageId?: number | null;
}

function MessageBubbleImpl({
  role,
  content,
  sources = [],
  streaming = false,
  onStop,
  errorText = null,
  messageId = null,
}: MessageBubbleProps) {
  if (role === "user") {
    return (
      <Flex justify="flex-end">
        <div
          className="message-bubble message-bubble--user"
          style={{
            maxWidth: "78%",
            padding: "10px 14px",
            borderRadius: 12,
            background: "rgba(47,107,255,0.10)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {content}
        </div>
      </Flex>
    );
  }

  return (
    <Flex justify="flex-start">
      <div
        className="message-bubble message-bubble--ai"
        style={{
          maxWidth: "88%",
          minWidth: 0,
          padding: "12px 16px",
          borderRadius: 12,
          background: "#ffffff",
          border: "1px solid rgba(0,0,0,0.06)",
        }}
      >
        {streaming && !content ? (
          <Flex align="center" gap={8}>
            <StreamCursor />
            <span style={{ color: "rgba(0,0,0,0.45)", fontSize: 13 }}>正在思考…</span>
          </Flex>
        ) : (
          <div className="streamdown-content">
            <Streamdown mode={streaming ? "streaming" : "static"} plugins={streamdownPlugins}>
              {content}
            </Streamdown>
            {streaming && <StreamCursor />}
          </div>
        )}

        {errorText ? (
          <div style={{ marginTop: 8, color: "#ff4d4f", fontSize: 13 }}>{errorText}</div>
        ) : null}

        {sources.length > 0 && !streaming && (
          <div style={{ marginTop: 8 }}>
            <SourceList sources={sources} />
          </div>
        )}

        {!streaming && messageId ? <FeedbackControls messageId={messageId} /> : null}

        {streaming && onStop ? (
          <Flex justify="flex-end" style={{ marginTop: 8 }}>
            <Button size="small" icon={<StopOutlined />} onClick={onStop}>
              停止生成
            </Button>
          </Flex>
        ) : null}
      </div>
    </Flex>
  );
}

export const MessageBubble = memo(MessageBubbleImpl);
