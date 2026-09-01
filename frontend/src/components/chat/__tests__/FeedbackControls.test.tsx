/**
 * 消息反馈控件单测：赞/踩提交、踩展开文字说明、已反馈态防重复、取消不提交。
 * mock @/api/queries，避免依赖 react-query / http 层。
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import FeedbackControls from "@/components/chat/FeedbackControls";
import { useFeedbackQuery } from "@/api/queries";

const mockMutation = { mutate: vi.fn(), isPending: false };

vi.mock("@/api/queries", () => ({
  useFeedbackQuery: vi.fn(),
  useFeedbackMutation: () => mockMutation,
}));

const mockUseFeedbackQuery = useFeedbackQuery as Mock;

function mockQuery(mine: { feedback_type: "like" | "dislike" } | null) {
  mockUseFeedbackQuery.mockReturnValue({
    data: { message_id: 42, mine, all: [] },
    isLoading: false,
  });
}

describe("FeedbackControls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMutation.mutate.mockClear();
    mockMutation.isPending = false;
  });

  it("未反馈时点赞直接提交 like", () => {
    mockQuery(null);
    render(<FeedbackControls messageId={42} />);
    fireEvent.click(screen.getByLabelText("点赞"));
    expect(mockMutation.mutate).toHaveBeenCalledWith({
      messageId: 42,
      feedback_type: "like",
      feedback_text: null,
    });
  });

  it("点踩展开文字说明，提交时带上反馈文字", () => {
    mockQuery(null);
    render(<FeedbackControls messageId={42} />);
    fireEvent.click(screen.getByLabelText("点踩"));
    const textarea = screen.getByLabelText("反馈说明");
    fireEvent.change(textarea, { target: { value: "回答不准确" } });
    // AntD 按钮两汉字间自动加空格（提 交），用容忍空白的正则匹配
    fireEvent.click(screen.getByRole("button", { name: /提\s*交/ }));
    expect(mockMutation.mutate).toHaveBeenCalledWith({
      messageId: 42,
      feedback_type: "dislike",
      feedback_text: "回答不准确",
    });
  });

  it("取消不提交，折叠文字输入", () => {
    mockQuery(null);
    render(<FeedbackControls messageId={42} />);
    fireEvent.click(screen.getByLabelText("点踩"));
    fireEvent.click(screen.getByRole("button", { name: /取\s*消/ }));
    expect(mockMutation.mutate).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("反馈说明")).not.toBeInTheDocument();
  });

  it("已反馈 dislike 时再点踩不重复提交，可切换为 like", () => {
    mockQuery({ feedback_type: "dislike" });
    render(<FeedbackControls messageId={42} />);
    fireEvent.click(screen.getByLabelText("点踩"));
    expect(mockMutation.mutate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("点赞"));
    expect(mockMutation.mutate).toHaveBeenCalledWith({
      messageId: 42,
      feedback_type: "like",
      feedback_text: null,
    });
  });

  it("已反馈 like 时再点赞不重复提交", () => {
    mockQuery({ feedback_type: "like" });
    render(<FeedbackControls messageId={42} />);
    fireEvent.click(screen.getByLabelText("点赞"));
    expect(mockMutation.mutate).not.toHaveBeenCalled();
  });
});
