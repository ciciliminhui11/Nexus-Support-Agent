/**
 * 文档状态标签单测：处理中/就绪/失败三种状态，失败附带 fail_msg。
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DocStatusTag from "@/components/knowledge/DocStatusTag";

describe("DocStatusTag", () => {
  it("处理中状态渲染 processing 标签", () => {
    render(<DocStatusTag status="处理中" />);
    expect(screen.getByText("处理中")).toBeInTheDocument();
  });

  it("就绪状态渲染 success 标签", () => {
    render(<DocStatusTag status="就绪" />);
    expect(screen.getByText("就绪")).toBeInTheDocument();
  });

  it("失败状态渲染 error 标签并展示失败原因", () => {
    render(<DocStatusTag status="失败" failMsg="解析超时" />);
    expect(screen.getByText("失败")).toBeInTheDocument();
    expect(screen.getByText("解析超时")).toBeInTheDocument();
  });

  it("失败但无 fail_msg 时仅渲染标签", () => {
    render(<DocStatusTag status="失败" />);
    expect(screen.getByText("失败")).toBeInTheDocument();
  });
});
