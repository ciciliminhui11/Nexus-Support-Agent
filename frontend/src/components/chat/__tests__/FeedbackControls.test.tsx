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

function mockQuery(mine: { feedback_type: "like" | "dislike"; feedback_text?: string | null } | null) {
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

  it("点踩立即进入编辑模式（先提交类型），填入文字后二次提交带文字", () => {
    mockQuery(null);
    render(<FeedbackControls messageId={42} />);
    // 第一次点击：提交 dislike 类型，展开文字区
    fireEvent.click(screen.getByLabelText("点踩"));
    expect(mockMutation.mutate).toHaveBeenCalledTimes(1);
    expect(mockMutation.mutate).toHaveBeenCalledWith({
      messageId: 42,
      feedback_type: "dislike",
      feedback_text: null,
    });
    const textarea = screen.getByLabelText("反馈说明");
    fireEvent.change(textarea, { target: { value: "回答不准确" } });
    // 第二次提交：带上文字
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
    mockMutation.isPending = false; // 模拟第一次类型提交完成
    expect(mockMutation.mutate).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /取\s*消/ }));
    // 取消不应触发第二次提交
    expect(mockMutation.mutate).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText("反馈说明")).not.toBeInTheDocument();
  });

  it("已反馈 dislike 时再点踩展开编辑区并回填已有文字", () => {
    mockQuery({ feedback_type: "dislike", feedback_text: "不够详细" });
    render(<FeedbackControls messageId={42} />);
    fireEvent.click(screen.getByLabelText("点踩"));
    // 已为 dislike，不再重复提交类型，直接进入编辑模式
    expect(mockMutation.mutate).not.toHaveBeenCalled();
    // 文字区应回填已有说明
    const textarea = screen.getByLabelText("反馈说明");
    expect(textarea).toHaveValue("不够详细");
    fireEvent.change(textarea, { target: { value: "回答不完整" } });
    fireEvent.click(screen.getByRole("button", { name: /提\s*交/ }));
    expect(mockMutation.mutate).toHaveBeenCalledWith({
      messageId: 42,
      feedback_type: "dislike",
      feedback_text: "回答不完整",
    });
  });

  it("已反馈 dislike 时可切换为 like", () => {
    mockQuery({ feedback_type: "dislike" });
    render(<FeedbackControls messageId={42} />);
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
