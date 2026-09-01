/**
 * 会话列表（T029）：新建会话按钮 + 会话项列表 + 加载 / 空态。
 */
import { Empty, Flex, Spin } from "antd";
import SessionItem from "./SessionItem";
import NewSessionButton from "./NewSessionButton";
import type { Session } from "@/types";

interface SessionListProps {
  sessions: Session[];
  activeSessionId: number | null;
  loading?: boolean;
  creating?: boolean;
  onSelect: (sessionId: number) => void;
  onNewSession: () => void;
}

export default function SessionList({
  sessions,
  activeSessionId,
  loading = false,
  creating = false,
  onSelect,
  onNewSession,
}: SessionListProps) {
  return (
    <Flex vertical style={{ height: "100%" }} gap={8}>
      <NewSessionButton onClick={onNewSession} loading={creating} />

      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading ? (
          <Spin style={{ display: "block", margin: "24px auto" }} />
        ) : sessions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无会话，点击上方新建"
            style={{ marginTop: 24 }}
          />
        ) : (
          sessions.map((s) => (
            <SessionItem
              key={s.session_id}
              session={s}
              active={s.session_id === activeSessionId}
              onClick={() => onSelect(s.session_id)}
            />
          ))
        )}
      </div>
    </Flex>
  );
}
