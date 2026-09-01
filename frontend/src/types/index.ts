/**
 * 领域类型定义（对齐 specs/007 data-model 视图模型与后端契约）。
 */

export type AccountType = "phone" | "email";
export type UserRole = "user" | "admin";

export interface User {
  user_id: number;
  account_identifier: string;
  account_type: AccountType;
  role: UserRole;
  created_at: string;
}

export interface Quota {
  limit: number;
  used: number;
  remaining: number;
}

export interface Session {
  session_id: number;
  title: string;
  create_time: string;
}

export interface Source {
  doc_name: string;
  snippet: string;
}

export type MessageRole = "user" | "ai";

/** 消息流式状态（T024 useChatStream 使用） */
export type StreamState = "connecting" | "streaming" | "completed" | "aborted" | "error";

export interface Message {
  message_id: number;
  session_id: number;
  role: MessageRole;
  content: string;
  reference_source: Source[] | null;
  intent_label: string | null;
  create_time: string;
}

export interface FeedbackItem {
  user_id: number;
  feedback_type: "like" | "dislike";
  feedback_text: string | null;
  updated_at: string;
}

/** 管理端反馈列表项 */
export interface FeedbackListItem {
  feedback_id: number;
  message_id: number;
  user_id: number;
  feedback_type: "like" | "dislike";
  feedback_text: string | null;
  message_content: string;
  updated_at: string;
}

/** 当前用户视角的反馈（mine 为 null 表示该用户尚未反馈） */
export interface MineFeedback {
  feedback_type: "like" | "dislike";
  feedback_text: string | null;
  updated_at: string;
}

/** GET /api/message/{id}/feedback 响应（对齐 specs/005 feedback-api） */
export interface FeedbackQueryResponse {
  message_id: number;
  mine: MineFeedback | null;
  all: FeedbackItem[];
}

/** POST /api/message/{id}/feedback 响应 */
export interface FeedbackSubmitResponse {
  message_id: number;
  feedback_type: "like" | "dislike";
  feedback_text: string | null;
  updated_at: string;
}

export type KnowledgeDocStatus = "处理中" | "就绪" | "失败";

export interface KnowledgeDoc {
  doc_id: number;
  doc_name: string;
  status: KnowledgeDocStatus;
  upload_time: string;
  fail_msg: string | null;
}

/** 后端 SSE 事件（POST /api/chat/stream） */
export type Postcheck = { status: "ok" | "review" };

export type SseEvent =
  | { type: "meta"; sources: Source[] }
  | { type: "data"; delta: string }
  | { type: "finish"; message_id: number; postcheck: Postcheck }
  | { type: "error"; code: string; message: string };

export interface ChatRequest {
  session_id: number;
  question: string;
}

/** 后端业务错误（axios 响应 `{code, message}` 结构） */
export interface ApiErrorBody {
  code: string;
  message: string;
}

/** 管理端用户额度列表项 */
export interface UserQuotaItem {
  user_id: number;
  account_identifier: string;
  account_type: AccountType;
  role: UserRole;
  daily_quota: number | null;
  used_today: number;
  effective_limit: number;
}

/** 管理端用户额度列表响应 */
export interface UserQuotaListResponse {
  total: number;
  items: UserQuotaItem[];
}

/** 设置用户额度请求 */
export interface SetUserQuotaRequest {
  daily_quota: number | null;
}

/** 设置用户额度响应 */
export interface SetUserQuotaResponse {
  user_id: number;
  daily_quota: number | null;
  effective_limit: number;
}

/** 全局额度响应 */
export interface GlobalQuotaResponse {
  daily_quota_limit: number;
}
