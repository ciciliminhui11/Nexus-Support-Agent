/**
 * TanStack Query hooks：登录态初始化、会话列表、历史消息、知识库列表、配额。
 */
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";
import type {
  FeedbackQueryResponse,
  FeedbackSubmitResponse,
  KnowledgeDoc,
  KnowledgeDocStatus,
  Message,
  Quota,
  Session,
  User,
  UserQuotaItem,
  UserQuotaListResponse,
  SetUserQuotaRequest,
  SetUserQuotaResponse,
  GlobalQuotaResponse,
} from "@/types";

// ---------- key 约定 ----------
export const QUERY_KEYS = {
  me: ["me"] as const,
  sessions: (page: number) => ["sessions", page] as const,
  messages: (sessionId: number) => ["messages", sessionId] as const,
  knowledgeDocs: (page: number) => ["knowledge-docs", page] as const,
  feedback: (messageId: number) => ["feedback", messageId] as const,
  quota: ["quota"] as const,
};

// ---------- 登录态初始化（App 启动时调用一次） ----------
export function useMe() {
  return useQuery<User>({
    queryKey: QUERY_KEYS.me,
    queryFn: async () => {
      const { data } = await http.get<User>("/api/auth/me");
      return data;
    },
    staleTime: 60_000,
    retry: false,
  });
}

// ---------- 会话列表 ----------
export function useSessions(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: QUERY_KEYS.sessions(page),
    queryFn: async () => {
      const { data } = await http.get<{ total: number; items: Session[] }>(
        "/api/session/list",
        { params: { page, page_size: pageSize } },
      );
      return data;
    },
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}

// ---------- 历史消息 ----------
export function useMessages(sessionId: number | null, pageSize = 100) {
  return useQuery({
    queryKey: QUERY_KEYS.messages(sessionId ?? -1),
    queryFn: async () => {
      const { data } = await http.get<{ total: number; items: Message[] }>(
        `/api/session/${sessionId}/messages`,
        { params: { page: 1, page_size: pageSize } },
      );
      return data;
    },
    enabled: sessionId !== null && sessionId > 0,
    staleTime: 10_000,
  });
}

// ---------- 创建会话 ----------
export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await http.post<Session>("/api/session");
      return data;
    },
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.sessions(1) });
      void session;
    },
  });
}

// ---------- 配额 ----------
export function useQuota() {
  return useQuery<Quota>({
    queryKey: QUERY_KEYS.quota,
    queryFn: async () => {
      const { data } = await http.get<{ user_id: number; quota: Quota }>("/api/auth/me");
      return data.quota;
    },
    staleTime: 30_000,
  });
}

// ---------- 知识库列表（管理端，US5 接入） ----------
export function useKnowledgeDocs(
  page = 1,
  pageSize = 20,
  options: {
    /** 轮询间隔（ms）或假值；也支持函数式（TanStack 传入 query，可依当前数据决策） */
    refetchInterval?:
      | number
      | false
      | ((query: { state: { data: unknown } }) => number | false);
  } = {},
) {
  return useQuery({
    queryKey: QUERY_KEYS.knowledgeDocs(page),
    queryFn: async () => {
      const { data } = await http.get<{ total: number; items: KnowledgeDoc[] }>(
        "/api/knowledge/list",
        { params: { page, page_size: pageSize } },
      );
      return data;
    },
    staleTime: 30_000,
    ...options,
  });
}

/** POST /api/knowledge/upload（FormData 字段 `file`，202 后置异步入库） */
export interface KnowledgeUploadResult {
  doc_id: number;
  doc_name: string;
  status: KnowledgeDocStatus;
  upload_time: string;
}

export interface KnowledgeUploadVariables {
  file: File;
  /** 上传进度回调（0-100，用于驱动进度条） */
  onProgress?: (percent: number) => void;
}

export function useUploadKnowledgeDoc() {
  const qc = useQueryClient();
  return useMutation<KnowledgeUploadResult, unknown, KnowledgeUploadVariables>({
    mutationFn: async ({ file, onProgress }) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await http.post<KnowledgeUploadResult>(
        "/api/knowledge/upload",
        form,
        {
          headers: { "Content-Type": "multipart/form-data" },
          onUploadProgress: (e) => {
            if (e.total) onProgress?.(Math.round((e.loaded / e.total) * 100));
          },
        },
      );
      return data;
    },
    onSuccess: () => {
      // 前缀匹配刷新所有分页
      qc.invalidateQueries({ queryKey: ["knowledge-docs"] });
    },
  });
}

/** DELETE /api/knowledge/{id}（204；级联清理向量与文件由后端处理） */
export function useDeleteKnowledgeDoc() {
  const qc = useQueryClient();
  return useMutation<void, unknown, number>({
    mutationFn: async (docId: number) => {
      await http.delete(`/api/knowledge/${docId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-docs"] });
    },
  });
}

// ---------- 005 用户反馈 ----------
/** 单条 AI 消息的反馈状态（当前用户 mine + 全量统计） */
export function useFeedbackQuery(messageId: number | null) {
  return useQuery<FeedbackQueryResponse>({
    queryKey: QUERY_KEYS.feedback(messageId ?? -1),
    queryFn: async () => {
      const { data } = await http.get<FeedbackQueryResponse>(
        `/api/message/${messageId}/feedback`,
      );
      return data;
    },
    enabled: messageId !== null && messageId > 0,
    staleTime: 10_000,
  });
}

export interface FeedbackMutationVariables {
  messageId: number;
  feedback_type: "like" | "dislike";
  feedback_text?: string | null;
}

/** 提交/覆盖一条消息的反馈（后端动态 201/200，成功后刷新该消息反馈状态） */
export function useFeedbackMutation() {
  const qc = useQueryClient();
  return useMutation<FeedbackSubmitResponse, unknown, FeedbackMutationVariables>({
    mutationFn: async ({ messageId, feedback_type, feedback_text }) => {
      const { data } = await http.post<FeedbackSubmitResponse>(
        `/api/message/${messageId}/feedback`,
        { feedback_type, feedback_text: feedback_text ?? null },
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.feedback(variables.messageId) });
    },
  });
}

// ---------- 登录态辅助 ----------
export function useIsAuthenticated(): boolean {
  return useAuthStore((s) => s.status === "authenticated");
}

// ---------- 管理员额度管理 ----------
export function useUserQuotaList(page = 1, pageSize = 20) {
  return useQuery<UserQuotaListResponse>({
    queryKey: ["admin-users-quota", page],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const { data } = await http.get<UserQuotaListResponse>(
        `/api/admin/users?${params.toString()}`
      );
      return data;
    },
    staleTime: 10_000,
  });
}

export function useSetUserQuota() {
  const qc = useQueryClient();
  return useMutation<SetUserQuotaResponse, unknown, SetUserQuotaRequest & { userId: number }>({
    mutationFn: async ({ userId, daily_quota }) => {
      const { data } = await http.put<SetUserQuotaResponse>(
        `/api/admin/users/${userId}/quota`,
        { daily_quota }
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users-quota"] });
    },
  });
}

export function useGlobalQuota() {
  return useQuery<GlobalQuotaResponse>({
    queryKey: ["admin-global-quota"],
    queryFn: async () => {
      const { data } = await http.get<GlobalQuotaResponse>("/api/admin/quota/global");
      return data;
    },
    staleTime: 30_000,
  });
}

export function useSetGlobalQuota() {
  const qc = useQueryClient();
  return useMutation<GlobalQuotaResponse, unknown, GlobalQuotaResponse>({
    mutationFn: async (data) => {
      const { data: res } = await http.put<GlobalQuotaResponse>(
        "/api/admin/quota/global",
        data
      );
      return res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-global-quota"] });
      qc.invalidateQueries({ queryKey: ["admin-users-quota"] });
    },
  });
}
