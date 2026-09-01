/**
 * Zustand 轻量 UI 态：当前会话 id、输入草稿。
 * 服务端数据（会话列表/消息）交给 TanStack Query 管理。
 */
import { create } from "zustand";

interface SessionState {
  activeSessionId: number | null;
  draft: string;
  setActiveSessionId: (id: number | null) => void;
  setDraft: (text: string) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  activeSessionId: null,
  draft: "",
  setActiveSessionId: (id) => set({ activeSessionId: id }),
  setDraft: (text) => set({ draft: text }),
}));
