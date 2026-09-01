/**
 * 智能问答主界面（US2/US3）：
 * - 布局：顶栏（品牌/配额/用户/退出 + 窄屏会话入口） + 左侧会话列表（≥1024px）
 * - 消息区：历史回读（useMessages）+ 本地流式 UI（useChatStream） + 自动滚动
 * - 输入区：500 字计数、Enter 发送 / Shift+Enter 换行、配额耗尽禁用
 * - 新会话欢迎态：示例问题引导
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Drawer,
  Flex,
  Input,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  LogoutOutlined,
  MenuOutlined,
  SettingOutlined,
  WechatOutlined,
} from "@ant-design/icons";
import { useQueryClient } from "@tanstack/react-query";
import { MessageBubble } from "@/components/chat/MessageBubble";
import SessionList from "@/components/session/SessionList";
import { QUERY_KEYS, useCreateSession, useMessages, useSessions } from "@/api/queries";
import { useAuthStore } from "@/stores/auth";
import { useSessionStore } from "@/stores/session";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useChatStream, type ChatDraftState } from "@/hooks/useChatStream";
import { MAX_QUESTION_LENGTH } from "@/utils/validation";
import type { Message, Postcheck, Source } from "@/types";

/** 本地渲染的消息结构：历史回读与流式增量统一成同一种形态 */
interface UiMessage {
  key: string;
  role: "user" | "ai";
  content: string;
  sources: Source[];
  state: ChatDraftState;
  messageId: number | null;
  postcheck: Postcheck | null;
  errorText: string | null;
}

const EXAMPLE_QUESTIONS = [
  "退货流程是怎样的？",
  "忘记密码怎么找回？",
  "运费怎么计算？",
];

function useIsNarrow() {
  const [narrow, setNarrow] = useState(() =>
    typeof window === "undefined" ? false : window.matchMedia("(max-width: 1023px)").matches,
  );
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 1023px)");
    const onChange = (e: MediaQueryListEvent) => setNarrow(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return narrow;
}

export default function ChatPage() {
  const { message } = AntApp.useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { user, quota, logout, apply401 } = useAuthStore();
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const draft = useSessionStore((s) => s.draft);
  const setActiveSessionId = useSessionStore((s) => s.setActiveSessionId);
  const setDraft = useSessionStore((s) => s.setDraft);

  // ---------- 服务端数据 ----------
  const { data: sessionsData, isLoading: sessionsLoading } = useSessions();
  const sessions = sessionsData?.items ?? [];
  const { data: history, isLoading: historyLoading } = useMessages(activeSessionId);
  const createSession = useCreateSession();
  const stream = useChatStream();

  // ---------- 本地消息列表 ----------
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const narrow = useIsNarrow();
  const { ref: scrollRef, onScroll } = useAutoScroll<HTMLDivElement>([
    messages,
    stream.state,
  ]);

  // 登录后首次进入：默认选中最近一个会话
  useEffect(() => {
    if (activeSessionId === null && sessions.length > 0) {
      setActiveSessionId(sessions[0].session_id);
    }
  }, [sessions, activeSessionId, setActiveSessionId]);

  // 记录已为哪个 activeSessionId 执行过历史播种，
  // 避免同一会话内重复覆盖本地正在流式的消息。
  const seededSessionRef = useRef<number | null>(null);

  // 历史回读 → 播种本地消息。
  // 仅在切换会话或首次加载时为当前会话播种一次；
  // 同一会话内如果已有本地消息（如正在流式），不覆盖。
  useEffect(() => {
    if (!history) return;
    if (activeSessionId === null) return;
    // 已为本会话播种过，跳过
    if (seededSessionRef.current === activeSessionId) return;

    seededSessionRef.current = activeSessionId;
    setMessages(
      history.items.map((m: Message): UiMessage => ({
        key: `h-${m.message_id}`,
        role: m.role,
        content: m.content,
        sources: m.reference_source ?? [],
        state: "completed",
        messageId: m.message_id,
        postcheck: null,
        errorText: null,
      })),
    );
  }, [history, activeSessionId]);

  // 新建会话
  const handleNewSession = async () => {
    if (stream.streaming) return;
    try {
      const created = await createSession.mutateAsync();
      setActiveSessionId(created.session_id);
      setMessages([]);
      seededSessionRef.current = null;
      setDraft("");
      setDrawerOpen(false);
    } catch {
      message.error("创建会话失败，请稍后重试");
    }
  };

  // 发送（支持示例问题一键触发）
  const handleSend = async (question?: string) => {
    const q = (question ?? draft).trim();
    if (!q) return;
    if (stream.streaming) return;
    if (quota && quota.remaining <= 0) {
      message.warning("今日问答配额已用完，请明天再来");
      return;
    }

    let sid = activeSessionId;
    if (!sid) {
      try {
        const created = await createSession.mutateAsync();
        sid = created.session_id;
        setActiveSessionId(sid);
        // 新会话无历史可播种，直接标记已播种，
        // 避免 useMessages 首次返回空结果时清掉本地占位消息。
        seededSessionRef.current = sid;
      } catch {
        message.error("创建会话失败，请稍后重试");
        return;
      }
    }

    const userKey = `u-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const aiKey = `ai-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        key: userKey,
        role: "user",
        content: q,
        sources: [],
        state: "completed",
        messageId: null,
        postcheck: null,
        errorText: null,
      },
      {
        key: aiKey,
        role: "ai",
        content: "",
        sources: [],
        state: "connecting",
        messageId: null,
        postcheck: null,
        errorText: null,
      },
    ]);
    setDraft("");

    stream.send(sid, q, {
      onUpdate: (patch) =>
        setMessages((prev) =>
          prev.map((m) => (m.key === aiKey ? { ...m, ...patch } : m)),
        ),
      onErrorEvent: (code, msg) => {
        if (code === "unauthorized") {
          apply401();
          return;
        }
        if (msg) {
          message.error(msg);
          setMessages((prev) =>
            prev.map((m) => (m.key === aiKey ? { ...m, errorText: msg } : m)),
          );
        }
      },
      onDone: (messageId) => {
        // 生成完成：更新本地消息的 messageId，并刷新会话标题与配额
        setMessages((prev) =>
          prev.map((m) => (m.key === aiKey ? { ...m, messageId } : m)),
        );
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sessions(1) });
        if (activeSessionId) {
          queryClient.invalidateQueries({ queryKey: QUERY_KEYS.messages(activeSessionId) });
        }
        useAuthStore.getState().fetchMe().catch(() => {});
      },
    });
  };

  const handleStop = () => stream.stop();

  // ---------- 渲染 ----------
  const showWelcome = activeSessionId === null && messages.length === 0;
  const emptyChat =
    activeSessionId !== null && !historyLoading && history && history.items.length === 0;

  const aside = (
    <SessionList
      sessions={sessions}
      activeSessionId={activeSessionId}
      loading={sessionsLoading}
      creating={createSession.isPending}
      onSelect={(id) => {
        if (stream.streaming) return;
        setActiveSessionId(id);
        setMessages([]);
        seededSessionRef.current = null;
        setDrawerOpen(false);
      }}
      onNewSession={handleNewSession}
    />
  );

  return (
    <Flex vertical style={{ height: "100vh" }}>
      {/* ---------- 顶栏 ---------- */}
      <Flex
        align="center"
        justify="space-between"
        style={{
          height: 56,
          padding: "0 16px",
          background: "#fff",
          borderBottom: "1px solid rgba(0,0,0,0.08)",
          flexShrink: 0,
        }}
      >
        <Flex align="center" gap={8}>
          {narrow && (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              aria-label="打开会话列表"
            />
          )}
          <WechatOutlined style={{ color: "#2f6bff", fontSize: 22 }} />
          <Typography.Text strong style={{ fontSize: 16 }}>
            Nexus 智能客服
          </Typography.Text>
        </Flex>

        <Flex align="center" gap={12}>
          {quota ? (
            <Tooltip title={`今日配额 ${quota.used}/${quota.limit}`}>
              <Tag color={quota.remaining > 0 ? "blue" : "red"}>
                剩余 {quota.remaining}
              </Tag>
            </Tooltip>
          ) : null}
          <Typography.Text type="secondary" style={{ maxWidth: 160 }}>
            {user?.account_identifier ?? ""}
          </Typography.Text>
          {user?.role === "admin" && (
            <Button
              type="text"
              icon={<SettingOutlined />}
              onClick={() => navigate("/admin")}
            >
              管理端
            </Button>
          )}
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            退出
          </Button>
        </Flex>
      </Flex>

      {/* ---------- 主体 ---------- */}
      <Flex style={{ flex: 1, minHeight: 0 }}>
        {!narrow && (
          <aside
            style={{
              width: 280,
              flexShrink: 0,
              padding: 12,
              background: "#fff",
              borderRight: "1px solid rgba(0,0,0,0.08)",
              overflow: "hidden",
            }}
          >
            {aside}
          </aside>
        )}

        <main
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            background: "#f5f6fa",
          }}
        >
          {/* 消息区 */}
          <div
            ref={scrollRef}
            onScroll={onScroll}
            style={{ flex: 1, overflowY: "auto", padding: "24px 16px" }}
          >
            <div
              style={{
                maxWidth: "var(--chat-max-width)",
                margin: "0 auto",
                display: "flex",
                flexDirection: "column",
                gap: 16,
              }}
            >
              {showWelcome ? (
                <WelcomePanel onPick={handleSend} />
              ) : messages.length === 0 && historyLoading ? (
                <Flex justify="center" style={{ paddingTop: 80 }}>
                  <Spin tip="加载历史消息…" />
                </Flex>
              ) : messages.length === 0 && emptyChat ? (
                <EmptyChat />
              ) : (
                messages.map((m) => (
                  <MessageBubble
                    key={m.key}
                    role={m.role}
                    content={m.content}
                    sources={m.sources}
                    streaming={m.role === "ai" && (m.state === "connecting" || m.state === "streaming")}
                    onStop={handleStop}
                    errorText={m.errorText}
                    messageId={m.messageId}
                  />
                ))
              )}
            </div>
          </div>

          {/* 输入区 */}
          <Flex vertical style={{ padding: "12px 16px 20px", flexShrink: 0 }}>
            <div
              style={{
                maxWidth: "var(--chat-max-width)",
                margin: "0 auto",
                width: "100%",
                background: "#fff",
                borderRadius: 12,
                border: "1px solid rgba(0,0,0,0.1)",
                padding: 8,
              }}
            >
              <Input.TextArea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder="请输入您的问题，Enter 发送 / Shift+Enter 换行"
                autoSize={{ minRows: 1, maxRows: 5 }}
                maxLength={MAX_QUESTION_LENGTH}
                showCount
                disabled={quota ? quota.remaining <= 0 : false}
                style={{ border: "none", boxShadow: "none", resize: "none" }}
              />
              <Flex align="center" justify="space-between" style={{ marginTop: 8 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {quota && quota.remaining <= 0
                    ? "今日配额已用完"
                    : `最多 ${MAX_QUESTION_LENGTH} 字`}
                </Typography.Text>
                {stream.streaming ? (
                  <Button onClick={handleStop} danger>
                    停止生成
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    disabled={!draft.trim()}
                    onClick={() => void handleSend()}
                  >
                    发送
                  </Button>
                )}
              </Flex>
            </div>
          </Flex>
        </main>
      </Flex>

      {/* 窄屏：会话列表抽屉 */}
      <Drawer
        open={narrow && drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="会话列表"
        width={280}
      >
        {aside}
      </Drawer>
    </Flex>
  );
}

function WelcomePanel({ onPick }: { onPick: (q: string) => void }) {
  return (
    <Flex vertical align="center" gap={16} style={{ paddingTop: 64 }}>
      <WechatOutlined style={{ fontSize: 56, color: "#2f6bff" }} />
      <Typography.Title level={4} style={{ margin: 0 }}>
        您好，我是 Nexus 智能客服
      </Typography.Title>
      <Typography.Text type="secondary">
        您可以询问关于产品、服务、政策等方面的问题
      </Typography.Text>
      <Flex gap={8} justify="center" wrap>
        {EXAMPLE_QUESTIONS.map((q) => (
          <Button key={q} onClick={() => onPick(q)}>
            {q}
          </Button>
        ))}
      </Flex>
    </Flex>
  );
}

function EmptyChat() {
  return (
    <Flex justify="center" style={{ paddingTop: 80 }}>
      <Typography.Text type="secondary">
        新会话开始，试试向下方输入您的问题
      </Typography.Text>
    </Flex>
  );
}
