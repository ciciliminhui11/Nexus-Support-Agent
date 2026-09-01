/**
 * 会话列表项（T031）：标题 + 选中高亮，点击切换当前会话。
 */
import { Typography } from "antd";
import type { Session } from "@/types";

interface SessionItemProps {
  session: Session;
  active: boolean;
  onClick: () => void;
}

export default function SessionItem({ session, active, onClick }: SessionItemProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={active}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      style={{
        padding: "10px 12px",
        borderRadius: 8,
        cursor: "pointer",
        background: active ? "rgba(47,107,255,0.10)" : "transparent",
        border: active ? "1px solid rgba(47,107,255,0.35)" : "1px solid transparent",
        transition: "background 0.15s ease",
      }}
    >
      <Typography.Text
        ellipsis
        style={{
          display: "block",
          fontWeight: active ? 600 : 400,
          color: active ? "#1f4fe0" : "rgba(0,0,0,0.88)",
        }}
      >
        {session.title || "新会话"}
      </Typography.Text>
    </div>
  );
}
